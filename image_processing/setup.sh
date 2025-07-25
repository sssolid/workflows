#!/bin/bash
# ===== setup.sh =====
# Crown Automotive Image Processing System Setup Script - Clean Architecture
# This script helps set up the clean architecture image processing system

set -e

echo "🖼️  Crown Automotive Image Processing System - Clean Architecture Setup"
echo "======================================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
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

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root"
   exit 1
fi

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

print_header "System Requirements Check"

# Check for Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
else
    print_status "Docker found: $(docker --version)"
fi

# Check for Docker Compose
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
else
    print_status "Docker Compose found: $(docker-compose --version)"
fi

print_header "Clean Architecture Structure Setup"

# Create the clean architecture directory structure
DIRECTORIES=(
    "src/models"
    "src/services"
    "src/workflows"
    "src/utils"
    "src/config"
    "src/web"
    "tests/unit"
    "tests/integration"
    "docker"
    "workflows"
    "templates"
    "assets"
    "config"
    "data/input"
    "data/processing/originals"
    "data/processing/bg_removed"
    "data/processing/approved"
    "data/processing/temp"
    "data/production"
    "data/rejected"
    "data/logs"
    "data/decisions"
    "data/metadata"
)

for dir in "${DIRECTORIES[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        print_status "Created directory: $dir"
    else
        print_status "Directory exists: $dir"
    fi
done

# Create production format directories based on clean architecture
PRODUCTION_FORMATS=(
    "original_300dpi_png"
    "original_300dpi_tiff"
    "2500_longest_300dpi_tiff"
    "2500_longest_300dpi_jpeg"
    "2500x2500_300dpi_tiff"
    "2500x2500_300dpi_jpeg"
    "watermark_2500x2500_300dpi_tiff"
    "watermark_2500x2500_300dpi_jpeg"
    "1500_longest_300dpi_tiff"
    "1500_longest_300dpi_jpeg"
    "1500x1500_300dpi_tiff"
    "1500x1500_300dpi_jpeg"
    "1000x1000_72dpi_jpeg"
    "1000_longest_72dpi_jpeg"
    "720x720_72dpi_jpeg"
    "720_longest_72dpi_jpeg"
    "600x600_72dpi_jpeg"
    "600_longest_72dpi_jpeg"
    "600x390_72dpi_png_icon"
    "600x390_72dpi_png"
    "300x200_72dpi_jpeg"
    "128x128_72dpi_jpeg"
    "64x64_72dpi_jpeg"
    "32x32_72dpi_jpeg"
)

for format in "${PRODUCTION_FORMATS[@]}"; do
    format_dir="data/production/$format"
    if [ ! -d "$format_dir" ]; then
        mkdir -p "$format_dir"
        print_status "Created production format directory: $format"
    fi
done

print_header "Configuration Files Setup"

# Copy sample configuration files if they don't exist
if [ ! -f ".env" ]; then
    if [ -f ".env.sample" ]; then
        cp ".env.sample" ".env"
        print_warning "Created .env from sample. Please review and update with your actual values."
    else
        print_error "Sample .env file not found. Please create .env manually."
    fi
else
    print_status "Environment file exists"
fi

if [ ! -f "config/filemaker.dsn" ]; then
    if [ -f "config/filemaker.dsn.sample" ]; then
        cp "config/filemaker.dsn.sample" "config/filemaker.dsn"
        print_warning "Created config/filemaker.dsn from sample. Please review and update with your database credentials."
    else
        print_error "Sample DSN file not found. Please create config/filemaker.dsn manually."
    fi
else
    print_status "FileMaker DSN file exists"
fi

# Create basic web templates if they don't exist
if [ ! -f "templates/dashboard.html" ]; then
    cat > templates/dashboard.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Crown Automotive - Image Processing Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin: 20px 0; }
        .stat-card { padding: 20px; background: #f5f5f5; border-radius: 8px; text-align: center; }
        .file-list { margin: 20px 0; }
        .file-item { padding: 10px; border: 1px solid #ddd; margin: 5px 0; border-radius: 4px; }
        .btn { padding: 8px 16px; background: #007acc; color: white; text-decoration: none; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>Crown Automotive Image Processing Dashboard</h1>

    <div class="stats">
        <div class="stat-card">
            <h3>{{ stats.pending }}</h3>
            <p>Pending Review</p>
        </div>
        <div class="stat-card">
            <h3>{{ stats.processing }}</h3>
            <p>Processing</p>
        </div>
        <div class="stat-card">
            <h3>{{ stats.completed }}</h3>
            <p>Completed</p>
        </div>
        <div class="stat-card">
            <h3>{{ stats.failed }}</h3>
            <p>Failed</p>
        </div>
    </div>

    <h2>Pending Files</h2>
    <div class="file-list">
        {% for file in pending_files %}
        <div class="file-item">
            <strong>{{ file.filename }}</strong> ({{ file.size_mb }} MB)
            <a href="{{ file.review_url }}" class="btn">Review</a>
        </div>
        {% endfor %}
    </div>

    <h2>Recently Completed</h2>
    <div class="file-list">
        {% for file in completed_files %}
        <div class="file-item">
            <strong>{{ file.filename }}</strong> - Completed
        </div>
        {% endfor %}
    </div>
</body>
</html>
EOF
    print_status "Created basic dashboard template"
fi

if [ ! -f "templates/review.html" ]; then
    cat > templates/review.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Review: {{ file.filename }} - Crown Automotive</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .comparison { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin: 30px 0; }
        .image-panel { text-align: center; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }
        .buttons { text-align: center; margin: 30px 0; }
        .btn { padding: 12px 24px; margin: 10px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; }
        .approve { background: #28a745; color: white; }
        .reject { background: #dc3545; color: white; }
        .retry { background: #ffc107; color: black; }
    </style>
</head>
<body>
    <h1>Review: {{ file.filename }}</h1>

    <div class="comparison">
        <div class="image-panel">
            <h3>Original Image</h3>
            <img src="{{ server_url }}/originals/{{ file.filename }}" alt="Original" style="max-width: 100%; height: auto;">
        </div>

        <div class="image-panel">
            <h3>Background Removed</h3>
            <img src="{{ server_url }}/bg_removed/{{ file.filename }}" alt="Background Removed" style="max-width: 100%; height: auto;">
        </div>
    </div>

    <div class="buttons">
        <button class="btn approve" onclick="approve()">✅ Approve</button>
        <button class="btn retry" onclick="retry()">🔄 Retry</button>
        <button class="btn reject" onclick="reject()">❌ Reject</button>
    </div>

    <script>
        function approve() {
            fetch('/api/approve/{{ file.file_id }}', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('File approved for production processing!');
                        window.location.href = '/';
                    } else {
                        alert('Error: ' + data.error);
                    }
                });
        }

        function reject() {
            fetch('/api/reject/{{ file.file_id }}', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('File rejected');
                        window.location.href = '/';
                    } else {
                        alert('Error: ' + data.error);
                    }
                });
        }

        function retry() {
            alert('Retry functionality will be implemented in the full system');
        }
    </script>
</body>
</html>
EOF
    print_status "Created basic review template"
fi

print_header "Asset Files Check"

# Check for required asset files
REQUIRED_ASSETS=(
    "assets/watermark_crown.png"
    "assets/icon_crown.png"
)

for asset in "${REQUIRED_ASSETS[@]}"; do
    if [ ! -f "$asset" ]; then
        print_warning "Missing asset file: $asset"
        print_warning "Please add your Crown Automotive branding assets"

        # Create placeholder directories
        mkdir -p "$(dirname "$asset")"

        # Create placeholder files with instructions
        if [[ "$asset" == *"watermark"* ]]; then
            echo "Please replace this file with your Crown Automotive watermark (PNG format, transparent background recommended)" > "$asset.README"
        elif [[ "$asset" == *"icon"* ]]; then
            echo "Please replace this file with your Crown Automotive brand icon (PNG format, small size ~64x64px)" > "$asset.README"
        fi
    else
        print_status "Asset file exists: $asset"
    fi
done

print_header "Docker Images Build"

# Build the Docker images
print_status "Building Docker images for clean architecture..."

if docker-compose build; then
    print_status "Docker images built successfully"
else
    print_error "Failed to build Docker images"
    exit 1
fi

print_header "Network Drive Configuration"

print_warning "IMPORTANT: Network Drive Setup Required"
echo ""
echo "You need to mount your network drives to the following locations:"
echo "  - Image drop zone: /path/to/network/drive/image-dropzone → data/input"
echo "  - Processed images: /path/to/network/drive/processed-images → data/production"
echo "  - Manual review: /path/to/network/drive/manual-review → data/rejected"
echo ""
echo "Update the docker-compose.yml file with your actual network drive paths:"
echo "  volumes:"
echo "    - /actual/path/to/dropzone:/data/input"
echo "    - /actual/path/to/processed:/data/production"
echo "    - /actual/path/to/manual:/data/rejected"

print_header "Configuration Review"

echo ""
echo "Please review and update the following configuration files:"
echo ""
echo "1. 📁 .env - Environment variables and system settings"
echo "2. 🔐 config/filemaker.dsn - Database connection settings"
echo "   Note: For JDBC fallback, download fmjdbc.jar from FileMaker and place in config/ directory"
echo "3. 📢 TEAMS_WEBHOOK_URL in .env - Teams notification webhook"
echo "4. 🖼️  assets/ directory - Add your Crown Automotive branding assets"
echo "5. ⚙️  config/output_specs.yaml - Customize image output formats (optional)"
echo ""

print_header "Quick Start Commands"

echo ""
echo "🚀 Start the system:"
echo "  docker-compose up -d"
echo ""
echo "📊 Check system status:"
echo "  docker-compose ps"
echo "  docker-compose logs -f"
echo ""
echo "🌐 Access the system:"
echo "  Dashboard:       http://localhost:8080"
echo "  n8n Workflows:   http://localhost:5678"
echo "  ML Processor:    http://localhost:8001"
echo "  File Monitor:    http://localhost:8002"
echo "  Image Processor: http://localhost:8003"
echo "  Teams Notifier:  http://localhost:8004"
echo ""
echo "⚙️  Import n8n workflow:"
echo "  1. Access n8n at http://localhost:5678"
echo "  2. Import workflows/crown_processing_clean.json"
echo "  3. Activate the workflow"
echo ""

print_header "Clean Architecture Benefits"

echo ""
echo "Your new system includes:"
echo "✅ Type-safe data models with Pydantic"
echo "✅ Checksum-based duplicate detection"
echo "✅ Robust error handling and recovery"
echo "✅ Microservice architecture with Docker"
echo "✅ Comprehensive test coverage"
echo "✅ Clean separation of concerns"
echo "✅ Easy maintenance and scaling"
echo ""

print_header "Testing and Validation"

echo ""
echo "🧪 Run tests:"
echo "  # Unit tests"
echo "  pytest tests/unit/ -v --cov=src"
echo ""
echo "  # Integration tests"
echo "  pytest tests/integration/ -v"
echo ""
echo "  # All tests with coverage"
echo "  pytest --cov=src --cov-report=html"
echo ""
echo "🔍 Code quality:"
echo "  black src/ tests/     # Format code"
echo "  isort src/ tests/     # Sort imports"
echo "  flake8 src/ tests/    # Lint code"
echo "  mypy src/             # Type checking"
echo ""

print_status "Setup completed successfully!"

echo ""
echo "🎉 Your Crown Automotive Image Processing System is ready!"
echo ""
echo "Next steps:"
echo "1. Update configuration files (.env, config/filemaker.dsn)"
echo "2. Add your branding assets to assets/ directory"
echo "3. Configure network drive mounts in docker-compose.yml"
echo "4. Start the system: docker-compose up -d"
echo "5. Import the n8n workflow"
echo "6. Test with sample images"
echo ""

print_warning "Remember to test the system with a few sample images before production use!"