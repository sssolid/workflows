"""
Crown Automotive Image Processing - Clean Architecture Implementation
================================================================

This is a restructured implementation following Uncle Bob's Clean Code principles
and the project instructions provided.
"""

# Project Structure:
# src/
# ├── __init__.py
# ├── workflows/               # n8n orchestration glue
# │   ├── __init__.py
# │   ├── file_monitoring.py
# │   └── processing_orchestrator.py
# ├── services/               # Business logic modules
# │   ├── __init__.py
# │   ├── file_monitor_service.py
# │   ├── image_processing_service.py
# │   ├── background_removal_service.py
# │   ├── exif_service.py
# │   ├── filemaker_service.py
# │   └── notification_service.py
# ├── models/                 # Pydantic data models
# │   ├── __init__.py
# │   ├── file_models.py
# │   ├── processing_models.py
# │   ├── metadata_models.py
# │   └── workflow_models.py
# ├── utils/                  # Reusable utilities
# │   ├── __init__.py
# │   ├── logging_config.py
# │   ├── error_handling.py
# │   ├── filesystem_utils.py
# │   └── crypto_utils.py
# ├── config/                 # Settings and configuration
# │   ├── __init__.py
# │   └── settings.py
# ├── web/                    # Web interface
# │   ├── __init__.py
# │   ├── app.py
# │   ├── routes/
# │   └── templates/
# └── main.py                 # CLI/bootstrapper
