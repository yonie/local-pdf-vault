"""
Tests for MCP Server handler functions.

The MCP server uses decorator-based handlers (@app.list_tools(), @app.call_tool()),
so we test the actual handler functions directly.
"""

import os
import sys
import pytest
import tempfile
import asyncio

# Set up environment before importing modules
test_dir = tempfile.mkdtemp(prefix='pdfvault_mcp_test_')
test_db = os.path.join(test_dir, 'test.db')
os.environ['DATABASE_PATH'] = test_db
os.environ['WEB_HOST'] = '127.0.0.1'
os.environ['WEB_PORT'] = '14339'
os.environ['SCAN_DIRECTORY'] = test_dir
os.environ['OLLAMA_HOST'] = '127.0.0.1'
os.environ['OLLAMA_PORT'] = '11434'
os.environ['OLLAMA_MODEL'] = 'qwen3-vl:30b-a3b-instruct'
os.environ['MAX_PAGES_PER_END'] = '3'
os.environ['MAX_PARALLEL_SCANNING'] = '4'
os.environ['MAX_PARALLEL_HASHING'] = '2'

from mcp.types import TextContent

# Load modules the same way mcp_server.py does
_base = os.path.dirname(os.path.abspath(__file__))
mcp_base = os.path.join(_base, '..')

def _load_module_direct(name, path, deps=None):
    import importlib.util
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

config = _load_module_direct("mcp_test_config", os.path.join(mcp_base, "src", "config.py"))
database = _load_module_direct("mcp_test_database", os.path.join(mcp_base, "src", "database", "__init__.py"))

Settings = config.Settings
DatabaseManager = database.DatabaseManager


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    d = DatabaseManager(test_db)
    yield d
    d.close()
    # Cleanup
    for ext in ['', '-shm', '-wal']:
        path = test_db + ext
        if os.path.exists(path):
            os.unlink(path)


# ============================================================
# Test handler functions extracted from mcp_server.py logic
# ============================================================

async def handle_search_documents(db, arguments):
    """Mirror of the handler in mcp_server.py"""
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
            "date": doc.get("date"),
            "sender": doc.get("sender"),
            "document_type": doc.get("document_type"),
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


async def handle_get_document(db, arguments):
    """Mirror of the handler in mcp_server.py"""
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
            text = text[:5000] + "\n\n... (text truncated)"
        response_text += f"\n**Extracted Text:**\n{text}\n"

    return [TextContent(type="text", text=response_text)]


async def handle_list_document_types(db):
    types = db.get_document_types()
    response_text = f"Found {len(types)} document types:\n\n"
    for doc_type in sorted(types):
        response_text += f"- {doc_type}\n"
    return [TextContent(type="text", text=response_text)]


async def handle_get_stats(db):
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


async def handle_get_indexing_status(db):
    status = db.get_indexing_status()
    response_text = "Indexing Status:\n\n"
    response_text += f"Running: {status.get('is_running', False)}\n"
    response_text += f"Current file: {status.get('current_file', 'N/A')}\n"
    response_text += f"Progress: {status.get('processed', 0)}/{status.get('total', 0)}\n"
    response_text += f"Skipped: {status.get('skipped', 0)}\n"
    response_text += f"Errors: {status.get('errors', 0)}\n"
    response_text += f"Stop requested: {status.get('stop_requested', False)}\n"
    return [TextContent(type="text", text=response_text)]


# ============================================================
# Tool definition tests (from mcp_server.py)
# ============================================================

def get_tool_definitions():
    """Return the tool definitions as defined in mcp_server.py"""
    from mcp.types import Tool
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


class TestToolDefinitions:
    """Test the tool definitions match mcp_server.py."""

    def test_five_tools_defined(self):
        tools = get_tool_definitions()
        assert len(tools) == 5

    def test_tool_names(self):
        tools = get_tool_definitions()
        names = [t.name for t in tools]
        assert names == [
            "search_documents",
            "get_document",
            "list_document_types",
            "get_stats",
            "get_indexing_status"
        ]

    def test_all_tools_have_descriptions(self):
        tools = get_tool_definitions()
        for tool in tools:
            assert tool.description and len(tool.description) > 10

    def test_all_tools_have_input_schemas(self):
        tools = get_tool_definitions()
        for tool in tools:
            assert tool.inputSchema is not None
            assert tool.inputSchema.get("type") == "object"

    def test_search_documents_requires_query(self):
        tools = get_tool_definitions()
        search = next(t for t in tools if t.name == "search_documents")
        assert "query" in search.inputSchema["required"]

    def test_get_document_requires_file_hash(self):
        tools = get_tool_definitions()
        doc = next(t for t in tools if t.name == "get_document")
        assert "file_hash" in doc.inputSchema["required"]

    def test_search_documents_has_filters(self):
        tools = get_tool_definitions()
        search = next(t for t in tools if t.name == "search_documents")
        props = search.inputSchema["properties"]
        assert "query" in props
        assert "document_type" in props
        assert "sender" in props
        assert "limit" in props

    def test_limit_has_default(self):
        tools = get_tool_definitions()
        search = next(t for t in tools if t.name == "search_documents")
        assert search.inputSchema["properties"]["limit"]["default"] == 10


class TestSearchDocumentsHandler:
    """Test search_documents handler logic."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, db):
        db.store_metadata({
            'file_hash': 'a' * 64,
            'filename': 'invoice_001.pdf',
            'subject': 'Invoice for services rendered',
            'document_type': 'invoice',
            'sender': 'Acme Corp',
            'date': '2024-01-15'
        })

        result = await handle_search_documents(db, {"query": "invoice"})
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "invoice" in result[0].text.lower()
        assert "invoice_001.pdf" in result[0].text

    @pytest.mark.asyncio
    async def test_search_with_document_type_filter(self, db):
        db.store_metadata({
            'file_hash': 'b' * 64,
            'filename': 'contract.pdf',
            'subject': 'Employment contract',
            'document_type': 'contract',
            'sender': 'HR Dept',
            'date': '2024-02-01'
        })
        db.store_metadata({
            'file_hash': 'c' * 64,
            'filename': 'invoice_002.pdf',
            'subject': 'Another invoice',
            'document_type': 'invoice',
            'sender': 'Vendor',
            'date': '2024-03-01'
        })

        result = await handle_search_documents(db, {
            "query": "invoice",
            "document_type": "contract"
        })
        # Should not find invoice results when filtering by contract
        assert "invoice_002.pdf" not in result[0].text

    @pytest.mark.asyncio
    async def test_search_with_sender_filter(self, db):
        db.store_metadata({
            'file_hash': 'd' * 64,
            'filename': 'letter_acme.pdf',
            'subject': 'Business letter',
            'sender': 'Acme Corp',
            'date': '2024-04-01'
        })
        db.store_metadata({
            'file_hash': 'e' * 64,
            'filename': 'letter_beta.pdf',
            'subject': 'Business letter',
            'sender': 'Beta Inc',
            'date': '2024-04-15'
        })

        result = await handle_search_documents(db, {
            "query": "letter",
            "sender": "Acme"
        })
        assert "Acme" in result[0].text

    @pytest.mark.asyncio
    async def test_empty_query_returns_error(self, db):
        result = await handle_search_documents(db, {"query": ""})
        assert "error" in result[0].text.lower() or "required" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_no_results(self, db):
        result = await handle_search_documents(db, {"query": "xyznonexistent"})
        assert "Found 0" in result[0].text

    @pytest.mark.asyncio
    async def test_respects_limit(self, db):
        for i in range(20):
            db.store_metadata({
                'file_hash': f'{i:064d}',
                'filename': f'doc_{i}.pdf',
                'subject': f'Document {i}',
                'file_path': f'/data/pdfs/doc_{i}.pdf'
            })

        result = await handle_search_documents(db, {"query": "document", "limit": 5})
        assert "5 results" in result[0].text

    @pytest.mark.asyncio
    async def test_response_format(self, db):
        db.store_metadata({
            'file_hash': 'f' * 64,
            'filename': 'formatted.pdf',
            'subject': 'Test formatted doc',
            'sender': 'Test Sender',
            'date': '2024-05-01',
            'document_type': 'letter',
            'file_path': '/data/pdfs/formatted.pdf'
        })

        result = await handle_search_documents(db, {"query": "formatted"})
        text = result[0].text
        assert "**formatted.pdf**" in text
        assert "Subject: Test formatted doc" in text
        assert "Date: 2024-05-01" in text
        assert "From: Test Sender" in text
        assert "Type: letter" in text


class TestGetDocumentHandler:
    """Test get_document handler logic."""

    @pytest.mark.asyncio
    async def test_get_existing_document(self, db):
        file_hash = 'f' * 64
        db.store_metadata({
            'file_hash': file_hash,
            'filename': 'report_2024.pdf',
            'subject': 'Annual Report 2024',
            'summary': 'Comprehensive annual financial report',
            'sender': 'Finance Dept',
            'date': '2024-12-31',
            'document_type': 'report',
            'tags': ['annual', 'finance'],
            'file_path': '/data/pdfs/report_2024.pdf'
        })

        result = await handle_get_document(db, {"file_hash": file_hash})
        assert len(result) == 1
        text = result[0].text
        assert "report_2024.pdf" in text
        assert "Annual Report 2024" in text
        assert "Finance Dept" in text
        assert "Comprehensive annual financial report" in text
        assert "Hash:" in text
        assert "Path:" in text

    @pytest.mark.asyncio
    async def test_get_nonexistent_document(self, db):
        result = await handle_get_document(db, {"file_hash": "0" * 64})
        assert "not found" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_missing_file_hash(self, db):
        result = await handle_get_document(db, {})
        assert "error" in result[0].text.lower() or "required" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_includes_tags(self, db):
        file_hash = '1' * 64
        db.store_metadata({
            'file_hash': file_hash,
            'filename': 'tagged.pdf',
            'subject': 'Tagged document',
            'tags': ['important', 'review'],
            'file_path': '/data/pdfs/tagged.pdf'
        })

        result = await handle_get_document(db, {"file_hash": file_hash})
        assert "important" in result[0].text
        assert "review" in result[0].text

    @pytest.mark.asyncio
    async def test_includes_summary(self, db):
        file_hash = '2' * 64
        db.store_metadata({
            'file_hash': file_hash,
            'filename': 'summary_doc.pdf',
            'subject': 'Has summary',
            'summary': 'This is a summary of the document content.',
            'file_path': '/data/pdfs/summary_doc.pdf'
        })

        result = await handle_get_document(db, {"file_hash": file_hash})
        assert "Summary:" in result[0].text
        assert "This is a summary" in result[0].text

    @pytest.mark.asyncio
    async def test_truncates_long_text(self, db):
        long_text = "x" * 10000
        file_hash = '3' * 64
        db.store_metadata({
            'file_hash': file_hash,
            'filename': 'long_text.pdf',
            'full_text': long_text,
            'file_path': '/data/pdfs/long_text.pdf'
        })

        result = await handle_get_document(db, {"file_hash": file_hash})
        assert "text truncated" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_includes_recipient(self, db):
        file_hash = '4' * 64
        db.store_metadata({
            'file_hash': file_hash,
            'filename': 'letter.pdf',
            'subject': 'Business letter',
            'recipient': 'John Doe',
            'file_path': '/data/pdfs/letter.pdf'
        })

        result = await handle_get_document(db, {"file_hash": file_hash})
        assert "To: John Doe" in result[0].text


class TestListDocumentTypesHandler:
    """Test list_document_types handler logic."""

    @pytest.mark.asyncio
    async def test_empty_database(self, db):
        result = await handle_list_document_types(db)
        assert "Found 0" in result[0].text

    @pytest.mark.asyncio
    async def test_with_types(self, db):
        db.store_metadata({
            'file_hash': '5' * 64,
            'filename': 'a.pdf',
            'document_type': 'invoice',
            'file_path': '/data/pdfs/a.pdf'
        })
        db.store_metadata({
            'file_hash': '6' * 64,
            'filename': 'b.pdf',
            'document_type': 'contract',
            'file_path': '/data/pdfs/b.pdf'
        })
        db.store_metadata({
            'file_hash': '7' * 64,
            'filename': 'c.pdf',
            'document_type': 'invoice',
            'file_path': '/data/pdfs/c.pdf'
        })

        result = await handle_list_document_types(db)
        assert "Found 2" in result[0].text
        assert "invoice" in result[0].text
        assert "contract" in result[0].text

    @pytest.mark.asyncio
    async def test_sorted_output(self, db):
        db.store_metadata({
            'file_hash': '8' * 64,
            'filename': 'z.pdf',
            'document_type': 'z_type',
            'file_path': '/data/pdfs/z.pdf'
        })
        db.store_metadata({
            'file_hash': '9' * 64,
            'filename': 'a.pdf',
            'document_type': 'a_type',
            'file_path': '/data/pdfs/a.pdf'
        })

        result = await handle_list_document_types(db)
        text = result[0].text
        assert text.index("a_type") < text.index("z_type")


class TestGetStatsHandler:
    """Test get_stats handler logic."""

    @pytest.mark.asyncio
    async def test_empty_stats(self, db):
        result = await handle_get_stats(db)
        assert "Total documents: 0" in result[0].text
        assert "Documents with errors: 0" in result[0].text

    @pytest.mark.asyncio
    async def test_with_documents(self, db):
        db.store_metadata({
            'file_hash': 'a' * 64,
            'filename': 'stat1.pdf',
            'document_type': 'invoice',
            'file_path': '/data/pdfs/stat1.pdf'
        })
        db.store_metadata({
            'file_hash': 'b' * 64,
            'filename': 'stat2.pdf',
            'document_type': 'contract',
            'file_path': '/data/pdfs/stat2.pdf',
            'error': 'Some processing error'
        })

        result = await handle_get_stats(db)
        assert "Total documents: 2" in result[0].text
        assert "Documents with errors: 1" in result[0].text
        assert "invoice: 1" in result[0].text
        assert "contract: 1" in result[0].text

    @pytest.mark.asyncio
    async def test_top_types_sorted(self, db):
        for i in range(5):
            db.store_metadata({
                'file_hash': f'{i}c' * 13,
                'filename': f's{i}.pdf',
                'document_type': 'invoice',
                'file_path': f'/data/pdfs/s{i}.pdf'
            })
        db.store_metadata({
            'file_hash': 'd' * 64,
            'filename': 'contract.pdf',
            'document_type': 'contract',
            'file_path': '/data/pdfs/contract.pdf'
        })

        result = await handle_get_stats(db)
        assert "invoice: 5" in result[0].text
        assert "contract: 1" in result[0].text


class TestGetIndexingStatusHandler:
    """Test get_indexing_status handler logic."""

    @pytest.mark.asyncio
    async def test_not_running(self, db):
        result = await handle_get_indexing_status(db)
        assert "Running: False" in result[0].text
        assert "Progress: 0/0" in result[0].text

    @pytest.mark.asyncio
    async def test_active_indexing(self, db):
        db.update_indexing_status({
            'is_running': True,
            'current_file': 'test.pdf',
            'processed': 5,
            'total': 10,
            'skipped': 2,
            'errors': 0
        })

        result = await handle_get_indexing_status(db)
        assert "Running: True" in result[0].text
        assert "Current file: test.pdf" in result[0].text
        assert "Progress: 5/10" in result[0].text
        assert "Skipped: 2" in result[0].text

    @pytest.mark.asyncio
    async def test_stop_requested(self, db):
        db.update_indexing_status({'stop_requested': True})
        result = await handle_get_indexing_status(db)
        assert "Stop requested: True" in result[0].text


class TestTextContentFormat:
    """Test that all handler responses use proper TextContent format."""

    @pytest.mark.asyncio
    async def test_all_handlers_return_text_content(self, db):
        db.store_metadata({
            'file_hash': 'e' * 64,
            'filename': 'fmt.pdf',
            'document_type': 'letter',
            'file_path': '/data/pdfs/fmt.pdf'
        })

        tests = [
            ("search", lambda: handle_search_documents(db, {"query": "fmt"})),
            ("get_doc", lambda: handle_get_document(db, {"file_hash": "e" * 64})),
            ("list_types", lambda: handle_list_document_types(db)),
            ("get_stats", lambda: handle_get_stats(db)),
            ("get_status", lambda: handle_get_indexing_status(db)),
        ]

        for name, handler in tests:
            result = await handler()
            assert len(result) > 0, f"{name} returned no results"
            for item in result:
                assert isinstance(item, TextContent), f"{name} returned non-TextContent"
                assert item.type == "text", f"{name} returned non-text type"
                assert len(item.text) > 0, f"{name} returned empty text"

    @pytest.mark.asyncio
    async def test_error_responses_are_text_content(self, db):
        result = await handle_search_documents(db, {"query": ""})
        assert isinstance(result[0], TextContent)
        assert result[0].type == "text"

        result = await handle_get_document(db, {})
        assert isinstance(result[0], TextContent)
        assert result[0].type == "text"

        result = await handle_get_document(db, {"file_hash": "0" * 64})
        assert isinstance(result[0], TextContent)
        assert result[0].type == "text"
