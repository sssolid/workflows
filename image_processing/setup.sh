#!/bin/bash

# Crown Automotive Image Processing System Setup Script
# This script helps set up the image processing system with proper permissions and configuration

set -e

echo "🖼️  Crown Automotive Image Processing System Setup"
echo "=================================================="

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

print_header "Directory Structure Setup"

# Create required directories
DIRECTORIES=(
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
    "config/models"
    "local-files"
)

for dir in "${DIRECTORIES[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        print_status "Created directory: $dir"
    else
        print_status "Directory exists: $dir"
    fi
done

# Create production format directories based on output_specs.yaml
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
if [ ! -f "config/filemaker.dsn" ]; then
    if [ -f "config/filemaker.dsn.sample" ]; then
        cp "config/filemaker.dsn.sample" "config/filemaker.dsn"
        print_warning "Created config/filemaker.dsn from sample. Please review and update if needed."
    else
        print_error "Sample DSN file not found. Please create config/filemaker.dsn manually."
    fi
else
    print_status "FileMaker DSN file exists"
fi

# Check for required asset files
print_header "Asset Files Check"

REQUIRED_ASSETS=(
    "assets/watermark_crown.png"
    "assets/icon_crown.png"
)

for asset in "${REQUIRED_ASSETS[@]}"; do
    if [ ! -f "$asset" ]; then
        print_warning "Missing asset file: $asset"
        print_warning "Please add your Crown Automotive branding assets"

        # Create placeholder directory
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

print_header "Environment Variables Setup"

# Check for environment variables
if [ -z "$TEAMS_WEBHOOK_URL" ]; then
    print_warning "TEAMS_WEBHOOK_URL environment variable not set"
    print_warning "Teams notifications will not work until this is configured"
fi

# Create .env file template if it doesn't exist
if [ ! -f ".env" ]; then
    cat > .env << EOF
# Crown Automotive Image Processing Environment Variables
# Copy this file and update with your actual values

# Teams Integration
TEAMS_WEBHOOK_URL=https://your-teams-webhook-url-here

# Server Configuration
IMAGE_SERVER_HOST=192.168.10.234
IMAGE_SERVER_PORT=8080

# FileMaker Database
FILEMAKER_DSN_PATH=/config/filemaker.dsn

# n8n Configuration
N8N_BASIC_AUTH_PASSWORD=your_secure_n8n_password

# Timezone
TZ=America/New_York
EOF
    print_status "Created .env template file. Please edit with your actual values."
else
    print_status "Environment file exists"
fi

print_header "File Permissions Setup"

# Set appropriate permissions
chmod +x scripts/*.py
chmod +x setup.sh

# Set permissions for data directories (for Docker container access)
chmod -R 755 data/
chmod -R 755 config/
chmod -R 755 scripts/
chmod -R 755 templates/

print_status "File permissions set"

print_header "Docker Configuration"

print_status "Choose deployment architecture:"
echo "  1. Multi-Container (Recommended) - Microservices with PyTorch support"
echo "  2. Single Container (Simple) - All-in-one container (limited ML features)"
echo ""

read -p "Enter choice (1 or 2) [default: 1]: " architecture_choice
architecture_choice=${architecture_choice:-1}

if [ "$architecture_choice" = "1" ]; then
    print_status "Using multi-container architecture..."
    COMPOSE_FILE="docker-compose-multi.yml"

    # Build all containers
    print_status "Building multi-container images..."
    if docker-compose -f "$COMPOSE_FILE" build; then
        print_status "Multi-container images built successfully"
    else
        print_error "Failed to build multi-container images"
        exit 1
    fi

    print_status "Multi-container setup complete!"
    print_status "Services will run on ports: 5678 (n8n), 8080 (dashboard), 8001-8004 (APIs)"

else
    print_status "Using single-container architecture..."
    COMPOSE_FILE="docker-compose.yml"

    # Build the single container
    print_status "Building single container image..."
    if docker-compose -f "$COMPOSE_FILE" build; then
        print_status "Single container image built successfully"
    else
        print_error "Failed to build single container image"
        exit 1
    fi

    print_warning "Note: Single container has limited ML capabilities due to Alpine/PyTorch compatibility"
    print_status "Single container setup complete!"
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

print_header "Final Steps"

echo ""
echo "Setup completed! Next steps:"
echo ""
echo "1. 📁 Update docker-compose.yml with your network drive paths"
echo "3. 🔐 Edit config/filemaker.dsn with your database credentials"
echo "   Note: fmjdbc.jar is required for JDBC fallback connection"
echo "   Download from FileMaker and place in config/ directory"
echo "3. 📢 Set your Teams webhook URL in .env file"
echo "4. 🖼️  Add your branding assets to the assets/ directory"
echo "5. ⚙️  Review and customize config/server_config.json if needed"
echo "6. 🚀 Start the system with: docker-compose up -d"
echo "7. 🌐 Access the dashboard at: http://192.168.10.234:8080"
echo "8. 🔧 Import the n8n workflow from config/n8n_workflow.json"
echo ""

print_status "Setup script completed successfully!"

echo ""
echo "🔧 Quick Start Commands:"
if [ "$architecture_choice" = "1" ]; then
    echo "  Start system:    docker-compose -f docker-compose-multi.yml up -d"
    echo "  View logs:       docker-compose -f docker-compose-multi.yml logs -f"
    echo "  Stop system:     docker-compose -f docker-compose-multi.yml down"
    echo "  Restart:         docker-compose -f docker-compose-multi.yml restart"
    echo "  Check status:    docker-compose -f docker-compose-multi.yml ps"
    echo ""
    echo "📊 Service URLs:"
    echo "  Dashboard:       http://192.168.10.234:8080"
    echo "  n8n Workflows:   http://192.168.10.234:5678"
    echo "  ML Processor:    http://192.168.10.234:8001"
    echo "  Image Processor: http://192.168.10.234:8003"
else
    echo "  Start system:    docker-compose up -d"
    echo "  View logs:       docker-compose logs -f"
    echo "  Stop system:     docker-compose down"
    echo "  Restart:         docker-compose restart"
    echo ""
    echo "📊 Service URLs:"
    echo "  Dashboard:       http://192.168.10.234:8080"
    echo "  n8n Workflows:   http://192.168.10.234:5678"
fi
echo ""

print_warning "Remember to test the system with a few sample images before production use!"