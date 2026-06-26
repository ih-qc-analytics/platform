PYTEST   = .venv/bin/pytest
UVICORN  = .venv/bin/uvicorn
PYTHON   = .venv/bin/python
RUFF     = .venv/bin/ruff

run:
	$(UVICORN) app.main:app --host 0.0.0.0 --port 8000 --reload

run-prod:
	ENVIRONMENT=prod $(UVICORN) app.main:app --host 0.0.0.0 --port 8000 --reload

run-dev:
	ENVIRONMENT=dev $(UVICORN) app.main:app --host 0.0.0.0 --port 8000 --reload

seed-ui:
	docker exec -i platform-mysql-1 mysql -u test_user -ptestpassword ihqc_test -e \
		"SET FOREIGN_KEY_CHECKS=0; \
		TRUNCATE cart_product; TRUNCATE cart; TRUNCATE seller_lead; \
		TRUNCATE \`lead\`; TRUNCATE seller; TRUNCATE product; \
		TRUNCATE exam_cat; TRUNCATE zone; \
		SET FOREIGN_KEY_CHECKS=1;"
	docker exec -i platform-mysql-1 mysql -u test_user -ptestpassword ihqc_test < tests/seeds/ui_dev.sql

install:
	pip install -r requirements.txt

test:
	$(PYTEST) tests/ -v

migrate:
	.venv/bin/alembic upgrade head

migrate-down:
	.venv/bin/alembic downgrade -1

migrate-status:
	.venv/bin/alembic current

exchange-rate-backfill:
	$(PYTHON) tools/backfill_exchange_rates.py

lint:
	$(RUFF) check .

format:
	$(RUFF) format .

format-check:
	$(RUFF) format --check .

build-check:
	$(PYTHON) -m compileall -q app

ci: lint format-check build-check test

dev:
	supabase status > /dev/null 2>&1 || supabase start
	docker-compose -p platform up mysql -d
	ENVIRONMENT=dev $(UVICORN) app.main:app --host 0.0.0.0 --port 8000 --reload

db-up:
	docker-compose -p platform up mysql -d

db-down:
	docker-compose -p platform down

db-logs:
	docker logs platform-mysql-1

db-reset:
	docker-compose -p platform down -v
	docker-compose -p platform up mysql -d
