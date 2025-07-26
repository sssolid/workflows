# Crown Image Processing - Local Development Testing Guide

This guide walks you through testing the complete Crown Automotive Image Processing System locally without any external dependencies.

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose installed
- At least 4GB RAM available
- Python 3.11+ (for setup scripts)

### 1. Setup Development Environment

```bash
# Clone the repository and navigate to it
cd crown-image-processing

# Make the setup script executable and run it
chmod +x dev/setup_dev_environment.sh
./dev/setup_dev_environment.sh

# Or use the Makefile
make -f Makefile.dev dev-setup
```

### 2. Start the Development Environment

```bash
# Start all services
make -f Makefile.dev dev-start

# This will:
# - Copy .env.dev to .env
# - Start all Docker containers
# - Initialize mock database with sample data
# - Create sample test images
```

### 3. Access the System

Once started, you can access:

- **Main Dashboard**: http://localhost:8080
- **n8n Workflows**: http://localhost:5678 (admin/admin)
- **Mock Teams Notifications**: http://localhost:3000

### 4. Test the Complete Workflow

```bash
# Run the automated test suite
python3 dev/test_workflow.py

# Or view logs to see what's happening
make -f Makefile.dev dev-logs
```

## 🧪 Testing Scenarios

### Scenario 1: Part Number Mapping

The system includes sample images that test different part number mapping scenarios:

1. **Direct Matches** (high confidence):
   - `J1234567_detail.jpg` → Maps to J1234567 (Fuel Tank Skid Plate)
   - `A5551234_main.jpg` → Maps to A5551234 (Air Filter)
   - `12345_front.jpg` → Maps to 12345 (Oil Pan)

2. **Numbered Variations** (medium confidence):
   - `J1234567_2.jpg` → Maps to J1234567
   - `12345 (2).jpg` → Maps to 12345
   - `A5551234_v3.jpg` → Maps to A5551234

3. **Interchange Mappings** (medium confidence):
   - `OLD12345_1.jpg` → Maps OLD12345 to 12345
   - `LEGACY67890.jpg` → Maps LEGACY67890 to 67890
   - `J1234567A_old.jpg` → Maps J1234567A to J1234567

4. **Manual Review Required** (low confidence):
   - `unknown_part_123.jpg` → Requires manual review
   - `crown_part_xyz.jpg` → Requires manual review
   - `IMG_001_product.jpg` → Requires manual review

### Scenario 2: Complete Processing Workflow

1. **Upload Images**:
   ```bash
   # Copy sample images to input directory (simulates network drop)
   cp dev/sample_images/*.jpg dev/test_data/input/
   ```

2. **Monitor Discovery**:
   - Visit http://localhost:8080 to see new files discovered
   - Check file monitor: http://localhost:8002/scan

3. **Review Part Mapping**:
   - Click "Review" on any discovered file
   - See automatic part number mapping results
   - Test confidence indicators and manual override

4. **Manual Override Testing**:
   - Click "Edit Metadata" on any file
   - Test part number autocomplete
   - Override system determinations
   - Save changes and see audit trail

5. **Background Removal**:
   - The ML processor will automatically process non-PSD files
   - Monitor progress in dashboard
   - Review results when complete

6. **Format Generation**:
   - Approve files for production
   - Watch automatic generation of 24+ formats
   - Check production directory

### Scenario 3: n8n Workflow Testing

1. **Access n8n**: http://localhost:5678 (admin/admin)

2. **Import Workflow**:
   ```bash
   # Copy the workflow file to n8n
   cp workflows/crown_processing_clean.json dev/n8n_workflows/
   ```

3. **Test Manual Execution**:
   - Create a new workflow in n8n
   - Add HTTP Request nodes pointing to local services
   - Test file discovery: `GET http://file_monitor:8002/processable`
   - Test background removal: `POST http://ml_processor:8001/remove_background`

### Scenario 4: Database Integration Testing

1. **Check Mock Database**:
   ```bash
   # View database contents
   make -f Makefile.dev dev-db
   
   # Connect to mock database directly
   docker-compose -f docker-compose.dev.yml exec mock_database sqlite3 /app/data/mock_crown.db
   ```

2. **Test Part Lookups**:
   ```sql
   -- In the SQLite prompt:
   SELECT * FROM Master WHERE AS400_NumberStripped = 'J1234567';
   SELECT * FROM as400_ininter WHERE ICPNO = 'OLD12345';
   ```

3. **Test API Endpoints**:
   ```bash
   # Test part search
   curl "http://localhost:8080/api/part-suggestions?q=J123"
   
   # Test system status
   curl "http://localhost:8080/api/status"
   ```

## 🔧 Development Features

### Mock Services

1. **Mock FileMaker Database**:
   - SQLite database with sample Crown parts
   - Interchange table with old→new part mappings
   - Automatic part metadata lookup

2. **Mock Teams Notifications**:
   - Simple HTTP server that logs notifications
   - View at http://localhost:3000

3. **Development Configuration**:
   - Debug logging enabled
   - Hot reload for code changes
   - Reduced scan intervals for faster testing

### Sample Data

The development environment includes:

- **8 sample part records** with realistic Crown data
- **5 interchange mappings** for testing old→new part resolution
- **15+ test images** covering various filename patterns
- **PSD simulation files** for testing direct format generation

### Debugging Tools

```bash
# View all service logs
make -f Makefile.dev dev-logs

# View specific service logs
docker-compose -f docker-compose.dev.yml logs -f web_server
docker-compose -f docker-compose.dev.yml logs -f ml_processor

# Check service health
curl http://localhost:8080/api/status
curl http://localhost:8001/health
curl http://localhost:8002/health

# View file monitor state
curl http://localhost:8002/status

# Test part mapping directly
python3 -c "
from src.services.part_mapping_service import PartMappingService
mapper = PartMappingService()
result = mapper.map_filename_to_part_number('J1234567_2.jpg')
print(f'Mapped to: {result.mapped_part_number}')
print(f'Confidence: {result.confidence_score}')
"
```

## 🧹 Cleanup and Reset

```bash
# Stop all services
make -f Makefile.dev dev-stop

# Clean everything (removes all data)
make -f Makefile.dev dev-clean

# Reset just the file monitor state
docker-compose -f docker-compose.dev.yml exec web_server python -m src.cli reset --confirm

# Recreate sample images
make -f Makefile.dev dev-images
```

## 🚨 Troubleshooting

### Common Issues

1. **Services not starting**:
   ```bash
   # Check Docker resources
   docker system df
   docker system prune -f
   
   # Restart with fresh build
   docker-compose -f docker-compose.dev.yml up --build -d
   ```

2. **ML models downloading slowly**:
   ```bash
   # Pre-download models
   docker-compose -f docker-compose.dev.yml exec ml_processor python -c "
   from rembg import new_session
   new_session('isnet-general-use')
   "
   ```

3. **Port conflicts**:
   ```bash
   # Check what's using ports
   lsof -i :8080
   lsof -i :5678
   
   # Stop conflicting services or change ports in docker-compose.dev.yml
   ```

4. **Database connection issues**:
   ```bash
   # Test mock database directly
   docker-compose -f docker-compose.dev.yml exec mock_database python mock_database_server.py
   ```

### Performance Tips

1. **Faster ML Processing**:
   - Reduce image sizes in dev/sample_images/
   - Use CPU-optimized models in development
   - Set `SKIP_ML_MODELS=true` for UI-only testing

2. **Faster File Discovery**:
   - Reduce scan interval: `PROCESSING_SCAN_INTERVAL_SECONDS=5`
   - Use smaller test images
   - Limit number of test files

## ✅ Validation Checklist

After setup, verify these features work:

- [ ] Dashboard loads and shows system status
- [ ] File upload interface works
- [ ] Sample images are discovered automatically
- [ ] Part number mapping shows confidence scores
- [ ] Manual override interface loads and saves changes
- [ ] Background removal processes images (may be slow)
- [ ] Format generation creates multiple file formats
- [ ] Teams notifications appear in mock webhook
- [ ] n8n workflow can be imported and executed
- [ ] Database queries return sample part data

## 🎯 Next Steps

Once local testing is complete:

1. **Production Deployment**:
   - Update `.env` with production values
   - Configure real FileMaker connection
   - Set up actual Teams webhook
   - Deploy using `docker-compose.yml` (not dev version)

2. **Network Drive Integration**:
   - Mount actual network drives
   - Test with real Crown part numbers
   - Validate interchange mappings

3. **Workflow Customization**:
   - Import production n8n workflows
   - Customize notification templates
   - Add business-specific validation rules

This development environment provides a complete, self-contained testing platform that mirrors the production system without requiring any external dependencies.