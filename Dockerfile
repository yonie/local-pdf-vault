# Use an official Python slim image for a smaller footprint
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV WEB_PORT=4337
ENV OLLAMA_HOST=host.docker.internal

# Set work directory
WORKDIR /app

# Install system dependencies for PDF processing (if any needed by pymupdf/fitz)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create directory for PDF storage (to be mounted)
RUN mkdir -p /data/pdfs

# Expose the web interface port
EXPOSE 4337

# Run the web application
CMD ["python", "webapp.py"]
