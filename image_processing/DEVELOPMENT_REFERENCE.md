# Crown Image Processing - Development Quick Reference

## 🚀 Essential Commands

```bash
# Setup (run once)
chmod +x dev/setup_dev_environment.sh
./dev/setup_dev_environment.sh

# Daily workflow
make -f Makefile.dev dev-start    # Start everything
make -f Makefile.dev dev-logs     # Watch logs
make -f Makefile.dev dev-stop     # Stop everything
make -f Makefile.dev dev-clean    # Reset everything
```

## 🌐 Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| **Main Dashboard** | http://localhost:8080 | None |
| **n8n Workflows** | http://localhost:5678 | admin/admin |
| **Mock Teams** | http://localhost:3000 | None |
| **ML Processor API** | http://localhost:8001/health | None |
| **File Monitor API** | http://localhost:8002/health | None |

## 🧪 Quick Tests

```bash
# Test all services
python3 dev/test_workflow.py

# Add test images (simulates file drop)
cp dev/sample_images/*.jpg dev/test_data/input/

# Check part mapping
curl "http://localhost:8080/api/part-suggestions?q=J123"

# View system status
curl "http://localhost:8080/api/status" | python -m json.tool

# Reset file monitor
docker-compose -f docker-compose.dev.yml exec web_server python -m src.cli reset --confirm
```

## 📁 Test Images Included

| Filename | Tests | Expected Result |
|----------|-------|----------------|
| `J1234567_detail.jpg` | Direct match | High confidence → J1234567 |
| `OLD12345_1.jpg` | Interchange | Medium confidence → 12345 |
| `unknown_part_123.jpg` | Manual review | Low confidence → Review needed |
| `J9876543_transmission_mount.psd` | PSD processing | Direct to formats |

## 🗄️ Mock Database

**Sample Parts Available:**
- J1234567 (Fuel Tank Skid Plate)
- A5551234 (Air Filter)  
- 12345 (Oil Pan)
- 67890 (Water Pump)
- J9876543 (Transmission Mount)
- A1111111 (Brake Pad Set)
- B2222222 (Shock Absorber)
- C3333333 (CV Joint)

**Interchange Mappings:**
- OLD12345 → 12345
- LEGACY67890 → 67890
- J1234567A → J1234567

## 🐛 Troubleshooting

**Services won't start:**
```bash
docker system prune -f
docker-compose -f docker-compose.dev.yml up --build -d
```

**Port conflicts:**
```bash
lsof -i :8080  # Check what's using port 8080
```

**ML models slow:**
```bash
# Pre-download in background
docker-compose -f docker-compose.dev.yml exec ml_processor python -c "from rembg import new_session; new_session('isnet-general-use')"
```

**Database issues:**
```bash
# Check mock database
make -f Makefile.dev dev-db
```

## 🔄 Development Workflow

1. **Start**: `make -f Makefile.dev dev-start`
2. **Add test images**: Copy to `dev/test_data/input/`
3. **Monitor**: http://localhost:8080
4. **Test features**: Upload, review, edit metadata, approve
5. **Check logs**: `make -f Makefile.dev dev-logs`
6. **Stop**: `make -f Makefile.dev dev-stop`

## 📊 Key Metrics to Verify

- [ ] File discovery working (new files appear in dashboard)
- [ ] Part mapping showing confidence scores
- [ ] Manual override saves changes
- [ ] Background removal processes (may be slow)
- [ ] Teams notifications logged
- [ ] n8n can connect to all services

**Perfect for testing without FileMaker, network drives, or production environment!**