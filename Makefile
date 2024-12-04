lint:
	pylint $(shell git ls-files --modified --others '*.py')

auto-lint:
	black --safe $(shell git ls-files --modified --others '*.py')

full-lint:
	pylint task_lock

full-auto-lint:
	black --safe task_lock

test:
	ENVIRONMENT=test pytest -v -s -p no:warnings

test-report:
	ENVIRONMENT=test pytest -v -s -p no:warnings --cov=. --cov-report=html:coverage