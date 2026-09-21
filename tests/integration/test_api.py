from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from packages.core.domain.models import JobType, RunEventType
from packages.core.orchestration.baseline import BaselineOrchestrator
from packages.persistence.jobs import DurableJobQueue
from packages.persistence.models import Base, JobRecord
from packages.persistence.repositories import SqlAlchemyUnitOfWork
from services.api.app.main import create_app

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not TEST_DATABASE_URL,
        reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
    ),
]


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client_and_queue(
    session_factory: sessionmaker[Session],
) -> tuple[TestClient, DurableJobQueue]:
    queue = DurableJobQueue(session_factory, worker_id="api-test")
    app = create_app(session_factory=session_factory, queue=queue)
    with TestClient(app) as client:
        yield client, queue


def test_create_problem_run_snapshot_and_event_stream(
    client_and_queue: tuple[TestClient, DurableJobQueue],
    session_factory: sessionmaker[Session],
) -> None:
    client, queue = client_and_queue

    problem_response = client.post(
        "/problems",
        json={
            "title": "API research problem",
            "prompt": "Find a defensible answer.",
        },
    )
    assert problem_response.status_code == 201
    problem = problem_response.json()

    run_response = client.post(
        "/runs",
        json={"problem_id": problem["id"]},
    )
    assert run_response.status_code == 201
    run = run_response.json()
    assert run["status"] == "CREATED"
    assert run["fresh_agent_count"] == 1
    assert run["redundancy_threshold"] == 0.78

    with session_factory() as session:
        jobs = session.execute(select(JobRecord)).scalars().all()
    assert len(jobs) == 1
    assert jobs[0].job_type == JobType.CREATE_GENERATION.value
    assert jobs[0].payload["run_id"] == run["id"]

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    BaselineOrchestrator(uow_factory, queue).start_run(
        run_id=__import__("uuid").UUID(run["id"])
    )

    snapshot_response = client.get(f"/runs/{run['id']}")
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()
    assert snapshot["problem"]["id"] == problem["id"]
    assert snapshot["status"] == "RESEARCHING"
    assert len(snapshot["generations"]) == 1
    assert snapshot["generations"][0]["index"] == 0
    assert len(snapshot["generations"][0]["agents"]) == 4
    assert snapshot["fresh_agent_count"] == 1
    assert all(
        agent["niche"] and agent["origin"]
        for agent in snapshot["generations"][0]["agents"]
    )
    assert snapshot["generations"][0]["submissions"] == []
    assert snapshot["generations"][0]["evaluations"] == []

    events_response = client.get(
        f"/runs/{run['id']}/events",
        params={"follow": "false"},
    )
    assert events_response.status_code == 200
    assert events_response.headers["content-type"].startswith("text/event-stream")
    assert f"event: {RunEventType.RUN_CREATED.value}" in events_response.text
    assert f"event: {RunEventType.RUN_STARTED.value}" in events_response.text


def test_api_returns_not_found_for_missing_resources(
    client_and_queue: tuple[TestClient, DurableJobQueue],
) -> None:
    client, _ = client_and_queue

    missing_problem = client.post(
        "/runs",
        json={"problem_id": str(uuid4())},
    )
    assert missing_problem.status_code == 404

    missing_run = client.get(f"/runs/{uuid4()}")
    assert missing_run.status_code == 404

    missing_events = client.get(
        f"/runs/{uuid4()}/events",
        params={"follow": "false"},
    )
    assert missing_events.status_code == 404


def test_last_event_id_header_is_validated(
    client_and_queue: tuple[TestClient, DurableJobQueue],
) -> None:
    client, _ = client_and_queue

    problem = client.post(
        "/problems",
        json={"title": "Header test", "prompt": "Test SSE resume."},
    ).json()
    run = client.post("/runs", json={"problem_id": problem["id"]}).json()

    response = client.get(
        f"/runs/{run['id']}/events",
        params={"follow": "false"},
        headers={"Last-Event-ID": "not-a-uuid"},
    )
    assert response.status_code == 400


def test_projects_metrics_and_manual_knowledge(
    client_and_queue: tuple[TestClient, DurableJobQueue],
    session_factory: sessionmaker[Session],
) -> None:
    client, queue = client_and_queue
    project_response = client.post(
        "/projects",
        json={"name": "Control room project", "description": "dashboard test"},
    )
    assert project_response.status_code == 201
    project = project_response.json()

    projects = client.get("/projects")
    assert projects.status_code == 200
    assert any(item["id"] == project["id"] for item in projects.json())

    problem = client.post(
        "/problems",
        json={
            "title": "Dashboard problem",
            "prompt": "Exercise dashboard APIs.",
            "project_id": project["id"],
        },
    ).json()
    run = client.post(
        "/runs",
        json={
            "problem_id": problem["id"],
            "critic_count": 0,
            "verification_enabled": False,
        },
    ).json()

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    BaselineOrchestrator(uow_factory, queue).start_run(
        run_id=__import__("uuid").UUID(run["id"])
    )

    injected = client.post(
        f"/runs/{run['id']}/knowledge",
        json={
            "kind": "HYPOTHESIS",
            "content": "Manual operator hypothesis.",
            "confidence": 0.6,
        },
    )
    assert injected.status_code == 201
    assert injected.json()["provenance"]["source"] == "manual_control_room"

    metrics = client.get(f"/runs/{run['id']}/metrics")
    assert metrics.status_code == 200
    assert metrics.json()["generations"] == 1
    assert metrics.json()["knowledge_items"] == 1

    runs = client.get("/runs")
    assert runs.status_code == 200
    assert any(item["id"] == run["id"] for item in runs.json())

    model_states = client.get("/model-states")
    assert model_states.status_code == 200
    assert isinstance(model_states.json(), list)
