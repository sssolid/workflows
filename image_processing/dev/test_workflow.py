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
