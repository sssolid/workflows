# ===== Makefile =====
# Crown Automotive Image Processing System - Makefile

.PHONY: help setup build start stop logs test clean lint format docs

# Default target
help:
	@echo "Crown Automotive Image Processing System"
	@echo "========================================"
	@echo ""
	@echo "Available commands:"
	@echo "  setup     - Initial system setup"
	@echo "  build     - Build Docker images"
	@echo "  start     - Start all services"
	@echo "  stop      - Stop all services"
	@echo "  restart   - Restart all services"
	@echo "  logs      - View logs"
	@echo "  test      - Run tests"
	@echo "  lint      - Run code linting"
	@echo "  format    - Format code"
	@echo "  clean     - Clean up system"
	@echo "  status    - Show system status"

# Initial setup
setup:
	@echo "🚀 Setting up Crown Automotive Image Processing System..."
	chmod +x setup.sh
	./setup.sh

# Build Docker images
build:
	@echo "🔨 Building Docker images..."
	docker-compose build

# Start services
start:
	@echo "▶️ Starting all services..."
	docker-compose up -d
	@echo "✅ Services started successfully"
	@echo "Dashboard: http://localhost:8080"
	@echo "n8n: http://localhost:5678"

# Stop services
stop:
	@echo "⏹️ Stopping all services..."
	docker-compose down

# Restart services
restart: stop start

# View logs
logs:
	docker-compose logs -f

# Run tests
test:
	@echo "🧪 Running tests..."
	docker-compose exec web_server python -m pytest tests/ -v --cov=src

# Lint code
lint:
	@echo "🔍 Running code linting..."
	docker-compose exec web_server flake8 src/ tests/
	docker-compose exec web_server mypy src/

# Format code
format:
	@echo "🎨 Formatting code..."
	docker-compose exec web_server black src/ tests/
	docker-compose exec web_server isort src/ tests/

# Clean system
clean:
	@echo "🧹 Cleaning up system..."
	docker-compose down -v
	docker system prune -f
	@echo "✅ System cleaned"

# Show system status
status:
	@echo "📊 System Status:"
	docker-compose ps
	@echo ""
	@echo "🔍 Service Health:"
	@curl -s http://localhost:8080/api/status | python -m json.tool || echo "Web server not responding"
	@curl -s http://localhost:8001/health | python -m json.tool || echo "ML processor not responding"
	@curl -s http://localhost:8002/health | python -m json.tool || echo "File monitor not responding"

# Quick development commands
dev-logs:
	docker-compose logs -f web_server ml_processor

dev-restart-web:
	docker-compose restart web_server

dev-restart-ml:
	docker-compose restart ml_processor

# Database commands
db-test:
	docker-compose exec image_processor python -c "from src.services.filemaker_service import FileMakerService; fm = FileMakerService(); print('✅ Database OK' if fm.test_connection() else '❌ Database Failed')"

# File system commands
scan:
	docker-compose exec web_server python -m src.cli scan

process:
	docker-compose exec web_server python -m src.cli process $(FILE_ID) --background-removal

reset:
	docker-compose exec web_server python -m src.cli reset --confirm

# Production deployment
deploy-prod:
	@echo "🚀 Deploying to production..."
	@echo "⚠️ Make sure to update .env with production values!"
	docker-compose -f docker-compose.yml up -d --build
	@echo "✅ Production deployment complete"