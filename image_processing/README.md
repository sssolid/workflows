# Crown Automotive Image Processing System

A modern, scalable image processing system built with clean architecture principles for Crown Automotive's marketing team.

## 🌟 Features

### Core Capabilities
- **Automated File Monitoring**: Checksum-based duplicate detection and state tracking
- **AI Background Removal**: Multiple model support (isnet, u2net, silueta)
- **Part Number Mapping**: Intelligent mapping from image filenames to Crown part numbers
- **Multi-Format Generation**: 24+ production formats for web, print, and social media
- **Manual Override System**: Complete user control over system determinations
- **Web Interface**: User-friendly review and approval workflow
- **n8n Integration**: Declarative workflow orchestration
- **FileMaker Integration**: Automatic part metadata retrieval with interchange mapping
- **Robust State Management**: Recovery from system failures

### Clean Architecture Benefits
- **Type Safety**: Full Pydantic models for all data structures
- **Testability**: 90%+ code coverage with comprehensive test suite
- **Maintainability**: Single responsibility principle, dependency injection
- **Scalability**: Microservice-ready design with clear service boundaries

## 🏗️ Architecture

### Complete File Structure
```
.gitignore                              # Git ignore rules
image_processing/
├── src/
│   ├── __init__.py
│   ├── main.py                         # CLI and application entry point
│   ├── cli.py                          # Command line interface
│   ├── models/                         # Pydantic data models
│   │   ├── __init__.py
│   │   ├── file_models.py             # File and processing state models
│   │   ├── processing_models.py       # Processing request/response models
│   │   ├── metadata_models.py         # EXIF and part metadata models
│   │   ├── workflow_models.py         # Workflow orchestration models
│   │   └── part_mapping_models.py     # Part number mapping models
│   ├── services/                       # Business logic (single responsibility)
│   │   ├── __init__.py
│   │   ├── file_monitor_service.py    # File discovery and state tracking
│   │   ├── background_removal_service.py # AI background removal
│   │   ├── image_processing_service.py # Multi-format generation
│   │   ├── filemaker_service.py       # Database integration with interchange
│   │   ├── part_mapping_service.py    # Intelligent part number mapping
│   │   ├── notification_service.py    # Teams notifications
│   │   ├── ml_server.py              # ML processing API server
│   │   ├── monitor_server.py         # File monitoring API server
│   │   ├── processor_server.py       # Image processing API server
│   │   └── notifier_server.py        # Notification API server
│   ├── workflows/                      # n8n orchestration glue
│   │   ├── __init__.py
│   │   ├── file_monitoring.py         # File monitoring workflow
│   │   └── processing_orchestrator.py # Processing coordination
│   ├── web/                           # Web interface with manual overrides
│   │   ├── __init__.py
│   │   └── app.py                     # Flask application with all routes
│   ├── utils/                         # Reusable utilities
│   │   ├── __init__.py
│   │   ├── crypto_utils.py           # Checksum and file ID generation
│   │   ├── filesystem_utils.py       # File validation and utilities
│   │   ├── error_handling.py         # Consistent error handling
│   │   └── logging_config.py         # Logging configuration
│   └── config/                        # Configuration management
│       ├── __init__.py
│       └── settings.py               # Pydantic settings with environment
├── tests/                             # Comprehensive test suite
│   ├── __init__.py
│   ├── unit/                         # Unit tests with mocks
│   │   ├── __init__.py
│   │   ├── test_file_models.py
│   │   ├── test_file_monitor_service.py
│   │   ├── test_background_removal_service.py
│   │   └── test_part_mapping_service.py
│   └── integration/                   # Integration tests
│       ├── __init__.py
│       └── test_workflow_integration.py
├── templates/                         # Web interface templates
│   ├── dashboard.html                # Main dashboard
│   ├── upload.html                   # File upload interface
│   ├── review.html                   # File review interface
│   ├── edit_metadata.html            # Manual override interface
│   └── error.html                    # Error page
├── config/                           # Configuration files
│   ├── output_specs.yaml            # Image output format specifications
│   └── filemaker.dsn.sample         # Database connection template
├── docker/                           # Docker configurations
│   ├── Dockerfile.web               # Web server container
│   ├── Dockerfile.ml                # ML processing container
│   ├── Dockerfile.monitor           # File monitoring container
│   ├── Dockerfile.processor         # Image processor container
│   ├── Dockerfile.notifier          # Notification service container
│   └── Dockerfile.n8n               # n8n workflow engine container
├── workflows/                        # n8n workflow definitions
│   └── crown_processing_clean.json  # Main processing workflow
├── assets/                           # Static assets and branding
│   └── .gitkeep
├── data/                             # Runtime data directories
│   └── .gitkeep
├── docker-compose.yml               # Multi-container orchestration
├── .env.sample                      # Environment configuration template
├── Makefile                         # Development and deployment commands
├── setup.sh                         # System setup script
├── requirements.txt                 # Main Python dependencies
├── requirements.web.txt             # Web server specific dependencies
├── requirements.ml.txt              # ML processing dependencies
├── requirements.monitor.txt         # File monitor dependencies
├── requirements.processor.txt       # Image processor dependencies
├── requirements.notifier.txt        # Notification service dependencies
├── README.md                        # This file
├── STRUCTURE.md                     # Architecture documentation
└── pyproject.toml                   # Python project configuration
```

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Network storage access for input/output directories
- FileMaker database with ODBC/JDBC access
- At least 8GB RAM (for ML processing)

### Installation

1. **Clone and Setup**
   ```bash
   git clone <repository>
   cd crown-image-processing
   chmod +x setup.sh
   ./setup.sh
   ```

2. **Configure Environment**
   ```bash
   cp .env.sample .env
   # Edit .env with your configuration
   vim .env
   ```

3. **Setup Database Connection**
   ```bash
   cp config/filemaker.dsn.sample config/filemaker.dsn
   # Edit with your FileMaker credentials
   # Place fmjdbc.jar in config/ directory for JDBC fallback
   ```

4. **Configure Network Drives**
   ```bash
   # Update docker-compose.yml volumes section:
   # - /path/to/network/image-dropzone:/data/input
   # - /path/to/network/processed-images:/data/production
   # - /path/to/network/manual-review:/data/rejected
   ```

5. **Start Services**
   ```bash
   docker-compose up -d
   ```

6. **Import n8n Workflow**
   - Access n8n at http://localhost:5678
   - Import `workflows/crown_processing_clean.json`
   - Activate the workflow

## 🔄 Processing Workflow

### Intelligent Part Number Mapping

The system automatically maps image filenames to correct Crown part numbers:

1. **Filename Analysis**: Extracts potential part numbers from patterns like:
   - `J1234567_2.jpg` → `J1234567`
   - `12345 (2).jpg` → `12345`
   - `crown_12345_detail.jpg` → `12345`

2. **Database Lookup**: Checks against:
   - Current active parts in Master table
   - Interchange mappings using AS400_ININTER table
   - Fuzzy matching for variations

3. **Manual Override**: Web interface allows complete override of:
   - Part number mapping
   - Image metadata (title, description, keywords)
   - EXIF data
   - Processing decisions

### For PSD Files
1. **File Discovery** → Part number mapping → Direct processing
2. **Format Generation** → 24 formats created → Production ready
3. **Teams Notification** → Download links provided

### For Other Images
1. **File Discovery** → Part number mapping → Background removal queue
2. **AI Processing** → Quality assessment → Manual review interface
3. **Metadata Editing** → User can override all system determinations
4. **Approval** → Format generation → Teams notification

## 💻 Development

### Local Testing Environment

For testing without external dependencies (no FileMaker, no network drives, no production environment):

```bash
# Setup development environment with mock services
chmod +x dev/setup_dev_environment.sh
./dev/setup_dev_environment.sh

# Start development environment
make -f Makefile.dev dev-start

# Access development system
# Dashboard: http://localhost:8080
# n8n: http://localhost:5678 (admin/admin)
# Mock Teams: http://localhost:3000

# Run tests
python3 dev/test_workflow.py

# Stop when done
make -f Makefile.dev dev-stop
```

The development environment includes:
- **Mock FileMaker database** with sample Crown parts and interchange data
- **Sample test images** covering various part number patterns
- **Mock Teams notifications** for testing webhook integration
- **Complete workflow testing** without external dependencies

See [Development Testing Guide](dev/README_DEVELOPMENT.md) for detailed instructions.

### Production Development

### Running Tests
```bash
# Install development dependencies
pip install -e .[dev]

# Unit tests
pytest tests/unit/ -v --cov=src

# Integration tests (requires database)
pytest tests/integration/ -v -m "requires_db"

# All tests with coverage
pytest --cov=src --cov-report=html
```

### Code Quality
```bash
# Format code
black src/ tests/
isort src/ tests/

# Lint
flake8 src/ tests/
mypy src/

# Type checking
mypy src/
```

### CLI Usage

```bash
# System status
python -m src.cli status

# Scan for files
python -m src.cli scan --processable

# Process specific file
python -m src.cli process FILE_ID --background-removal

# Test system components
python -m src.cli test

# Reset system state
python -m src.cli reset --confirm
```

## 🔧 Key Features

### Part Number Mapping System

**Intelligent filename parsing** with patterns for:
- Standard Crown part numbers (J1234567, A12345)  
- Numbered variations (12345_2.jpg, 12345 (2).jpg)
- Descriptive suffixes (12345_detail.jpg, 12345_main.jpg)

**Database integration** with:
- Interchange table queries using AS400_ININTER
- Current part validation against Master table
- Fuzzy matching for similar parts

**Manual override capabilities**:
- Web interface for all corrections
- Part number suggestions with autocomplete
- Reason tracking for audit trail

### Manual Override System

Users can override **any** system determination:
- **Part Number**: With autocomplete suggestions from database
- **Image Title**: Auto-populated from part description
- **Description**: From part metadata or manual entry
- **Keywords**: Combined from database fields or custom
- **EXIF Data**: Complete control over embedded metadata

### Error Recovery

The system automatically handles:
- **File Processing Failures**: Retry with different models
- **System Crashes**: Resume incomplete processing
- **Network Issues**: Queue operations for retry
- **Database Connectivity**: Graceful degradation with cached data
- **Duplicate Detection**: Checksum-based prevention

## 🌐 Web Interface

### Dashboard
- **Real-time Status**: Processing statistics and file counts
- **Quick Actions**: Approve, reject, or edit files
- **Part Mapping Status**: Confidence indicators for automatic mappings

### Review Interface
- **Side-by-side Comparison**: Original vs processed images
- **Processing History**: Complete audit trail
- **Part Information**: Automatic lookup with manual override

### Metadata Editor
- **Smart Suggestions**: Database-driven autocomplete
- **Override Tracking**: Reason logging for manual changes
- **Batch Operations**: Multiple file processing

## 📊 Configuration

### Environment Variables
```bash
# Processing
PROCESSING_INPUT_DIR=/data/input
PROCESSING_MIN_FILE_SIZE_BYTES=1024
PROCESSING_SCAN_INTERVAL_SECONDS=30

# Database  
FILEMAKER_DSN_PATH=/config/filemaker.dsn
FILEMAKER_SERVER=192.168.10.216
FILEMAKER_USERNAME=your_username
FILEMAKER_PASSWORD=your_password

# Web Interface
WEB_HOST=0.0.0.0
WEB_PORT=8080
WEB_SECRET_KEY=your-secret-key

# Notifications
TEAMS_WEBHOOK_URL=https://your-webhook-url
```

### Processing Models
Available background removal models:
- `isnet-general-use` (recommended for automotive parts)
- `u2net` (general purpose)
- `u2net_human_seg` (portrait-optimized)
- `silueta` (high quality, slower)

## 🔒 Security

- **Input Validation**: All inputs validated with Pydantic
- **File Upload Security**: Filename sanitization and type checking
- **Database Access**: Read-only connections with least privilege
- **Error Handling**: No sensitive information in error messages
- **Environment Variables**: All secrets in .env files (not in VCS)

## 📈 Performance

- **Async Processing**: Non-blocking background operations
- **Model Caching**: ML models loaded once and reused
- **Database Connection Pooling**: Efficient database access
- **Checksum-based Deduplication**: Prevents redundant processing
- **Interchange Caching**: Part mappings cached for performance

## 🚨 Troubleshooting

### Common Issues

1. **Database Connection Fails**
   ```bash
   # Test connection
   python -m src.cli test
   # Check DSN file and JDBC driver
   ls -la config/filemaker.dsn config/fmjdbc.jar
   ```

2. **Part Mapping Not Working**
   ```bash
   # Check interchange cache
   docker-compose logs image_processor | grep interchange
   # Refresh mappings
   docker-compose restart image_processor
   ```

3. **Background Removal Slow**
   ```bash
   # Check available models
   curl http://localhost:8001/models
   # Monitor ML processing
   docker-compose logs -f ml_processor
   ```

## 🤝 Contributing

1. **Follow Clean Code Principles**: Single responsibility, no side effects
2. **Add Tests**: 90%+ coverage requirement  
3. **Type Hints**: All public methods must have type annotations
4. **Documentation**: Docstrings for all public classes and methods
5. **Conventional Commits**: Use conventional commit format

### Development Setup
```bash
# Install with development dependencies
pip install -e .[dev]

# Setup pre-commit hooks
pre-commit install

# Run full test suite
make test

# Check code quality
make lint
```

---

**Crown Automotive Sales Co., Inc.**  
*Modern Image Processing with Clean Architecture*