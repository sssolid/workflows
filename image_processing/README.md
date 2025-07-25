# Crown Automotive Image Processing System

A comprehensive, automated image processing pipeline designed for Crown Automotive's marketing team. This system automatically processes product images, removes backgrounds, and generates multiple production-ready formats with proper metadata.

## 🌟 Features

### Automated Processing Pipeline
- **PSD File Processing**: Direct processing of Photoshop files into multiple formats
- **Background Removal**: AI-powered background removal using rembg with optimized automotive part detection
- **Multi-Format Output**: Generates 24+ different image formats for web, print, and social media
- **Quality Control**: Manual review process for background removal results

### Marketing Team Friendly
- **Web Dashboard**: Clean, intuitive interface for monitoring and review
- **Teams Integration**: Real-time notifications with image previews
- **One-Click Approval**: Simple approve/reject workflow
- **EXIF Editor**: Easy metadata editing with part information

### Production Ready
- **Automatic Metadata**: Pulls part data from FileMaker database
- **Watermarking**: Configurable watermarks and brand icons
- **Multiple DPI**: Web (72 DPI) and print (300 DPI) formats
- **Batch Processing**: Handles multiple files simultaneously

## 🏗️ System Architecture

```
Marketing Team Drops Files → File Monitor → Processing Pipeline
                                ↓
PSD Files ────────────────→ Direct Processing ────────────→ Production Formats
                                ↓
Non-PSD Files ─────────→ Background Removal ─────────→ Review Interface
                                ↓                           ↓
                         Teams Notification          Approve/Reject/Retry
                                                          ↓
                                              Final Production Processing
```

### Components
- **n8n Workflow Engine**: Orchestrates the entire pipeline
- **Python Processing Scripts**: Handle image manipulation and AI processing
- **Web Server**: Provides dashboard and review interfaces
- **FileMaker Integration**: Retrieves product metadata
- **Teams Integration**: Sends notifications and updates

## 📋 Requirements

### System Requirements
- **Docker** and **Docker Compose**
- **Network Storage**: Accessible file shares for input/output
- **FileMaker Database**: With ODBC access (or JDBC with fmjdbc.jar)
- **Microsoft Teams**: Webhook for notifications

### Hardware Recommendations
- **CPU**: 4+ cores (8+ recommended for heavy processing)
- **RAM**: 8GB minimum (16GB+ recommended)
- **Storage**: SSD recommended for processing directories
- **Network**: Reliable connection to network drives

## 🚀 Quick Start

### 1. Clone and Setup
```bash
git clone <repository-url>
cd crown-image-processing
chmod +x setup.sh
./setup.sh
```

### 2. Configure Network Drives
Edit `docker-compose.yml` to mount your network drives:
```yaml
volumes:
  - /path/to/network/image-dropzone:/data/input
  - /path/to/network/processed-images:/data/production
  - /path/to/network/manual-review:/data/rejected
```

### 3. Database Configuration
Edit `config/filemaker.dsn` with your FileMaker credentials:
```ini
DRIVER={FileMaker ODBC};
SERVER=192.168.10.216;
DATABASE=CrownMasterDatabase;
UID=dataportal;
PWD=9ee7381fd5;
PORT=2399;
```

**Note**: The system first tries ODBC connection, then falls back to JDBC. For JDBC fallback, place `fmjdbc.jar` (FileMaker JDBC driver) in the `config/` directory. This can be downloaded from your FileMaker installation or from Claris.

### 4. Teams Integration
Set your Teams webhook URL in `.env`:
```bash
TEAMS_WEBHOOK_URL=https://your-teams-webhook-url
```

### 5. Start the System
```bash
docker-compose up -d
```

### 6. Access Dashboard
Open http://192.168.10.234:8080 in your browser

### 7. Import n8n Workflow
1. Access n8n at http://192.168.10.234:5678
2. Import `config/n8n_workflow.json`
3. Activate the workflow

## 📁 Directory Structure

```
crown-image-processing/
├── 📁 scripts/                    # Processing scripts
│   ├── file_monitor.py           # Watches for new files
│   ├── image_processor.py        # Main image processing
│   ├── background_removal.py     # AI background removal
│   ├── web_server.py            # Dashboard web server
│   ├── teams_notifier.py        # Teams notifications
│   └── 📁 utils/                 # Shared utilities
├── 📁 config/                    # Configuration files
│   ├── output_specs.yaml        # Image format specifications
│   ├── server_config.json       # Server settings
│   ├── filemaker.dsn            # Database connection
│   └── n8n_workflow.json        # n8n workflow definition
├── 📁 templates/                 # Web interface templates
│   ├── dashboard.html           # Main dashboard
│   ├── review.html              # Review interface
│   └── exif_editor.html         # Metadata editor
├── 📁 assets/                    # Branding assets
│   ├── watermark_crown.png      # Watermark image
│   └── icon_crown.png           # Brand icon
├── 📁 data/                      # Data directories
│   ├── 📁 input/                 # 🔥 DROP ZONE - Watch folder
│   ├── 📁 processing/            # Temporary processing
│   ├── 📁 production/            # 📤 Final output files
│   ├── 📁 rejected/              # Failed/rejected files
│   ├── 📁 logs/                  # System logs
│   ├── 📁 decisions/             # Approval decisions
│   └── 📁 metadata/              # Processing metadata
├── docker-compose.yml           # Docker configuration
├── Dockerfile                   # Container definition
├── requirements.txt             # Python dependencies
├── setup.sh                     # Setup script
└── README.md                    # This file
```

## 🔄 Workflow Process

### For PSD Files
1. File dropped in watch folder
2. **Immediate processing** starts
3. Teams notification sent
4. **24 formats generated** automatically
5. Files available in production folder
6. **Completion notification** sent

### For Non-PSD Files
1. File dropped in watch folder
2. **Background removal** processing starts
3. **Review notification** sent to Teams with preview
4. Marketing team **reviews and approves/rejects**
5. If approved: **Production processing** starts
6. **24 formats generated**
7. **Completion notification** sent

## 🖼️ Generated Image Formats

The system generates 24+ image formats optimized for different uses:

### High Resolution (Print)
- **Original PNG/TIFF** (300 DPI, transparent)
- **2500x2500 TIFF/JPEG** (300 DPI, white background)
- **1500x1500 TIFF/JPEG** (300 DPI, white background)
- **Longest side 2500px/1500px** (300 DPI, aspect ratio preserved)

### Web Ready
- **1000x1000 JPEG** (72 DPI, web optimized)
- **720x720 JPEG** (72 DPI, social media)
- **600x600 JPEG** (72 DPI, thumbnails)
- **Special 600x390 PNG** (with brand icon)

### Thumbnails
- **300x200, 128x128, 64x64, 32x32** (various uses)

### Watermarked Versions
- Most formats available with Crown watermark overlay

## 🎛️ Configuration

### Image Processing Settings
Edit `config/server_config.json`:
```json
{
  "image_processing": {
    "min_required_resolution": 2500,
    "default_dpi": 300,
    "quality_settings": {
      "jpeg_quality": 85,
      "tiff_compression": "tiff_lzw"
    }
  }
}
```

### Background Removal Tuning
```json
{
  "background_removal": {
    "default_model": "isnet-general-use",
    "preprocessing": {
      "contrast_factor": 1.2,
      "apply_sharpening": true
    },
    "postprocessing": {
      "alpha_threshold": 40,
      "edge_feathering": 1
    }
  }
}
```

## 👥 Usage for Marketing Team

### Processing Images

#### Option 1: PSD Files (Recommended)
1. **Save your final PSD** to the watch folder
2. **Processing starts immediately**
3. **All formats generated** automatically
4. **Download links** sent via Teams

#### Option 2: Other Image Files
1. **Drop JPG/PNG** in watch folder
2. **Background removal** occurs automatically
3. **Review notification** sent to Teams
4. **Click review link** to approve/reject
5. **Edit metadata** if needed
6. **Production files** generated after approval

### Review Process
1. **Teams notification** includes image preview
2. **Click "Review Images"** to see before/after
3. **Options available**:
   - ✅ **Approve**: Generate all production formats
   - 🔄 **Retry**: Try different AI settings
   - ❌ **Reject**: Move to manual processing
   - 📊 **Edit EXIF**: Update metadata

### Dashboard Features
- **Real-time status** of all processing
- **File browser** for downloads
- **Processing history**
- **Quick approval** buttons

## 🔧 Administration

### Starting/Stopping the System
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop system
docker-compose down

# Restart specific service
docker-compose restart n8n
```

### Monitoring
- **Dashboard**: http://192.168.10.234:8080
- **n8n Admin**: http://192.168.10.234:5678
- **Logs**: `docker-compose logs -f`
- **File System**: Check `data/logs/` directory

### Troubleshooting

#### No Files Being Processed
1. Check file monitor: `docker-compose logs file_watcher`
2. Verify network drive mounts
3. Check file permissions
4. Ensure n8n workflow is active

#### Background Removal Issues
1. Check model cache: `data/config/models/`
2. Try different settings in review interface
3. Check processing logs: `data/logs/background_removal.log`
4. Verify image quality (minimum 2500px recommended)

#### Teams Notifications Not Working
1. Verify webhook URL in `.env`
2. Check Teams channel permissions
3. Test webhook manually
4. Check notification logs

#### Database Connection Issues
1. Verify FileMaker DSN configuration
2. Test database connectivity: `python3 scripts/utils/filemaker_conn.py --test-part TEST123`
3. Check user permissions  
4. For JDBC fallback: ensure `fmjdbc.jar` is in `config/` directory
5. Ensure ODBC driver is installed (tries ODBC first, then JDBC)

### Backup and Maintenance

#### Daily Maintenance
- System automatically cleans old temporary files
- Logs are rotated automatically
- Check dashboard for any errors

#### Weekly Maintenance
- Review processing statistics
- Clean up rejected files if needed
- Monitor disk space usage

#### Database Maintenance
- Ensure part metadata is up to date
- Review and optimize queries if needed

## 🆘 Support

### Getting Help
1. **Check logs** first: `docker-compose logs -f`
2. **Review configuration** files
3. **Test individual components**:
   ```bash
   # Test file monitor
   python3 scripts/file_monitor.py
   
   # Test database connection
   python3 scripts/utils/filemaker_conn.py --test-part PART123
   
   # Test background removal
   python3 scripts/background_removal.py --single-file test.jpg
   ```

### Common Solutions

#### "No new files detected"
- Check network drive permissions
- Verify file formats are supported
- Ensure files are completely uploaded (not being written)

#### "Background removal failed"
- Image may be too complex
- Try higher resolution source
- Use manual processing for difficult images

#### "Teams notifications not appearing"
- Verify webhook URL is correct
- Check Teams channel permissions
- Test with curl or Postman

### Performance Optimization

#### For Heavy Workloads
1. **Increase processing threads** in config
2. **Add more RAM** to Docker containers
3. **Use SSD storage** for processing directories
4. **Scale horizontally** with multiple processing nodes

#### For Network Issues
1. **Use local processing** directories
2. **Implement file staging** area
3. **Add retry logic** for network operations
4. **Monitor bandwidth** usage

## 📊 Analytics and Reporting

The system automatically tracks:
- **Processing times** per file
- **Success/failure rates**
- **Format generation** statistics
- **User approval** patterns
- **Daily/weekly** summaries

Access analytics through:
- **Daily Teams** summary
- **Dashboard** statistics
- **Log analysis** tools
- **File metadata** JSON files

## 🔒 Security Considerations

- **Network isolation**: System runs on local network only
- **Database access**: Uses dedicated service account
- **File permissions**: Proper isolation between components
- **No external dependencies**: All processing happens locally
- **Audit trail**: All actions are logged

## 📝 Version History

### v1.0.0 - Initial Release
- Complete automated processing pipeline
- Teams integration
- Web dashboard
- Background removal with AI
- Multi-format output generation
- FileMaker database integration

---

**Crown Automotive Sales Co., Inc.**  
*Automated Image Processing System*

For technical support or feature requests, contact your IT administrator.