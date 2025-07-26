#!/bin/bash
# ===== dev/setup_dev_environment.sh =====
# Development Environment Setup Script
# Creates sample data and test images for local testing

set -e

echo "🚀 Setting up Crown Image Processing Development Environment"
echo "==========================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "\n${BLUE}==== $1 ====${NC}"
}

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

print_header "Creating Development Directory Structure"

# Create development directories
DEV_DIRS=(
    "dev"
    "dev/config"
    "dev/test_data/input"
    "dev/test_data/processing/originals"
    "dev/test_data/processing/bg_removed"
    "dev/test_data/processing/approved"
    "dev/test_data/processing/temp"
    "dev/test_data/production"
    "dev/test_data/rejected"
    "dev/test_data/logs"
    "dev/test_data/metadata"
    "dev/sample_images"
    "dev/n8n_workflows"
    "assets"
)

for dir in "${DEV_DIRS[@]}"; do
    mkdir -p "$dir"
    print_status "Created directory: $dir"
done

print_header "Creating Sample Test Images"

# Create sample test images using Python
cat > dev/create_sample_images.py << 'EOF'
#!/usr/bin/env python3
"""Create sample test images for development."""

from PIL import Image, ImageDraw, ImageFont
import os

def create_test_image(filename, size=(800, 600), color='white', text=None):
    """Create a test image with optional text."""
    img = Image.new('RGB', size, color)

    if text:
        draw = ImageDraw.Draw(img)
        # Try to use a default font, fall back to basic if not available
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/arial.ttf", 40)
        except:
            font = ImageFont.load_default()

        # Center the text
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (size[0] - text_width) // 2
        y = (size[1] - text_height) // 2

        draw.text((x, y), text, fill='black', font=font)

    return img

# Sample images with various part number patterns
sample_images = [
    # Direct part number matches
    ("J1234567_detail.jpg", (1000, 800), 'lightblue', "J1234567\nFuel Tank\nSkid Plate"),
    ("A5551234_main.jpg", (1200, 900), 'lightgreen', "A5551234\nAir Filter\nElement"),
    ("12345_front.jpg", (800, 600), 'lightyellow', "12345\nEngine\nOil Pan"),
    ("67890_side.jpg", (900, 700), 'lightcoral', "67890\nWater Pump\nAssembly"),

    # Numbered variations (common pattern)
    ("J1234567_2.jpg", (1000, 800), 'lightcyan', "J1234567 #2\nAlternate View"),
    ("12345 (2).jpg", (800, 600), 'lavender', "12345 (2)\nSecond Photo"),
    ("A5551234_v3.jpg", (1200, 900), 'mistyrose', "A5551234 v3\nVersion 3"),

    # Interchange mapping tests (old part numbers)
    ("OLD12345_1.jpg", (800, 600), 'lightsteelblue', "OLD12345\n(maps to 12345)"),
    ("LEGACY67890.jpg", (900, 700), 'lightgoldenrodyellow', "LEGACY67890\n(maps to 67890)"),
    ("J1234567A_old.jpg", (1000, 800), 'lightpink', "J1234567A\n(revision A)"),

    # Manual review required (unclear part numbers)
    ("unknown_part_123.jpg", (800, 600), 'lightgray', "Unknown Part\nNeeds Review"),
    ("crown_part_xyz.jpg", (900, 700), 'wheat', "Crown Part XYZ\nManual Review"),
    ("IMG_001_product.jpg", (1000, 800), 'palegreen', "Generic Image\nNo Clear Part #"),

    # Different file formats
    ("B2222222_shock.png", (800, 600), 'aliceblue', "B2222222\nShock Absorber"),
    ("C3333333_joint.tiff", (1200, 900), 'honeydew', "C3333333\nCV Joint"),
]

# Create sample images directory
os.makedirs('dev/sample_images', exist_ok=True)

print("Creating sample test images...")
for filename, size, color, text in sample_images:
    img = create_test_image(filename, size, color, text)
    img.save(f'dev/sample_images/{filename}')
    print(f"  Created: {filename}")

print(f"Created {len(sample_images)} sample test images")

# Create a few PSD-like files (just renamed images for testing)
psd_files = [
    "J9876543_transmission_mount.psd",
    "A1111111_brake_pads.psd"
]

for psd_name in psd_files:
    # Create a larger, higher quality image for PSD simulation
    img = create_test_image("temp", (2500, 2000), 'white',
                          f"PSD FILE\n{psd_name.split('_')[0]}\nHigh Resolution")

    img.save(f'dev/sample_images/{psd_name}.png')  # Save as PNG
    os.rename(f'dev/sample_images/{psd_name}.png', f'dev/sample_images/{psd_name}')  # Rename to .psd

    print(f"  Created PSD simulation: {psd_name}")

print("Sample images created successfully!")
EOF

python3 dev/create_sample_images.py

print_header "Creating Development Environment Configuration"

# Create development .env file
cat > .env.dev << 'EOF'
# ===== .env.dev =====
# Development Environment Configuration
ENVIRONMENT=development
LOG_LEVEL=DEBUG
TZ=America/New_York

# ===== Processing Settings =====
PROCESSING_INPUT_DIR=/data/input
PROCESSING_PROCESSING_DIR=/data/processing
PROCESSING_PRODUCTION_DIR=/data/production
PROCESSING_REJECTED_DIR=/data/rejected
PROCESSING_METADATA_DIR=/data/metadata
PROCESSING_LOGS_DIR=/data/logs

PROCESSING_MIN_FILE_SIZE_BYTES=512
PROCESSING_MAX_FILE_SIZE_BYTES=52428800
PROCESSING_SCAN_INTERVAL_SECONDS=10
PROCESSING_MIN_RESOLUTION=800

# ===== Mock Database Settings =====
FILEMAKER_DSN_PATH=/dev/config/filemaker.dsn
FILEMAKER_SERVER=mock_database
FILEMAKER_PORT=5432
FILEMAKER_DATABASE=mock_crown
FILEMAKER_USERNAME=dev_user
FILEMAKER_PASSWORD=dev_password

# ===== Web Interface Settings =====
WEB_HOST=0.0.0.0
WEB_PORT=8080
WEB_SECRET_KEY=dev-secret-key-change-in-production
WEB_DEBUG=true

# ===== n8n Settings =====
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=admin
PUBLIC_HOST=localhost

# ===== Mock Notification Settings =====
TEAMS_WEBHOOK_URL=http://mock_teams:3000/webhook

# ===== Development Flags =====
MOCK_FILEMAKER=true
MOCK_TEAMS=true
ENABLE_DEBUG_LOGGING=true
SKIP_ML_MODELS=false
EOF

print_status "Created .env.dev file"

print_header "Creating Mock Teams Webhook Response"

cat > dev/mock_teams.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Mock Teams Webhook</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .notification {
            background: #e3f2fd;
            border: 1px solid #2196f3;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
        }
        .timestamp { color: #666; font-size: 0.9em; }
    </style>
</head>
<body>
    <h1>🔔 Mock Teams Notifications</h1>
    <p>This page simulates Teams webhook notifications during development.</p>

    <div class="notification">
        <strong>Mock Notification Received</strong><br>
        <span class="timestamp">Development notifications will appear here in a real environment.</span>
    </div>

    <h2>Recent Notifications</h2>
    <div id="notifications">
        <div class="notification">
            <strong>File Discovered:</strong> sample_image.jpg<br>
            <span class="timestamp">2024-01-01 12:00:00</span>
        </div>
        <div class="notification">
            <strong>Processing Complete:</strong> background removal finished<br>
            <span class="timestamp">2024-01-01 12:05:00</span>
        </div>
    </div>
</body>
</html>
EOF

print_header "Creating Development FileMaker DSN"

cat > dev/config/filemaker.dsn << 'EOF'
# Development FileMaker DSN (points to mock database)
[ODBC]
DRIVER={Mock FileMaker}
SERVER=mock_database
PORT=5432
DATABASE=mock_crown
UID=dev_user
PWD=dev_password
TIMEOUT=30
CHARSET=UTF-8
EOF

print_header "Creating Development Scripts"

# Create development Makefile
cat > Makefile.dev << 'EOF'
# ===== Makefile.dev =====
# Development environment commands

.PHONY: dev-help dev-setup dev-start dev-stop dev-logs dev-test dev-clean

dev-help:
	@echo "Crown Automotive Image Processing - Development Commands"
	@echo "======================================================"
	@echo ""
	@echo "Available commands:"
	@echo "  dev-setup     - Setup development environment"
	@echo "  dev-start     - Start development environment"
	@echo "  dev-stop      - Stop development environment"
	@echo "  dev-logs      - View development logs"
	@echo "  dev-test      - Run development tests"
	@echo "  dev-clean     - Clean development environment"
	@echo "  dev-images    - Create sample test images"
	@echo "  dev-db        - Show mock database contents"

dev-setup:
	@echo "🚀 Setting up development environment..."
	chmod +x dev/setup_dev_environment.sh
	./dev/setup_dev_environment.sh

dev-start:
	@echo "▶️ Starting development environment..."
	cp .env.dev .env
	docker-compose -f docker-compose.dev.yml up -d
	@echo "✅ Development environment started"
	@echo "Dashboard: http://localhost:8080"
	@echo "n8n: http://localhost:5678 (admin/admin)"
	@echo "Mock Teams: http://localhost:3000"

dev-stop:
	@echo "⏹️ Stopping development environment..."
	docker-compose -f docker-compose.dev.yml down

dev-logs:
	docker-compose -f docker-compose.dev.yml logs -f

dev-test:
	@echo "🧪 Running development tests..."
	docker-compose -f docker-compose.dev.yml exec web_server python -m pytest tests/ -v

dev-clean:
	@echo "🧹 Cleaning development environment..."
	docker-compose -f docker-compose.dev.yml down -v
	docker system prune -f
	rm -rf dev/test_data/*
	@echo "✅ Development environment cleaned"

dev-images:
	@echo "🖼️ Creating sample test images..."
	python3 dev/create_sample_images.py

dev-db:
	@echo "📊 Mock database contents:"
	docker-compose -f docker-compose.dev.yml exec mock_database sqlite3 /app/data/mock_crown.db ".tables"
	docker-compose -f docker-compose.dev.yml exec mock_database sqlite3 /app/data/mock_crown.db "SELECT COUNT(*) as 'Total Parts' FROM Master;"
	docker-compose -f docker-compose.dev.yml exec mock_database sqlite3 /app/data/mock_crown.db "SELECT COUNT(*) as 'Interchange Records' FROM as400_ininter;"

dev-status:
	@echo "📊 Development Environment Status:"
	docker-compose -f docker-compose.dev.yml ps
	@echo ""
	@echo "🔍 Service Health:"
	@curl -s http://localhost:8080/api/status | python -m json.tool || echo "Web server not responding"
EOF

print_header "Creating Test Workflow"

# Create a simple test script
cat > dev/test_workflow.py << 'EOF'
#!/usr/bin/env python3
"""Test the complete workflow locally."""

import requests
import json
import time
import sys

def test_service(name, url):
    """Test if a service is responding."""
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"✅ {name}: OK")
            return True
        else:
            print(f"❌ {name}: HTTP {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ {name}: {e}")
        return False

def main():
    """Run development workflow test."""
    print("🧪 Testing Crown Image Processing Development Environment")
    print("=" * 60)

    # Test all services
    services = [
        ("Web Server", "http://localhost:8080/api/status"),
        ("ML Processor", "http://localhost:8001/health"),
        ("File Monitor", "http://localhost:8002/health"),
        ("Image Processor", "http://localhost:8003/health"),
        ("Teams Notifier", "http://localhost:8004/health"),
        ("n8n", "http://localhost:5678/healthz"),
        ("Mock Teams", "http://localhost:3000"),
    ]

    all_healthy = True
    for name, url in services:
        if not test_service(name, url):
            all_healthy = False

    if not all_healthy:
        print("\n❌ Some services are not responding. Check docker-compose logs.")
        sys.exit(1)

    print("\n✅ All services are healthy!")

    # Test file discovery
    print("\n🔍 Testing file discovery...")
    try:
        response = requests.get("http://localhost:8002/scan")
        data = response.json()
        print(f"📁 Found {data.get('new_files_count', 0)} new files")

        # Test part mapping
        for file_data in data.get('new_files', [])[:3]:
            filename = file_data.get('filename')
            part_mapping = file_data.get('part_mapping')
            if part_mapping:
                print(f"🔧 {filename} → {part_mapping.get('mapped_part_number')} "
                      f"({part_mapping.get('confidence_score', 0):.2f} confidence)")
            else:
                print(f"❓ {filename} → No part mapping")

    except Exception as e:
        print(f"❌ File discovery test failed: {e}")

    print("\n🎉 Development environment test completed!")
    print("\nNext steps:")
    print("1. Visit http://localhost:8080 to see the dashboard")
    print("2. Upload test images or use the sample images in dev/sample_images/")
    print("3. Visit http://localhost:5678 to configure n8n workflows")
    print("4. Check logs with: make dev-logs")

if __name__ == "__main__":
    main()
EOF

chmod +x dev/test_workflow.py

print_header "Development Environment Setup Complete"

echo ""
echo "🎉 Development environment is ready!"
echo ""
echo "Quick start commands:"
echo "  make -f Makefile.dev dev-start    # Start all services"
echo "  make -f Makefile.dev dev-test     # Test the environment"
echo "  make -f Makefile.dev dev-logs     # View logs"
echo "  make -f Makefile.dev dev-stop     # Stop services"
echo ""
echo "Access points:"
echo "  Dashboard:       http://localhost:8080"
echo "  n8n Workflows:   http://localhost:5678 (admin/admin)"
echo "  Mock Teams:      http://localhost:3000"
echo ""
echo "Sample test images created in: dev/sample_images/"
echo "Test various part number patterns and manual override features!"

print_status "Setup complete! Run 'make -f Makefile.dev dev-start' to begin testing."