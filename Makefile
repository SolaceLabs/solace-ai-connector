.PHONY: gen-docs, build-pypi, build, run-local, test, structure-test, pytest, pytest-docker
include .env
VERSION ?= local

gen-docs:
	@python3 src/solace_ai_connector/tools/gen_component_docs.py

build-pypi:
	@python3 -m build

build: gen-docs build-pypi
	@docker build  --platform=linux/amd64 -t solace/solace-ai-connector:${VERSION} .

run-local:
	@docker-compose -f docker-compose-local.yaml run --rm solace-ai-connector

test: structure-test pytest

structure-test:
	@docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v ${PWD}/container-structure-test-file.yaml:/container-structure-test-file.yaml \
	gcr.io/gcp-runtimes/container-structure-test:latest test \
	--image docker.io/solace/solace-ai-connector:${VERSION} \
	--config container-structure-test-file.yaml

pytest:
	@pytest

pytest-docker:
	@docker run --rm --entrypoint pytest solace/solace-ai-connector:${VERSION} 
