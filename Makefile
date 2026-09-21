.PHONY: up real-up wandb-smoke down logs db-up db-down migrate api worker web test test-integration lint

up:
	docker compose up --build

real-up:
	INFERENCE_PROVIDER=wandb docker compose up --build

wandb-smoke:
	INFERENCE_PROVIDER=wandb docker compose run --rm -e INFERENCE_PROVIDER=wandb worker python -m services.worker.worker.smoke

down:
	docker compose down

logs:
	docker compose logs -f

db-up:
	docker compose up -d postgres

db-down:
	docker compose stop postgres

migrate:
	alembic upgrade head

api:
	uvicorn services.api.app.main:app --reload --port 8000

worker:
	python -m services.worker.worker.main

web:
	cd apps/web && npm run dev

test:
	pytest -q

test-integration:
	pytest -q -m integration

lint:
	ruff check .
