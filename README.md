# PDF Scanner with Ollama Integration

A command-line tool that recursively scans directories for PDF files and uses local Ollama vision models to analyze document content by converting PDF pages to images. Extracts structured metadata including subject, summary, dates, sender/recipient information, document type, and automatically generated categorization tags. Outputs clean JSON data for easy integration with other systems.

## Features

- **Directory Scanner**: Recursively scan directories and subfolders for PDF files only
- **Ollama Integration**: Connect to local Ollama server with configurable host, port, and model
- **Model Configuration**: Default to qwen3-vl:30b-a3b-instruct-q4_K_M but fully configurable
- **File Processing**: Generate SHA-256 hash and extract text content from PDFs
- **Vision Analysis**: Use Ollama vision models to analyze PDFs and extract metadata
- **Metadata Extraction**: Extract filename, file hash, subject, summary, date, sender, recipient, document type, and categorization tags
- **JSON Output**: Clean, valid JSON output to console
- **Robust Error Handling**: Gracefully handle corrupted PDFs, API failures, and other edge cases
- **Comprehensive Logging**: Track progress and issues with detailed logging

## Installation

1. **Clone or download the application files**

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Ollama**:
   - Download from [https://ollama.ai](https://ollama.ai)
   - Install a vision model:
     ```bash
     ollama pull qwen3-vl:30b-a3b-instruct-q4_K_M
     ```

4. **Start Ollama server**:
   ```bash
   ollama serve
   ```

## Usage

### Basic Usage

```bash
python pdfscanner.py --directory /path/to/pdfs
```

### Advanced Usage

```bash
# Custom Ollama server settings
python pdfscanner.py --directory /path/to/pdfs --host 192.168.1.100 --port 11434 --model qwen3-vl:30b-a3b-instruct-q4_K_M

# Verbose logging
python pdfscanner.py --directory /path/to/pdfs --verbose
```

### Command Line Arguments

- `--directory` (required): Directory path to scan for PDF files
- `--host` (optional): Ollama server host (default: localhost)
- `--port` (optional): Ollama server port (default: 11434)
- `--model` (optional): Ollama model name (default: qwen3-vl:30b-a3b-instruct-q4_K_M)
- `--verbose` (optional): Enable verbose logging

## Example Output

```json
[
  {
    "filename": "/path/to/document.pdf",
    "file_hash": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
    "subject": "Quarterly Financial Report Q3 2024",
    "summary": "This document contains the quarterly financial report for Q3 2024, including revenue analysis, expense breakdown, and profit margins compared to previous quarters.",
    "date": "2024-10-15",
    "sender": "Finance Department",
    "recipient": "Executive Committee",
    "document_type": "report",
    "tags": ["finance", "quarterly", "report", "revenue", "q3"],
    "error": null
  },
  {
    "filename": "/path/to/invoice.pdf",
    "file_hash": "f9e8d7c6b5a49382716059483726150483627150483627150483",
    "subject": "Invoice #2024-1056",
    "summary": "Invoice for professional services rendered in September 2024, including hourly rates, total hours worked, and payment terms.",
    "date": "2024-09-30",
    "sender": "ABC Consulting LLC",
    "recipient": "XYZ Corporation",
    "document_type": "invoice",
    "tags": ["invoice", "consulting", "services", "payment"],
    "error": null
  }
]
```

## Dependencies

- `requests>=2.31.0`: HTTP library for Ollama API calls
- `PyPDF2>=3.0.1`: PDF metadata extraction
- `pymupdf>=1.23.8`: PDF to image conversion for vision analysis

## Error Handling

The application includes comprehensive error handling for:

- Corrupted or unreadable PDF files
- Ollama server connection failures
- Vision model processing errors
- File system access issues
- Network timeouts

Each processed file includes an `error` field that will be populated if processing failed, while successful files have `error: null`.

## Technical Details

### Architecture

The application follows a modular architecture:

1. **PDFScanner Class**: Main orchestrator that handles the entire workflow
2. **Directory Scanning**: Recursive scanning using `os.walk()`
3. **File Hashing**: SHA-256 hash generation for file integrity
4. **Metadata Extraction**: Using PyPDF2 for PDF metadata and Ollama for advanced analysis
5. **Vision Analysis**: Converting individual PDF pages to high-quality PNG images for Ollama vision model analysis
6. **JSON Output**: Clean JSON serialization with proper formatting

### Ollama Integration

The application connects to Ollama's REST API:
- Endpoint: `http://host:port/api/generate`
- Model: Vision-capable models like qwen3-vl or llama3.2-vision
- Payload: Includes images, text prompt, and generation options
- Timeout: 60 seconds for model processing

### Privacy and Security

- All processing happens locally using Ollama models
- No data is sent to external services
- Files remain on your local system
- SHA-256 hashing ensures file integrity tracking

## Troubleshooting

### Common Issues

1. **Ollama Connection Failed**
   - Ensure Ollama server is running: `ollama serve`
   - Check host and port settings
   - Verify firewall settings

2. **No Vision Model Found**
   - Install a vision model: `ollama pull qwen3-vl:30b-a3b-instruct-q4_K_M`
   - List available models: `ollama list`

3. **PDF Processing Errors**
   - Check if PDF files are corrupted
   - Ensure sufficient disk space
   - Verify file permissions

4. **Missing Dependencies**
   - Install requirements: `pip install -r requirements.txt`
   - Check Python version compatibility

### Logging

Enable verbose logging with `--verbose` flag to see detailed processing information:

```
2025-12-05 08:00:01 - pdfscanner - INFO - Starting PDF scan of directory: /path/to/pdfs
2025-12-05 08:00:02 - pdfscanner - INFO - Found 5 PDF files in /path/to/pdfs
2025-12-05 08:00:03 - pdfscanner - INFO - Successfully connected to Ollama at http://localhost:11434
2025-12-05 08:00:04 - pdfscanner - INFO - Processing: /path/to/pdfs/document1.pdf
```

## License

MIT License - see LICENSE file for details, or feel free to use this code for educational and practical purposes with attribution.

## Author

Created by Kilo Code - A highly skilled software engineer focused on practical automation solutions.