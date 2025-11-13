.PHONY: gen-docs, build-pypi, build, run-local, test, structure-test, pytest, pytest-docker
include .env
VERSION ?= local

gen-docs: ## Generate component documentation
	@python3 src/solace_ai_connector/tools/gen_component_docs.py

build-pypi: ## Build the pypi package
	@python3 -m build

build: gen-docs build-pypi ## Build the docker image
	@docker build  --platform=linux/amd64 -t solace/solace-ai-connector:${VERSION} .

run-local: ## Run the connector locally using docker-compose
	@docker-compose -f docker-compose-local.yaml run --rm solace-ai-connector

test: structure-test pytest ## Run all tests

structure-test: ## Run container-structure-test
	@docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v ${PWD}/container-structure-test-file.yaml:/container-structure-test-file.yaml \
	gcr.io/gcp-runtimes/container-structure-test:latest test \
	--image docker.io/solace/solace-ai-connector:${VERSION} \
	--config container-structure-test-file.yaml

pytest: ## Run pytest locally
	@pytest

pytest-docker: ## Run pytest inside docker container
	@docker run --rm --entrypoint pytest solace/solace-ai-connector:${VERSION} 

check-uv-installed: ## Check if uv is installed
	@command -v uv >/dev/null 2>&1 || { echo >&2 "uv is required but it's not installed. install: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }

clean: ## Clean local environment (.env and env folders)
	rm -rf .venv
	rm -f uv.lock
	rm -rf env

clean-setup: clean dev-setup ## cleans & build project

dev-setup: ## Set up development environment
	@echo "Setting up development environment..."
	UV_VENV_CLEAR=1 uv venv --python 3.12
	@echo "Activating virtual environment and installing dependencies..."
	uv pip install -e .
	@echo "Development environment setup complete!"
	@echo "To activate the virtual environment, run: source .venv/bin/activate"

uv-clean-cache: ## Clean UV cache
	@echo "🚀 Cleaning UV cache"
	uv cache clean

unit-test: clean dev-setup ## Runs clean, dev-setup and unit tests
	uv pip install -e ".[test,all]"
	uv run --no-sync pytest tests/ -v --cov=src/ --ignore=tests/integration/

integration-test: clean dev-setup ## Runs clean, dev-setup and integration tests
	uv pip install -e ".[all,integration-test]"
	uv run --no-sync pytest tests/integration/ -v

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
