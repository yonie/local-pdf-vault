#!/usr/bin/env python3
"""
MCP Server for LocalPDFVault.

Provides standard MCP (Model Context Protocol) interface via stdio transport.
"""

import asyncio
import importlib.util
import json
import logging
import os
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

_base = os.path.dirname(os.path.abspath(__file__))

def _load_module_direct(name: str, path: str, deps: dict = None):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    if deps:
        for dep_name, dep_module in deps.items():
            setattr(module, dep_name, dep_module)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

config = _load_module_direct("pdfvault_config", os.path.join(_base, "src", "config.py"))
database = _load_module_direct("pdfvault_database", os.path.join(_base, "src", "database", "__init__.py"))

settings = config.Settings()
DatabaseManager = database.DatabaseManager
app = Server("local-pdf-vault")
db: DatabaseManager | None = None


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_documents",
            description="Search for PDF documents by content, metadata, or text. Returns matching documents with metadata.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query. Searches in document text, subject, summary, sender, recipient, and tags."
                    },
                    "document_type": {
                        "type": "string",
                        "description": "Filter by document type (e.g., 'invoice', 'contract', 'letter')"
                    },
                    "sender": {
                        "type": "string",
                        "description": "Filter by sender name"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_document",
            description="Retrieve detailed information about a specific document by its hash, including full extracted text.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_hash": {
                        "type": "string",
                        "description": "The SHA-256 hash of the document"
                    }
                },
                "required": ["file_hash"]
            }
        ),
        Tool(
            name="list_document_types",
            description="List all document types in the database with counts.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_stats",
            description="Get statistics about the document database.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_indexing_status",
            description="Get the current indexing status (progress, files processed, errors).",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, any]) -> list[TextContent]:
    if db is None:
        return [TextContent(type="text", text="Error: Database not initialized")]
    
    try:
        if name == "search_documents":
            return await handle_search_documents(arguments)
        elif name == "get_document":
            return await handle_get_document(arguments)
        elif name == "list_document_types":
            return await handle_list_document_types()
        elif name == "get_stats":
            return await handle_get_stats()
        elif name == "get_indexing_status":
            return await handle_get_indexing_status()
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def handle_search_documents(arguments: dict) -> list[TextContent]:
    query = arguments.get("query", "")
    document_type = arguments.get("document_type")
    sender = arguments.get("sender")
    limit = min(arguments.get("limit", 10), 50)
    
    if not query:
        return [TextContent(type="text", text="Error: 'query' parameter is required")]
    
    result = db.search_metadata(
        query=query,
        limit=limit,
        document_type=document_type,
        sender=sender
    )
    
    documents = []
    for doc in result.get("results", [])[:limit]:
        documents.append({
            "file_hash": doc.get("file_hash"),
            "filename": doc.get("filename"),
            "subject": doc.get("subject"),
            "summary": doc.get("summary"),
            "date": doc.get("date"),
            "sender": doc.get("sender"),
            "recipient": doc.get("recipient"),
            "document_type": doc.get("document_type"),
            "tags": doc.get("tags", [])
        })
    
    response_text = f"Found {result.get('total', 0)} documents matching '{query}'"
    if documents:
        response_text += f". Showing {len(documents)} results:\n\n"
        for i, doc in enumerate(documents, 1):
            response_text += f"{i}. **{doc['filename']}**\n"
            if doc.get("subject"):
                response_text += f"   Subject: {doc['subject']}\n"
            if doc.get("date"):
                response_text += f"   Date: {doc['date']}\n"
            if doc.get("sender"):
                response_text += f"   From: {doc['sender']}\n"
            if doc.get("document_type"):
                response_text += f"   Type: {doc['document_type']}\n"
            response_text += f"   Hash: {doc['file_hash']}\n\n"
    
    return [TextContent(type="text", text=response_text)]


async def handle_get_document(arguments: dict) -> list[TextContent]:
    file_hash = arguments.get("file_hash")
    
    if not file_hash:
        return [TextContent(type="text", text="Error: 'file_hash' parameter is required")]
    
    doc = db.get_metadata(file_hash)
    
    if not doc:
        return [TextContent(type="text", text=f"Document not found with hash: {file_hash}")]
    
    response_text = f"**{doc['filename']}**\n\n"
    if doc.get("subject"):
        response_text += f"Subject: {doc['subject']}\n"
    if doc.get("date"):
        response_text += f"Date: {doc['date']}\n"
    if doc.get("sender"):
        response_text += f"From: {doc['sender']}\n"
    if doc.get("recipient"):
        response_text += f"To: {doc['recipient']}\n"
    if doc.get("document_type"):
        response_text += f"Type: {doc['document_type']}\n"
    if doc.get("tags"):
        response_text += f"Tags: {', '.join(doc['tags'])}\n"
    
    response_text += f"\nHash: {doc['file_hash']}\n"
    response_text += f"Path: {doc.get('file_path', 'N/A')}\n"
    
    if doc.get("summary"):
        response_text += f"\n**Summary:**\n{doc['summary']}\n"
    
    if doc.get("full_text"):
        text = doc["full_text"]
        if len(text) > 5000:
            text = text[:5000] + "\n\n... (text truncated, use file_hash to access full document)"
        response_text += f"\n**Extracted Text:**\n{text}\n"
    
    return [TextContent(type="text", text=response_text)]


async def handle_list_document_types() -> list[TextContent]:
    types = db.get_document_types()
    
    response_text = f"Found {len(types)} document types:\n\n"
    for doc_type in sorted(types):
        response_text += f"- {doc_type}\n"
    
    return [TextContent(type="text", text=response_text)]


async def handle_get_stats() -> list[TextContent]:
    stats = db.get_stats()
    
    response_text = "Document Database Statistics:\n\n"
    response_text += f"Total documents: {stats.get('total', 0)}\n"
    response_text += f"Documents with errors: {stats.get('errors', 0)}\n"
    response_text += "\nTop document types:\n"
    
    by_type = stats.get("by_type", {})
    sorted_types = sorted(by_type.items(), key=lambda x: x[1], reverse=True)[:10]
    for doc_type, count in sorted_types:
        response_text += f"  {doc_type}: {count}\n"
    
    return [TextContent(type="text", text=response_text)]


async def handle_get_indexing_status() -> list[TextContent]:
    status = db.get_indexing_status()
    
    response_text = "Indexing Status:\n\n"
    response_text += f"Running: {status.get('is_running', False)}\n"
    response_text += f"Current file: {status.get('current_file', 'N/A')}\n"
    response_text += f"Progress: {status.get('processed', 0)}/{status.get('total', 0)}\n"
    response_text += f"Skipped: {status.get('skipped', 0)}\n"
    response_text += f"Errors: {status.get('errors', 0)}\n"
    response_text += f"Last directory: {status.get('last_directory', 'N/A')}\n"
    response_text += f"Stop requested: {status.get('stop_requested', False)}\n"
    
    return [TextContent(type="text", text=response_text)]


async def main():
    global db
    
    db = DatabaseManager(settings.database_path)
    logger.info(f"Connected to database: {settings.database_path}")
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())