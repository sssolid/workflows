# ===== docker/Dockerfile.ml =====
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
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Copy requirements for ML processing
COPY requirements.ml.txt /tmp/requirements.ml.txt

# Install ML-specific Python packages
RUN pip install --no-cache-dir -r /tmp/requirements.ml.txt

# Create directories
RUN mkdir -p /app/src /config /data /assets

# Copy clean architecture source
COPY src/ /app/src/

# Set Python path
ENV PYTHONPATH=/app

# Set permissions
RUN chmod +x /app/src/services/*.py

# Expose port for ML API
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run ML processing server
CMD ["python", "-m", "src.services.ml_server"]