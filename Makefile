.PHONY: all
all: ## Show the available make targets.
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@fgrep "##" Makefile | fgrep -v fgrep

.PHONY: clean
clean: ## Clean the temporary files.
	rm -rf .mypy_cache
	rm -rf .ruff_cache	

lint: ## Format the python code (auto fix)
	poetry run black . || true
	poetry run ruff check . --fix || true
	poetry run pylint . || true


lint-nofix: ## Format the python code (no fix)
	poetry run black . --check
	poetry run ruff check .
	poetry run pylint .

black: ## Run black
	poetry run black .

install: ## Install the dependencies
	poetry install --only main --no-root

install-dev: ## Install the dev dependencies
	poetry install --no-root

install-test: ## Install the test dependencies
	poetry install --with test
