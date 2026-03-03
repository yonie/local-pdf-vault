#!/usr/bin/env python3
"""
LocalPDFVault - Main Entry Point

A privacy-focused PDF indexing and search application.
All data stays on your computer - never sent to external services.

Author: yonie (https://github.com/yonie)
"""

import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import after logging is configured
from src.web import create_app
from src.config import settings


def main():
    """Main entry point for the application."""
    app = create_app()
    
    # Suppress Flask/Werkzeug request logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    
    logger.info(f"Starting LocalPDFVault on http://{settings.web_host}:{settings.web_port}")
    logger.info(f"Vault directory: {settings.scan_directory}")
    logger.info(f"Ollama URL: {settings.ollama_url}")
    logger.info(f"Model: {settings.ollama_model}")
    
    app.run(
        host=settings.web_host,
        port=settings.web_port,
        debug=settings.debug
    )


if __name__ == '__main__':
    main()