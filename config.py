import os

# LocalPDFVault Configuration File
# Edit these values or use environment variables to customize your setup

# Web Interface Configuration
WEB_HOST = os.getenv('WEB_HOST', '0.0.0.0')  # Bind to all interfaces (0.0.0.0) or localhost
WEB_PORT = int(os.getenv('WEB_PORT', 4337))    # Port for the web interface

# Ollama Configuration
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'localhost')  # Ollama server host
OLLAMA_PORT = int(os.getenv('OLLAMA_PORT', 11434))     # Ollama server port
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen3-vl:30b-a3b-instruct')  # Vision model to use

# PDF Processing Configuration
SCAN_DIRECTORY = os.getenv('SCAN_DIRECTORY', '/data/pdfs')
MAX_PAGES_PER_END = int(os.getenv('MAX_PAGES_PER_END', 3))  # Number of pages to scan from start and end of large PDFs
MAX_PARALLEL_SCANNING = int(os.getenv('MAX_PARALLEL_SCANNING', 128))  # Number of parallel threads for directory scanning
MAX_PARALLEL_HASHING = int(os.getenv('MAX_PARALLEL_HASHING', 16))  # Number of parallel hashing jobs
# Set MAX_PAGES_PER_END to 0 to scan all pages (original behavior) - WARNING: may cause issues with large documents

# Vision Analysis Retry Configuration
MAX_VISION_RETRIES = int(os.getenv('MAX_VISION_RETRIES', 3))  # Number of retry attempts with different page selections
# Retry strategies: 0=first+last pages, 1=middle pages, 2=distributed pages, 3=first 6 pages
