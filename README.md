# LocalPDFVault 🔒📄

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-2.3+-green.svg)](https://flask.palletsprojects.com/)
[![Ollama](https://img.shields.io/badge/Ollama-AI-orange.svg)](https://ollama.ai)

**Privacy-focused AI-powered local PDF search with beautiful web interface**

LocalPDFVault is a self-hosted web application that uses local AI vision models (via Ollama) to automatically index and search your PDF documents. With an intuitive web interface and powerful search capabilities, you can organize and find your documents instantly - all while keeping your data 100% private on your own machine.

![Screenshot](screenshot.png)

---

## ✨ Features

### 🌐 Web Interface (Primary)
- **Beautiful Modern UI** - Clean, responsive design that works on desktop, tablet, and mobile
- **Instant Search** - Real-time fuzzy search with intelligent relevance ranking
- **PDF Preview** - Built-in viewer with zoom, pan, and page navigation
- **Live Progress** - Watch AI analyze your documents in real-time
- **Easy Management** - One-click folder indexing from the web UI
- **Recent Searches** - Quick access to your search history
- **Dark Mode** - Eye-friendly interface for long viewing sessions

### 🤖 AI-Powered Intelligence
- **Vision Model Analysis** - Uses Ollama's local vision models to "read" your PDFs
- **Smart Metadata** - Automatically extracts subject, summary, dates, sender/recipient, document type
- **Auto-Tagging** - AI generates relevant categorization tags for each document
- **Multi-Language** - Works with documents in any language
- **Configurable Models** - Use any Ollama vision model you prefer

### 🔒 Privacy & Security
- **100% Local** - All processing happens on your machine, nothing sent to the cloud
- **Your Files Stay Put** - PDFs remain in their original locations
- **Open Source** - Full transparency, audit the code yourself
- **No Telemetry** - Zero tracking, analytics, or phone-home features

### ⚡ Performance
- **Fast Search** - SQLite database for instant results from thousands of documents
- **Efficient Indexing** - Smart skip of already-processed files
- **Batch Processing** - Index entire folders with progress tracking
- **Low Resource** - Runs efficiently on modest hardware

---

## 🚀 Quick Start

### Prerequisites

1. **Python 3.8+** - [Download Python](https://www.python.org/downloads/)
2. **Ollama** - [Install Ollama](https://ollama.ai)

### Installation

```bash
# Clone the repository
git clone https://github.com/yonie/local-pdf-vault.git
cd local-pdf-vault

# Install Python dependencies
pip install -r requirements.txt

# Download AI vision model
ollama pull qwen3-vl:30b-a3b-instruct-q4_K_M

# Start Ollama (in a separate terminal)
ollama serve
```

### Launch Web Interface

```bash
# Start the web application
python webapp.py
```

Then open your browser to **http://localhost:4337**

### First Use

1. Click **"⚙️ Manage Index"** button
2. Enter the path to a folder containing PDFs
3. Click **"🔍 Scan Folder"**
4. Watch as AI analyzes your documents!
5. Use the search box to find anything instantly

---

## 📖 How It Works

1. **📁 Scan**: Recursively finds all PDF files in specified folders
2. **🔑 Hash**: Generates SHA-256 hash to detect duplicates
3. **🖼️ Convert**: Converts PDF pages to high-quality images
4. **🤖 Analyze**: Local Ollama vision model "reads" the document
5. **📝 Extract**: AI extracts metadata (subject, summary, dates, sender, recipient, type, tags)
6. **💾 Index**: Stores searchable metadata in local SQLite database
7. **🔍 Search**: Instant fuzzy search with intelligent relevance ranking

### AI Vision Analysis

LocalPDFVault uses vision models that can actually "see" and understand your documents:
- Reads text from scanned documents (OCR capability)
- Understands layout and document structure
- Identifies logos, signatures, and visual elements
- Extracts information from tables and forms
- Works with handwritten notes (model dependent)

---

## 🎯 Web Interface Guide

### Search Features

**Search Syntax:**
- Simple terms: `invoice` or `2024`
- Multiple words: `consulting services` (finds documents with both words)
- Exact phrases: Results with exact phrase matches rank highest

**Relevance Scoring:**
- 🟢 **High** (80-100%) - Exact phrase matches, all terms present
- 🔵 **Medium** (50-79%) - Multiple terms found
- 🟡 **Low** (10-49%) - Partial or fuzzy matches

**Search Scope:**
- Filename
- Subject
- Summary
- Sender/Recipient
- Document type
- All tags

### Document Management

**Indexing:**
- Click "Manage Index" → Enter folder path → Scan
- Progress shows: files processed, skipped, errors
- Already-indexed files are automatically skipped
- Re-scan same folder to pick up new PDFs

**Individual Documents:**
- Click any result to view PDF and metadata
- "📄 Open in New Tab" - view in browser
- "📋 Copy Path" - copy file location
- Re-index option for updated documents

**Database Maintenance:**
- View statistics (total documents, types, errors)
- "🔄 Reset Index" - re-analyze all files with fresh AI
- Database stored as `pdfscanner.db` in project folder

---

## 💻 Command-Line Interface

For automation and scripting, LocalPDFVault includes a CLI:

### Basic CLI Usage

```bash
# Index a directory
python pdfscanner.py --directory /path/to/pdfs

# Custom Ollama settings
python pdfscanner.py --directory /path/to/pdfs \
  --host localhost \
  --port 11434 \
  --model llama3.2-vision

# Enable detailed logging
python pdfscanner.py --directory /path/to/pdfs --verbose
```

### CLI Arguments

- `--directory` (required): Directory path to scan for PDF files
- `--host` (optional): Ollama server host (default: `localhost`)
- `--port` (optional): Ollama server port (default: `11434`)
- `--model` (optional): Ollama model name (default: `qwen3-vl:30b-a3b-instruct-q4_K_M`)
- `--verbose` (optional): Enable verbose logging

### Use Cases for CLI

- **Scheduled Tasks**: Cron jobs or Windows Task Scheduler
- **CI/CD Pipelines**: Automated document processing
- **Batch Operations**: Index multiple folders via script
- **Server Deployments**: Headless environments

---

## ⚙️ Configuration

### Supported Ollama Models

Any vision-capable Ollama model works. Popular choices:

| Model | Size | Performance | Accuracy |
|-------|------|-------------|----------|
| `qwen3-vl:30b-a3b-instruct-q4_K_M` | ~17GB | Fast | Excellent ⭐ |
| `llama3.2-vision:11b` | ~7GB | Very Fast | Good |
| `llama3.2-vision:90b` | ~55GB | Slower | Excellent |
| `llava:13b` | ~8GB | Fast | Good |

Browse more models: [Ollama Library](https://ollama.ai/library?search=vision)

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **CPU** | Dual-core | Quad-core+ |
| **RAM** | 8GB | 16GB+ |
| **Storage** | 5GB free | 20GB+ free |
| **GPU** | Optional | NVIDIA/AMD (faster) |

---

## 📊 Example Metadata

```json
{
  "filename": "/Users/me/Documents/invoice-2024.pdf",
  "file_hash": "a1b2c3d4e5f67890...",
  "subject": "Invoice #2024-1056 - Consulting Services",
  "summary": "Professional services invoice for September 2024, including hourly rates and payment terms.",
  "date": "2024-09-30",
  "sender": "ABC Consulting LLC",
  "recipient": "XYZ Corporation",
  "document_type": "invoice",
  "tags": ["invoice", "consulting", "services", "payment", "2024"],
  "error": null
}
```

---

## 🔧 Troubleshooting

### Ollama Issues

**Connection Failed**
```bash
# Ensure Ollama is running
ollama serve

# Test connection
curl http://localhost:11434/api/tags
```

**Model Not Found**
```bash
# List installed models
ollama list

# Install required model
ollama pull qwen3-vl:30b-a3b-instruct-q4_K_M
```

### Web Interface Issues

**Port Already in Use**
```python
# Edit webapp.py line 331 to change port:
app.run(host='0.0.0.0', port=4338, debug=True)
```

**Can't Access from Other Devices**
- By default, server binds to `0.0.0.0` (all interfaces)
- Check firewall allows port 4337
- Access via: `http://YOUR_IP:4337`

### PDF Processing

**Indexing Errors**
- Check PDF files aren't corrupted
- Verify file permissions (read access)
- Ensure sufficient disk space
- Check Ollama logs for vision model issues

**Slow Performance**
- Use smaller/faster Ollama model
- Close other resource-intensive apps
- Consider GPU acceleration for Ollama
- Index smaller batches at a time

---

## 🏗️ Technical Architecture

### System Components

```
┌─────────────────────────────────────────┐
│         Web Browser (You)               │
│    http://localhost:4337                │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│       Flask Web Server (webapp.py)      │
│  • Serves HTML/CSS/JS                   │
│  • API endpoints                        │
│  • Background indexing                  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│    PDF Scanner Engine (pdfscanner.py)   │
│  • Directory scanning                   │
│  • PDF processing                       │
│  • Vision model integration             │
└──────────────┬──────────┬───────────────┘
               │          │
               ▼          ▼
         ┌─────────┐  ┌──────────────┐
         │ SQLite  │  │ Ollama API   │
         │Database │  │ (localhost)  │
         └─────────┘  └──────────────┘
```

### Database Schema

**pdf_metadata table:**
- `file_hash` (PRIMARY KEY) - SHA-256 hash
- `filename` - Full file path
- `subject` - Document title/topic
- `summary` - Brief content summary
- `date` - Document date (YYYY-MM-DD)
- `sender` - From information
- `recipient` - To information
- `document_type` - Category (invoice, contract, etc.)
- `tags` - JSON array of tags
- `error` - Error message if processing failed
- `last_updated` - Timestamp

**Search Algorithm:**
- Tiered relevance scoring (exact phrase > all terms > partial > fuzzy)
- Fuzzy matching for typo tolerance
- Multi-field search across all metadata
- Results sorted by relevance score

---

## 📦 Dependencies

```
requests>=2.31.0      # Ollama API communication
PyPDF2>=3.0.1         # PDF metadata extraction
pymupdf>=1.23.8       # PDF to image conversion
flask>=2.3.0          # Web framework
```

See [`requirements.txt`](requirements.txt) for complete list.

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development setup
- Code style guidelines
- Testing procedures
- Pull request process

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

Free for personal and commercial use with attribution.

---

## 👤 Author

**[@yonie](https://github.com/yonie)**

*Developed with AI assistance*

---

## 🙏 Acknowledgments

- [Ollama](https://ollama.ai) - Local AI model runtime
- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF processing library
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [PDF.js](https://mozilla.github.io/pdf.js/) - Browser PDF rendering

---

## 🔗 Links

- [🐛 Report Bug](https://github.com/yonie/local-pdf-vault/issues)
- [💡 Request Feature](https://github.com/yonie/local-pdf-vault/issues)
- [💬 Discussions](https://github.com/yonie/local-pdf-vault/discussions)

---

**⭐ If you find this useful, please star the repository!**