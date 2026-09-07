.PHONY: up down build logs ps backend-shell migrate makemigrations test lint frontend-install frontend-build radius-render wg-server-keys

up:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

ps:
	docker compose ps

backend-shell:
	docker compose exec backend python manage.py shell

migrate:
	docker compose exec backend python manage.py migrate

makemigrations:
	docker compose exec backend python manage.py makemigrations

test:
	docker compose exec backend python manage.py test
	docker compose exec frontend npm run lint
	docker compose exec frontend npm run build

lint:
	docker compose exec backend ruff check .
	docker compose exec frontend npm run lint

frontend-install:
	docker compose exec frontend npm install

frontend-build:
	docker compose exec frontend npm run build

radius-render:
	docker compose exec backend python manage.py render_radius_clients

wg-server-keys:
	docker compose exec backend python manage.py wireguard_server_keys
