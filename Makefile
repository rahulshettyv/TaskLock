lint:
	python -m pylint $(shell git ls-files --modified --others '*.py')

auto-lint:
	python -m black --safe $(shell git ls-files --modified --others '*.py')

full-lint:
	python -m pylint task_lock

full-auto-lint:
	python -m black --safe task_lock

test:
	ENVIRONMENT=test python -m pytest -v -s -p no:warnings

test-report:
	ENVIRONMENT=test python -m pytest -v -s -p no:warnings --cov=. --cov-report=html:coverage