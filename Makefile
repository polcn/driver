PYTHONPATH := backend

.PHONY: install-dev compile lint format-check test audit check run

install-dev:
	python3 -m pip install --upgrade pip
	python3 -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt

compile:
	python3 -m compileall backend/app tests

lint:
	ruff check backend tests

format-check:
	ruff format --check backend tests

test:
	PYTHONPATH=$(PYTHONPATH) pytest -q tests

audit:
	pip-audit -r backend/requirements.txt

check: compile lint format-check test

run:
	uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
