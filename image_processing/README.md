# ===== README.md =====
# Crown Automotive Image Processing System - Clean Architecture

A modern, scalable image processing system built with clean architecture principles for Crown Automotive's marketing team.

## 🌟 Features

### Core Capabilities
- **Automated File Monitoring**: Checksum-based duplicate detection and state tracking
- **AI Background Removal**: Multiple model support (isnet, u2net, silueta)
- **Multi-Format Generation**: 24+ production formats for web, print, and social media
- **Web Interface**: User-friendly review and approval workflow
- **n8n Integration**: Declarative workflow orchestration
- **FileMaker Integration**: Automatic part metadata retrieval
- **Robust State Management**: Recovery from system failures

### Clean Architecture Benefits
- **Type Safety**: Full Pydantic models for all data structures
- **Testability**: 90%+ code coverage with comprehensive test suite
- **Maintainability**: Single responsibility principle, dependency injection
- **Scalability**: Microservice-ready design with clear service boundaries

## 🏗️ Architecture

```
src/
├── models/              # Pydantic data models (pure data, no logic)
│   ├── file_models.py   # File and processing state models
│   ├── processing_models.py  # Processing request/response models
│   ├── metadata_models.py    # EXIF and part metadata models
│   └── workflow_models.py    # Workflow orchestration models
├── services/            # Business logic (single responsibility)
│   ├── file_monitor_service.py      # File discovery and state tracking
│   ├── background_removal_service.py # AI background removal
│   ├── image_processing_service.py   # Multi-format generation
│   ├── filemaker_service.py         # Database integration
│   └── notification_service.py      # Teams notifications
├── workflows/           # n8n orchestration glue (minimal logic)
│   ├── file_monitoring.py           # File monitoring workflow
│   └── processing_orchestrator.py   # Processing coordination
├── utils/               # Reusable utilities
│   ├── crypto_utils.py  # Checksum and file ID generation
│   ├── filesystem_utils.py # File validation and utilities
│   └── error_handling.py   # Consistent error handling
├── config/              # Configuration management
│   └── settings.py      # Pydantic settings with environment variables
├── web/                 # Web interface
│   ├── app.py          # Flask application
│   └── routes/         # API endpoints
└── main.py             # CLI and application entry point
```

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Network storage access for input/output directories
- FileMaker database with ODBC/JDBC access

### Installation

1. **Clone and Setup**
   ```bash
   git clone <repository>
   cd crown-image-processing
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp .env.sample .env
   # Edit .env with your configuration
   ```

3. **Setup Database Connection**
   ```bash
   cp config/filemaker.dsn.sample config/filemaker.dsn
   # Edit with your FileMaker credentials
   # Place fmjdbc.jar in config/ directory for JDBC fallback
   ```

4. **Start Services**
   ```bash
   docker-compose -f docker-compose.clean.yml up -d
   ```

5. **Import n8n Workflow**
   - Access n8n at http://localhost:5678
   - Import `workflows/crown_processing.json`
   - Activate the workflow

### Network Drive Configuration

Update docker-compose.clean.yml volumes:
```yaml
volumes:
  - /path/to/network/image-dropzone:/data/input
  - /path/to/network/processed-images:/data/production
  - /path/to/network/manual-review:/data/rejected
```

## 💻 Development

### Running Tests
```bash
# Unit tests
pytest tests/unit/ -v --cov=src

# Integration tests
pytest tests/integration/ -v

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
```

### CLI Usage

```bash
# Monitor files (standalone)
python -m src.main monitor --once

# Run web server
python -m src.main web

# System status
python -m src.main status

# n8n workflow mode
python -m src.main monitor --workflow scan
python -m src.main monitor --workflow processable
```

## 🔄 Workflow Process

### For PSD Files
1. **File Discovery** → Checksum calculation → State tracking
2. **Direct Processing** → 24 formats generated → Production ready
3. **Teams Notification** → Download links provided

### For Other Images
1. **File Discovery** → Checksum validation → Queue for processing
2. **Background Removal** → AI processing → Quality assessment
3. **Review Interface** → Manual approval/rejection → EXIF editing
4. **Production Processing** → 24 formats generated → Teams notification

## 🧪 Testing Strategy

### Unit Tests
- **Models**: Validation logic and computed properties
- **Services**: Business logic with mocked dependencies
- **Utils**: Pure functions and error handling

### Integration Tests
- **Workflow**: End-to-end n8n integration
- **API**: Web interface endpoints
- **Database**: FileMaker connection and queries

### Test Data Management
```python
# Example test with proper mocking
def test_background_removal(mock_file, bg_service):
    """Test background removal with proper isolation."""
    request = BackgroundRemovalRequest(
        file_id="test_123",
        model=ProcessingModel.ISNET_GENERAL
    )
    
    with patch('rembg.remove') as mock_remove:
        mock_remove.return_value = b"processed_image_data"
        result = bg_service.remove_background(mock_file, request)
        
    assert result.success is True
    assert result.quality_score > 0
```

## 🔧 Key Improvements

### From Original Implementation

1. **State Management**: 
   - Checksum-based file tracking prevents duplicates
   - Recovery from system failures
   - Persistent state across restarts

2. **Type Safety**:
   - Pydantic models for all data structures
   - Compile-time error detection
   - API contract validation

3. **Error Handling**:
   - Consistent error propagation
   - Structured logging
   - Graceful degradation

4. **Testability**:
   - Dependency injection
   - Mocked external services
   - Isolated unit tests

5. **Maintainability**:
   - Single responsibility classes
   - Clear service boundaries
   - Configuration management

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

# Web Interface
WEB_HOST=0.0.0.0
WEB_PORT=8080
WEB_SECRET_KEY=your-secret-key

# Notifications
NOTIFICATION_TEAMS_WEBHOOK_URL=https://your-webhook-url
```

### Processing Models
Available background removal models:
- `isnet-general-use` (recommended for automotive parts)
- `u2net` (general purpose)
- `u2net_human_seg` (portrait-optimized)
- `silueta` (high quality, slower)

## 🚨 Error Recovery

The system automatically handles:
- **File Processing Failures**: Retry with different models
- **System Crashes**: Resume incomplete processing
- **Network Issues**: Queue operations for retry
- **Database Connectivity**: Graceful degradation with cached data

## 🔒 Security

- **Input Validation**: All inputs validated with Pydantic
- **File Upload Security**: Filename sanitization and type checking
- **Database Access**: Read-only connections with least privilege
- **Error Handling**: No sensitive information in error messages

## 📈 Performance

- **Async Processing**: Non-blocking background operations
- **Model Caching**: ML models loaded once and reused
- **Database Connection Pooling**: Efficient database access
- **Checksum-based Deduplication**: Prevents redundant processing

## 🤝 Contributing

1. **Follow Clean Code Principles**: Single responsibility, no side effects
2. **Add Tests**: 90%+ coverage requirement
3. **Type Hints**: All public methods must have type annotations
4. **Documentation**: Docstrings for all public classes and methods
5. **Conventional Commits**: Use conventional commit format

---

**Crown Automotive Sales Co., Inc.**  
*Modern Image Processing with Clean Architecture*