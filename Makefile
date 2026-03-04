.DEFAULT_GOAL := help

.PHONY: help install test coverage lint format check build clean

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dev dependencies
	uv sync --extra dev

test: ## Run tests
	uv run --extra dev pytest

coverage: ## Run tests with coverage report
	uv run --extra dev pytest --cov=sitebuilder --cov-report=term-missing

lint: ## Run linter
	uv run --extra dev ruff check src/ tests/

format: ## Format code
	uv run --extra dev ruff format src/ tests/

check: lint test ## Run lint and tests

build: clean ## Build the package
	uv build

clean: ## Remove build artifacts
	rm -rf dist/ build/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
