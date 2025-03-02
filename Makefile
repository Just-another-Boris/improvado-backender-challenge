DOCKER_COMPOSE_FILE = ./docker-compose.yml


run:
	docker compose -f ${DOCKER_COMPOSE_FILE} up -d --build

setup:
	make migrations
	make migrate

migrations:
	docker compose -f ${DOCKER_COMPOSE_FILE} exec app /bin/bash -c "python /manage.py makemigrations"

migrate:
	docker compose -f ${DOCKER_COMPOSE_FILE} exec app /bin/bash -c "python /manage.py migrate"

superuser:
	docker compose -f ${DOCKER_COMPOSE_FILE} exec app /bin/bash -c "python /manage.py createsuperuser"

shell:
	docker compose -f ${DOCKER_COMPOSE_FILE} run --rm app /bin/bash

lint:
	docker compose -f ${DOCKER_COMPOSE_FILE} run --rm app ruff check --fix

test:
	docker compose -f ${DOCKER_COMPOSE_FILE} run --build --rm app pytest -svv

gh-ci-tests
	docker compose -f ${DOCKER_COMPOSE_FILE} run --build --rm app /bin/bash -c "./manage.py makemigrations && ./manage.py migrate && pytest -svv"
