.PHONY: db-up db-down migrate test test-integration lint

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

migrate:
	alembic upgrade head

test:
	pytest -q

test-integration:
	pytest -q -m integration

lint:
	ruff check .
