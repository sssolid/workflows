# Image Processing Automation Project Structure

```
/project-root/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── scripts/
│   ├── file_monitor.py              # Watches for new files
│   ├── image_processor.py           # Main PSD/image processing
│   ├── background_removal.py        # Background removal with rembg
│   ├── web_server.py               # HTTP server for image serving & review
│   ├── teams_notifier.py           # Teams notification helper
│   ├── exif_manager.py             # EXIF data viewing/editing
│   └── utils/
│       ├── __init__.py
│       ├── filemaker_conn.py       # FileMaker database connection
│       └── image_utils.py          # Shared image utilities
├── config/
│   ├── output_specs.yaml          # Image output format specifications
│   ├── server_config.json         # Server configuration
│   └── models/                     # Background removal model cache
├── templates/
│   ├── dashboard.html              # Main dashboard
│   ├── review.html                 # Image review interface
│   ├── exif_editor.html           # EXIF data editor
│   └── teams_message.json         # Teams message template
├── assets/
│   ├── watermark_crown.png         # Watermark image
│   ├── icon_crown.png             # Brand icon
│   └── css/
│       └── dashboard.css          # Dashboard styling
├── local-files/                   # n8n volume mount
└── data/                          # Data directories (will be networked drives)
    ├── input/                     # DROP ZONE - watched folder
    ├── processing/                # Temporary processing
    │   ├── originals/
    │   ├── bg_removed/
    │   ├── approved/
    │   └── temp/
    ├── production/                # Final output
    │   ├── original_300dpi_png/
    │   ├── original_300dpi_tiff/
    │   ├── 2500x2500_300dpi_tiff/
    │   ├── 1500x1500_300dpi_jpeg/
    │   ├── 1000x1000_72dpi_jpeg/
    │   └── [all other formats from YAML]
    ├── rejected/                  # Failed/rejected files
    ├── logs/                      # Processing logs
    ├── decisions/                 # Approval decision files
    └── metadata/                  # EXIF and part metadata cache
```

## Network Drive Mapping
```bash
# These will be mounted to your networked storage
/data/input/           → //network-drive/image-dropzone/
/data/production/      → //network-drive/processed-images/
/data/rejected/        → //network-drive/manual-review/
```

## Docker Volume Mounts
```yaml
volumes:
  - ./data:/data                    # Main data directory
  - ./scripts:/scripts              # Processing scripts
  - ./config:/config                # Configuration files
  - ./templates:/templates          # Web templates
  - ./assets:/assets                # Static assets
  - n8n_data:/home/node/.n8n       # n8n data
```