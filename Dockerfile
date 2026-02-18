# Cross-platform Dockerfile optimized for Raspberry Pi
# Uses Python 3.10 slim base image (ARM-compatible)

ARG TARGETPLATFORM
FROM python:3.10-slim-buster AS base

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY system_monitor.py .
COPY utils.py .
COPY config.py .

# Add any other local files/modules as needed

# Default command
CMD ["python", "system_monitor.py"]

# For cross-platform builds, use:
# docker buildx build --platform linux/amd64,linux/arm64 -t system_monitor .
