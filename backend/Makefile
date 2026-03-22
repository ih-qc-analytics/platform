PYTEST   = .venv/bin/pytest
UVICORN  = .venv/bin/uvicorn

ifneq (,$(wildcard .env))
  include .env
  export
endif

run:
	$(UVICORN) app.main:app --reload

seed-ui:
	docker exec -i platform-mysql-1 mysql -u test_user -ptestpassword ihqc_test < tests/seeds/ui_dev.sql

run-dev: seed-ui run

install:
	pip install -r requirements.txt

test:
	$(PYTEST) tests/ -v