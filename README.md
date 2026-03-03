# LocalPDFVault 🔒📄

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Appliance-blue.svg)](https://www.docker.com/)
[![Ollama](https://img.shields.io/badge/Ollama-AI-orange.svg)](https://ollama.ai)

**Privacy-focused AI-powered local PDF search appliance.**

LocalPDFVault is a self-hosted "Vault" application that uses local AI vision models (via Ollama) to automatically index and search your PDF documents. It runs as a secure Docker container with read-only access to your archive, ensuring your documents are never modified or sent to the cloud.

![Screenshot](screenshot.png)

---

## ✨ Features

### 🌐 Web Interface
- **Modern Search UI** - Clean, responsive design for all devices
- **Instant Search** - Real-time fuzzy search with intelligent relevance ranking
- **PDF Preview** - Built-in viewer with zoom, pan, and page navigation
- **Turbo Sync** - High-performance "Smart Sync" pipeline rescans 1,000+ files in < 2 seconds
- **One-Button Update** - Keep your index in sync with your files with a single click
- **Dark Mode** - Professional, eye-friendly interface

### 🤖 AI Intelligence
- **Smart Sync Technology** - Uses parallel directory scanning and stat-based caching to detect changes instantly
- **Vision Model Analysis** - "Reads" your PDFs using local Ollama models
- **Smart Metadata** - Extracts subject, summary, dates, sender/recipient, and type
- **Auto-Tagging** - Generates relevant categorization tags automatically
- **100% Private** - All processing happens locally on your hardware

### 🔒 Security & Safety
- **Docker Isolation** - Runs in a sealed environment
- **Read-Only Vault** - Mounts your archive as `ro`, making it physically impossible for the app to delete or modify your files
- **Zero Telemetry** - No tracking, no phone-home, no cloud dependencies

---

## 🚀 Quick Start (Docker)

### Prerequisites

1.  **Ollama** - [Install Ollama](https://ollama.ai) (must be running on your host machine)
2.  **Docker & Docker Compose** - [Install Docker](https://docs.docker.com/get-docker/)

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/yonie/local-pdf-vault.git
cd local-pdf-vault

# Download the AI vision model
ollama pull qwen3-vl:30b-a3b-instruct
```

### 2. Configure your Vault

Edit `docker-compose.yml` to point to your PDF collection. You must map your local folder to `/data/pdfs:ro` inside the container.

**Examples for different Operating Systems:**

- **Windows**: `- D:\Documents:/data/pdfs:ro` or `- C:\Users\Name\Documents:/data/pdfs:ro`
- **macOS**: `- /Users/name/Documents/PDFs:/data/pdfs:ro`
- **Linux**: `- /home/name/documents:/data/pdfs:ro` or `- /mnt/nas/archive:/data/pdfs:ro`

```yaml
    volumes:
      - ./pdfscanner.db:/app/pdfscanner.db
      - /path/to/your/pdfs:/data/pdfs:ro  # Replace with your actual host path
```

### 3. Launch


```bash
docker-compose up -d
```

Open your browser to **http://localhost:4337**

### 4. Indexing

1.  Click **"⚙️ Manage Index"**
2.  Click **"🔄 Update Index"**
3.  The AI will now begin analyzing your documents. Results will appear in the search view as they are processed.

---

## 📖 How It Works

1.  **📁 Vault**: Mounts your host directory to `/data/pdfs` inside the container.
2.  **🤖 Analyze**: Local Ollama vision model "sees" the document pages.
3.  **📝 Extract**: AI extracts rich metadata (subject, summary, dates, tags).
4.  **💾 Index**: Searchable metadata is stored in a local SQLite database.
5.  **🔍 Search**: You get instant, tiered search results across your entire collection.

---

## ⚙️ Configuration

### Supported Models

Popular choices for the `OLLAMA_MODEL` environment variable:

| Model | Size | Performance | Accuracy |
|-------|------|-------------|----------|
| `qwen3-vl:30b-a3b-instruct` | ~17GB | Fast | Excellent ⭐ |
| `llama3.2-vision:11b` | ~7GB | Very Fast | Good |
| `llava:13b` | ~8GB | Fast | Good |

### Environment Variables

Configure these in `docker-compose.yml`:
- `OLLAMA_HOST`: Set to `host.docker.internal` to reach your host's Ollama.
- `OLLAMA_MODEL`: Which vision model to use.
- `SCAN_DIRECTORY`: Internal path to scan (default: `/data/pdfs`).
- `MAX_PAGES_PER_END`: How many pages to scan for large PDFs (default: `3`).
- `MAX_PARALLEL_HASHING`: Number of CPU workers for file hashing (default: `16`).
- `MAX_PARALLEL_SCANNING`: Number of I/O workers for directory discovery (default: `128`).

---

## 🔧 Troubleshooting

### Connection to Ollama Failed
Ensure your host's Ollama is listening on all interfaces. On Windows/Linux, set the environment variable `OLLAMA_HOST=0.0.0.0` for the Ollama service.

### Vault Path Not Found
Verify that your host path in `docker-compose.yml` is absolute and correctly formatted. The app expects your PDFs to be mapped specifically to `/data/pdfs` inside the container.

---

## 📄 License
MIT License - Free for personal and commercial use.

**⭐ If you find this useful, please star the repository!**

---

## 🤖 MCP Integration (Model Context Protocol)

LocalPDFVault includes an **MCP server** (`mcp_server.py`) for AI assistants to search and read your documents. This allows any MCP-compatible AI tool to access your document vault.

### Available Tools

| Tool | Description |
|------|-------------|
| `search_documents` | Search PDFs by content, metadata, or full text |
| `get_document` | Retrieve document details with full extracted text |
| `list_document_types` | List all document types in database |
| `get_stats` | Get database statistics |
| `get_indexing_status` | Get current indexing progress |

### Configuring MCP Clients

The MCP server uses **stdio transport** - it runs as a local process and communicates via stdin/stdout.

#### OpenCode / Claude Desktop / Other MCP Clients

Add to your MCP configuration (e.g., `~/.config/opencode/opencode.json`):

```json
{
  "mcp": {
    "local-pdf-vault": {
      "command": ["python", "/path/to/local-pdf-vault/mcp_server.py"],
      "type": "local",
      "enabled": true,
      "environment": {
        "DATABASE_PATH": "/path/to/local-pdf-vault/pdfscanner.db"
      }
    }
  }
}
```

Replace `/path/to/local-pdf-vault` with the actual path to your LocalPDFVault installation.

### Using with AI Assistants

Once configured, you can ask your AI assistant:

- "Search my PDFs for invoices from last year"
- "Find all contracts mentioning 'termination'"
- "What documents does my vault contain about taxes?"
- "Read the full text of document [hash]"

The AI assistant will use the MCP tools to search your document vault and retrieve content.

---
