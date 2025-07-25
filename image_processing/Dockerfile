FROM n8nio/n8n:1.68.0

USER root

# Install system dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    python3-dev \
    build-base \
    jpeg-dev \
    zlib-dev \
    freetype-dev \
    lcms2-dev \
    openjpeg-dev \
    tiff-dev \
    tk-dev \
    tcl-dev \
    harfbuzz-dev \
    fribidi-dev \
    libimagequant-dev \
    libxcb-dev \
    libpng-dev \
    exiftool \
    git \
    openjdk11-jre \
    openjdk11-jdk

# Create Python requirements file
COPY requirements.txt /tmp/requirements.txt

# Install Python packages
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Set Java environment for jpype
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk

# Create directories for our application
RUN mkdir -p /scripts /config /templates /assets /data

# Set permissions for node user
RUN chown -R node:node /scripts /config /templates /assets /data

USER node

# Copy configuration and scripts
COPY --chown=node:node scripts/ /scripts/
COPY --chown=node:node config/ /config/
COPY --chown=node:node templates/ /templates/
COPY --chown=node:node assets/ /assets/

# Make scripts executable
USER root
RUN chmod +x /scripts/*.py
USER node

WORKDIR /home/node

# Expose additional port for web server
EXPOSE 5678 8080