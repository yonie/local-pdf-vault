"""
MCP (Model Context Protocol) endpoint for AI assistant integration.

Provides read-only access to the document search system.
"""

import logging
from flask import Blueprint, request, jsonify

from .. import get_db
from ...config import settings

logger = logging.getLogger(__name__)

mcp_bp = Blueprint('mcp', __name__, url_prefix='/mcp')


# MCP Tool Definitions
MCP_TOOLS = [
    {
        "name": "search_documents",
        "description": "Search for PDF documents by content, metadata, or text. Returns matching documents with metadata.",
        "inputSchema": {
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
    },
    {
        "name": "get_document",
        "description": "Retrieve detailed information about a specific document by its hash, including full extracted text.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_hash": {
                    "type": "string",
                    "description": "The SHA-256 hash of the document"
                }
            },
            "required": ["file_hash"]
        }
    },
    {
        "name": "list_document_types",
        "description": "List all document types in the database with counts.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_stats",
        "description": "Get statistics about the document database.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


@mcp_bp.route('/tools/list', methods=['GET', 'POST'])
def list_tools():
    """List available MCP tools."""
    return jsonify({
        "tools": MCP_TOOLS
    })


@mcp_bp.route('/tools/call', methods=['POST'])
def call_tool():
    """Execute an MCP tool call."""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No JSON body provided"}), 400
    
    tool_name = data.get('name')
    arguments = data.get('arguments', {})
    
    if not tool_name:
        return jsonify({"error": "Missing 'name' field"}), 400
    
    db = get_db()
    
    try:
        if tool_name == 'search_documents':
            return handle_search_documents(db, arguments)
        elif tool_name == 'get_document':
            return handle_get_document(db, arguments)
        elif tool_name == 'list_document_types':
            return handle_list_document_types(db)
        elif tool_name == 'get_stats':
            return handle_get_stats(db)
        else:
            return jsonify({"error": f"Unknown tool: {tool_name}"}), 404
    except Exception as e:
        logger.error(f"Error executing MCP tool {tool_name}: {e}")
        return jsonify({"error": str(e)}), 500


def handle_search_documents(db, arguments):
    """Handle search_documents tool."""
    query = arguments.get('query', '')
    document_type = arguments.get('document_type')
    sender = arguments.get('sender')
    limit = min(arguments.get('limit', 10), 50)  # Cap at 50
    
    if not query:
        return jsonify({
            "content": [{
                "type": "text",
                "text": "Error: 'query' parameter is required"
            }],
            "isError": True
        })
    
    result = db.search_metadata(
        query=query,
        limit=limit,
        document_type=document_type,
        sender=sender
    )
    
    # Format results for MCP
    documents = []
    for doc in result.get('results', [])[:limit]:
        documents.append({
            "file_hash": doc.get('file_hash'),
            "filename": doc.get('filename'),
            "subject": doc.get('subject'),
            "summary": doc.get('summary'),
            "date": doc.get('date'),
            "sender": doc.get('sender'),
            "recipient": doc.get('recipient'),
            "document_type": doc.get('document_type'),
            "tags": doc.get('tags', [])
        })
    
    response_text = f"Found {result.get('total', 0)} documents matching '{query}'"
    if documents:
        response_text += f". Showing {len(documents)} results:\n\n"
        for i, doc in enumerate(documents, 1):
            response_text += f"{i}. **{doc['filename']}**\n"
            if doc.get('subject'):
                response_text += f"   Subject: {doc['subject']}\n"
            if doc.get('date'):
                response_text += f"   Date: {doc['date']}\n"
            if doc.get('sender'):
                response_text += f"   From: {doc['sender']}\n"
            if doc.get('document_type'):
                response_text += f"   Type: {doc['document_type']}\n"
            response_text += f"   Hash: {doc['file_hash']}\n\n"
    
    return jsonify({
        "content": [{
            "type": "text",
            "text": response_text
        }],
        "isError": False
    })


def handle_get_document(db, arguments):
    """Handle get_document tool."""
    file_hash = arguments.get('file_hash')
    
    if not file_hash:
        return jsonify({
            "content": [{
                "type": "text",
                "text": "Error: 'file_hash' parameter is required"
            }],
            "isError": True
        })
    
    doc = db.get_metadata(file_hash)
    
    if not doc:
        return jsonify({
            "content": [{
                "type": "text",
                "text": f"Document not found with hash: {file_hash}"
            }],
            "isError": True
        })
    
    response_text = f"**{doc['filename']}**\n\n"
    if doc.get('subject'):
        response_text += f"Subject: {doc['subject']}\n"
    if doc.get('date'):
        response_text += f"Date: {doc['date']}\n"
    if doc.get('sender'):
        response_text += f"From: {doc['sender']}\n"
    if doc.get('recipient'):
        response_text += f"To: {doc['recipient']}\n"
    if doc.get('document_type'):
        response_text += f"Type: {doc['document_type']}\n"
    if doc.get('tags'):
        response_text += f"Tags: {', '.join(doc['tags'])}\n"
    
    response_text += f"\nHash: {doc['file_hash']}\n"
    response_text += f"Path: {doc.get('file_path', 'N/A')}\n"
    
    if doc.get('summary'):
        response_text += f"\n**Summary:**\n{doc['summary']}\n"
    
    if doc.get('full_text'):
        text = doc['full_text']
        # Truncate very long texts
        if len(text) > 5000:
            text = text[:5000] + "\n\n... (text truncated, use file_hash to access full document)"
        response_text += f"\n**Extracted Text:**\n{text}\n"
    
    return jsonify({
        "content": [{
            "type": "text",
            "text": response_text
        }],
        "isError": False
    })


def handle_list_document_types(db):
    """Handle list_document_types tool."""
    types = db.get_document_types()
    
    response_text = f"Found {len(types)} document types:\n\n"
    for doc_type in sorted(types):
        response_text += f"- {doc_type}\n"
    
    return jsonify({
        "content": [{
            "type": "text",
            "text": response_text
        }],
        "isError": False
    })


def handle_get_stats(db):
    """Handle get_stats tool."""
    stats = db.get_stats()
    
    response_text = f"Document Database Statistics:\n\n"
    response_text += f"Total documents: {stats.get('total', 0)}\n"
    response_text += f"Documents with errors: {stats.get('errors', 0)}\n"
    response_text += f"\nTop document types:\n"
    
    # Sort by count and show top 10
    by_type = stats.get('by_type', {})
    sorted_types = sorted(by_type.items(), key=lambda x: x[1], reverse=True)[:10]
    for doc_type, count in sorted_types:
        response_text += f"  {doc_type}: {count}\n"
    
    return jsonify({
        "content": [{
            "type": "text",
            "text": response_text
        }],
        "isError": False
    })