.PHONY: up down build logs ps backend-shell migrate makemigrations test lint frontend-install frontend-build radius-render wg-server-keys prod-config prod-build prod-up prod-down prod-logs prod-ps prod-preflight prod-backup prod-deploy

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

prod-config:
	docker compose --env-file .env.production -f docker-compose.prod.yml config -q

prod-build:
	docker compose --env-file .env.production -f docker-compose.prod.yml build

prod-up:
	docker compose --env-file .env.production -f docker-compose.prod.yml up -d

prod-down:
	docker compose --env-file .env.production -f docker-compose.prod.yml down

prod-logs:
	docker compose --env-file .env.production -f docker-compose.prod.yml logs -f

prod-ps:
	docker compose --env-file .env.production -f docker-compose.prod.yml ps

prod-preflight:
	docker compose --env-file .env.production -f docker-compose.prod.yml run --rm backend python manage.py production_preflight

prod-backup:
	PAMIRNET_ENV_FILE=.env.production bash scripts/backup-production.sh

prod-deploy:
	PAMIRNET_ENV_FILE=.env.production bash scripts/deploy-production.sh
