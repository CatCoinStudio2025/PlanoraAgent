# Image Processing Service Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for PIL/Pillow
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY image_service/ ./image_service/
COPY setup.py .
COPY README.md .

# Install package
RUN pip install -e .

# Create workspace directory
RUN mkdir -p /app/workspace/PlanoraAgent/image_store
RUN mkdir -p /app/workspace/PlanoraAgent/thumbnails

# Set environment variables
ENV PYTHONPATH=/app
ENV IMAGE_SERVICE_WORKSPACE=/app/workspace
ENV IMAGE_SERVICE_HOST=0.0.0.0
ENV IMAGE_SERVICE_PORT=8000

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run FastAPI server
CMD ["uvicorn", "image_service.api:app", "--host", "0.0.0.0", "--port", "8000"]