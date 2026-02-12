# --- Variables ---
COMPOSE = docker-compose
EXEC = $(COMPOSE) exec web
PYTHON = $(EXEC) python

# --- Build & Infrastructure ---
.PHONY: setup
setup: build up migrate import demo  ## Full first-time setup

.PHONY: build
build:
	$(COMPOSE) build

.PHONY: up
up:
	$(COMPOSE) up -d

.PHONY: down
down:
	$(COMPOSE) down

# --- Database & Migrations ---
.PHONY: migrate
migrate:
	$(PYTHON) manage.py makemigrations routing
	$(PYTHON) manage.py makemigrations
	$(PYTHON) manage.py migrate

.PHONY: import
import:
	$(PYTHON) manage.py import_fuel_data fuel_prices.csv --use-mock

# --- Testing & Utilities ---
.PHONY: demo
demo:
	$(PYTHON) demo.py

.PHONY: logs
logs:
	$(COMPOSE) logs -f web

.PHONY: shell
shell:
	$(EXEC) /bin/bash