# ===== Makefile =====
# Crown Automotive Image Processing System - Makefile

.PHONY: help setup build start stop logs test clean lint format docs

.DEFAULT_GOAL := help

##@ Makefile.dev Help
help:  ## Show this help.
	@awk 'BEGIN {FS = ":.*?## "}; /^[a-zA-Z0-9_%-]+:.*?## .*$$/ { printf "  %-30s %s\n", $$1, $$2 }' $(MAKEFILE_LIST) | sort

prod-help:  ## Show available production commands
	@grep -E '^[a-zA-Z0-9_%-]+:.*?##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; { printf "  %-30s %s\n", $$1, $$2 }'

setup: ## Initial setup
	@echo "🚀 Setting up Crown Automotive Image Processing System..."
	chmod +x setup.sh
	./setup.sh

build: ## Build Docker images
	@echo "🔨 Building Docker images..."
	docker-compose build

start: ## Start services
	@echo "▶️ Starting all services..."
	docker-compose up -d
	@echo "✅ Services started successfully"
	@echo "Dashboard: http://localhost:8080"
	@echo "n8n: http://localhost:5678"

stop: ## Stop services
	@echo "⏹️ Stopping all services..."
	docker-compose down

restart: ## Restart services
	stop start

logs: ## View logs
	docker-compose logs -f

test: ## Run tests
	@echo "🧪 Running tests..."
	docker-compose exec web_server python -m pytest tests/ -v --cov=src

lint: ## Lint code
	@echo "🔍 Running code linting..."
	docker-compose exec web_server flake8 src/ tests/
	docker-compose exec web_server mypy src/

format: ## Format code
	@echo "🎨 Formatting code..."
	docker-compose exec web_server black src/ tests/
	docker-compose exec web_server isort src/ tests/

clean: ## Clean system
	@echo "🧹 Cleaning up system..."
	docker-compose down -v
	docker system prune -f
	@echo "✅ System cleaned"

rebuild-web-server: ## Rebuild web server
	docker-compose build web_server
	docker-compose up -d --no-deps --build web_server

rebuild-ml-processor: ## Rebuild ml processor
	docker-compose build ml_processor
	docker-compose up -d --no-deps --build ml_processor

rebuild-file-monitor: ## Rebuild file monitor
	docker-compose build file_monitor
	docker-compose up -d --no-deps --build file_monitor

rebuild-image-processor: ## Rebuild image processor
	docker-compose build image_processor
	docker-compose up -d --no-deps --build image_processor

rebuild-teams-notifier: ## Rebuild teams notifier
	docker-compose build teams_notifier
	docker-compose up -d --no-deps --build teams_notifier

rebuild-n8n: ## Rebuild n8n
	docker-compose build n8n
	docker-compose up -d --no-deps --build n8n

rebuild-all: ## Rebuild all
	docker-compose build web_server ml_processor file_monitor image_processor teams_notifier n8n
	docker-compose up -d --no-deps --build web_server ml_processor file_monitor image_processor teams_notifier n8n

status: ## Show system status
	@echo "📊 System Status:"
	docker-compose ps
	@echo ""
	@echo "🔍 Service Health:"
	@curl -s http://localhost:8080/api/status | python -m json.tool || echo "Web server not responding"
	@curl -s http://localhost:8001/health | python -m json.tool || echo "ML processor not responding"
	@curl -s http://localhost:8002/health | python -m json.tool || echo "File monitor not responding"

db-test: ## Test database
	docker-compose exec image_processor python -c "from src.services.filemaker_service import FileMakerService; fm = FileMakerService(); print('✅ Database OK' if fm.test_connection() else '❌ Database Failed')"

scan: ## Scan file system
	docker-compose exec web_server python -m src.cli scan

process: ## Process files
	docker-compose exec web_server python -m src.cli process $(FILE_ID) --background-removal

reset: ## Reset status
	docker-compose exec web_server python -m src.cli reset --confirm

deploy-prod: ## Production deployment
	@echo "🚀 Deploying to production..."
	@echo "⚠️ Make sure to update .env with production values!"
	docker-compose -f docker-compose.yml up -d --build
	@echo "✅ Production deployment complete"