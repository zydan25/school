PYTHON ?= python
MANAGE = $(PYTHON) manage.py

.PHONY: install check migrations migrate test lint run collectstatic
install:
	$(PYTHON) -m pip install -r requirements/dev.txt

check:
	$(MANAGE) check

migrations:
	$(MANAGE) makemigrations accounts tenants academics platform notifications auditlog

migrate:
	$(MANAGE) migrate

test:
	pytest -q

lint:
	ruff check .

run:
	$(MANAGE) runserver 0.0.0.0:8000

collectstatic:
	$(MANAGE) collectstatic --noinput
