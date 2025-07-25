# ML Processing Container - Ubuntu base for PyTorch/rembg compatibility
FROM python:3.11-slim

# Install system dependencies for ML libraries
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libglib2.0-0 \
    libgtk-3-0 \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Copy requirements for ML processing
COPY requirements.ml.txt /tmp/requirements.ml.txt

# Install ML-specific Python packages
RUN pip install --no-cache-dir -r /tmp/requirements.ml.txt

# Create directories
RUN mkdir -p /scripts /config /data /assets

# Copy ML processing scripts
COPY scripts/background_removal.py /scripts/
COPY scripts/ml_server.py /scripts/
COPY scripts/utils/ /scripts/utils/

# Set permissions
RUN chmod +x /scripts/*.py

# Set working directory to scripts so imports work
WORKDIR /scripts

# Expose port for ML API
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run ML processing server with explicit Python path and binding
CMD ["python3", "ml_server.py"]