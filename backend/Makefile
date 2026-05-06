PYTEST   = .venv/bin/pytest
UVICORN  = .venv/bin/uvicorn

ifneq (,$(wildcard .env))
  include .env
  export
endif

run:
	$(UVICORN) app.main:app --reload

run-prod:
	SOURCE_DB_URL="$$(sed -n "s/^PROD_SOURCE_DB_URL='\(.*\)'/\1/p" .env)" ENVIRONMENT=production $(UVICORN) app.main:app --reload

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
