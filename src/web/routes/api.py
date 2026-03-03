"""
API routes for LocalPDFVault.
"""

import os
import re
import threading
import logging
from flask import Blueprint, jsonify, request, Response
from pydantic import ValidationError

from .. import get_db, get_cache, cached
from ...config import settings
from ...models import SearchQuery, IndexRequest, PaginatedResponse
from ...services import PDFScanner, start_watcher, stop_watcher, get_watcher

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

# Thread lock for indexing operations
indexing_lock = threading.Lock()
indexing_thread: threading.Thread = None
scanner: PDFScanner = None


# ============= Search & Document Routes =============

@api_bp.route('/search')
def search():
    """Search documents with filtering, sorting, and pagination."""
    try:
        # Validate query parameters
        query = SearchQuery(
            q=request.args.get('q', ''),
            limit=int(request.args.get('limit', 50)),
            offset=int(request.args.get('offset', 0)),
            document_type=request.args.get('document_type'),
            sender=request.args.get('sender'),
            date_from=request.args.get('date_from'),
            date_to=request.args.get('date_to'),
            sort_by=request.args.get('sort_by', 'relevance'),
            sort_order=request.args.get('sort_order', 'desc')
        )
    except (ValueError, ValidationError) as e:
        return jsonify({'error': 'Invalid parameters', 'detail': str(e)}), 400
    
    db = get_db()
    
    try:
        # Always use search_metadata to support filters
        # When query is empty, it returns all documents with filters applied
        result = db.search_metadata(
            query=query.q,
            limit=query.limit,
            offset=query.offset,
            document_type=query.document_type,
            sender=query.sender,
            date_from=query.date_from,
            date_to=query.date_to,
            sort_by=query.sort_by,
            sort_order=query.sort_order
        )
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({'error': 'Search failed'}), 500


@api_bp.route('/documents')
def list_documents():
    """List all documents with pagination."""
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        sort_by = request.args.get('sort_by', 'last_updated')
        sort_order = request.args.get('sort_order', 'desc')
    except ValueError as e:
        return jsonify({'error': 'Invalid parameters'}), 400
    
    db = get_db()
    result = db.get_all_metadata(limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order)
    return jsonify(result)


@api_bp.route('/pdf/<file_hash>')
def serve_pdf(file_hash):
    """Serve a PDF file by its hash."""
    # Validate hash format
    if not re.match(r'^[a-fA-F0-9]{64}$', file_hash):
        return jsonify({'error': 'Invalid hash format'}), 400
    
    file_hash = file_hash.lower()
    
    db = get_db()
    metadata = db.get_metadata(file_hash)
    
    if not metadata:
        return jsonify({'error': 'Document not found'}), 404
    
    file_path = metadata.get('file_path') or metadata.get('filename')
    
    if not file_path:
        return jsonify({'error': 'File path not found in metadata'}), 404
    
    # Security: Validate path is within vault directory
    try:
        real_path = os.path.realpath(file_path)
        vault_path = settings.vault_realpath
        
        if not real_path.startswith(vault_path):
            logger.warning(f"Path traversal attempt blocked: {file_path}")
            return jsonify({'error': 'Access denied'}), 403
    except Exception as e:
        logger.error(f"Path validation error: {e}")
        return jsonify({'error': 'Invalid file path'}), 500
    
    if not os.path.exists(real_path):
        return jsonify({'error': 'File not found on disk'}), 404
    
    try:
        with open(real_path, 'rb') as f:
            pdf_data = f.read()
        
        response = Response(pdf_data, mimetype='application/pdf')
        response.headers['Content-Disposition'] = 'inline'
        response.headers['Content-Type'] = 'application/pdf'
        return response
    except Exception as e:
        logger.error(f"Error serving PDF: {e}")
        return jsonify({'error': 'Failed to read file'}), 500


@api_bp.route('/document/<file_hash>')
def get_document(file_hash):
    """Get document metadata by hash."""
    if not re.match(r'^[a-fA-F0-9]{64}$', file_hash):
        return jsonify({'error': 'Invalid hash format'}), 400
    
    file_hash = file_hash.lower()
    db = get_db()
    metadata = db.get_metadata(file_hash)
    
    if not metadata:
        return jsonify({'error': 'Document not found'}), 404
    
    return jsonify(metadata)


@api_bp.route('/stats')
@cached(timeout=10)
def get_stats():
    """Get database statistics."""
    db = get_db()
    return jsonify(db.get_stats())


@api_bp.route('/config')
@cached(timeout=30)
def get_config():
    """Return system configuration."""
    db = get_db()
    
    return jsonify({
        'database_path': os.path.abspath(db.db_path),
        'ollama_url': settings.ollama_url,
        'model': settings.ollama_model,
        'vault_path': settings.scan_directory,
        'watch_enabled': settings.watch_enabled
    })


@api_bp.route('/document-types')
def get_document_types():
    """Get list of all document types for filtering."""
    db = get_db()
    return jsonify({'types': db.get_document_types()})


@api_bp.route('/senders')
def get_senders():
    """Get list of all senders for autocomplete."""
    db = get_db()
    limit = int(request.args.get('limit', 100))
    return jsonify({'senders': db.get_senders(limit=limit)})


# ============= Ollama Status =============

@api_bp.route('/ollama/status')
def ollama_status():
    """Check Ollama service status."""
    import requests as req
    
    try:
        response = req.get(f"{settings.ollama_url}/api/tags", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            models = [m.get('name', '') for m in data.get('models', [])]
            model_available = settings.ollama_model in models
            
            return jsonify({
                'status': 'running',
                'url': settings.ollama_url,
                'model': settings.ollama_model,
                'model_available': model_available
            })
        else:
            return jsonify({
                'status': 'error',
                'url': settings.ollama_url,
                'model': settings.ollama_model,
                'error': f'HTTP {response.status_code}'
            })
    except req.exceptions.ConnectionError:
        return jsonify({
            'status': 'offline',
            'url': settings.ollama_url,
            'model': settings.ollama_model,
            'error': 'Connection refused'
        })
    except req.exceptions.Timeout:
        return jsonify({
            'status': 'timeout',
            'url': settings.ollama_url,
            'model': settings.ollama_model,
            'error': 'Connection timeout'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'url': settings.ollama_url,
            'model': settings.ollama_model,
            'error': str(e)
        })


# ============= Delete Routes =============

@api_bp.route('/delete/<file_hash>', methods=['DELETE'])
def delete_document(file_hash):
    """Delete a single document from the index."""
    if not re.match(r'^[a-fA-F0-9]{64}$', file_hash):
        return jsonify({'error': 'Invalid hash format'}), 400
    
    file_hash = file_hash.lower()
    db = get_db()
    success = db.delete_metadata(file_hash)
    
    return jsonify({'success': success})


@api_bp.route('/delete', methods=['POST'])
def delete_documents():
    """Delete multiple documents from the index."""
    data = request.get_json()
    
    if not data or 'hashes' not in data:
        return jsonify({'error': 'Missing hashes parameter'}), 400
    
    hashes = data['hashes']
    if not isinstance(hashes, list) or len(hashes) == 0:
        return jsonify({'error': 'hashes must be a non-empty list'}), 400
    
    # Validate all hashes
    for h in hashes:
        if not re.match(r'^[a-fA-F0-9]{64}$', h):
            return jsonify({'error': f'Invalid hash format: {h}'}), 400
    
    db = get_db()
    deleted = 0
    for h in hashes:
        if db.delete_metadata(h.lower()):
            deleted += 1
    
    return jsonify({'success': True, 'deleted': deleted})


@api_bp.route('/clear', methods=['DELETE'])
def clear_database():
    """Clear all documents from the index."""
    db = get_db()
    success = db.delete_all_metadata()
    return jsonify({'success': success})


# ============= Export Routes =============

@api_bp.route('/export')
def export_documents():
    """Export documents as JSON or CSV."""
    import json as json_module
    
    db = get_db()
    format_type = request.args.get('format', 'json').lower()
    
    # Get all documents (reasonable limit for export)
    result = db.get_all_metadata(limit=10000)
    documents = result['results']
    
    if format_type == 'json':
        return jsonify(documents)
    elif format_type == 'csv':
        import csv
        from io import StringIO
        
        output = StringIO()
        if not documents:
            return jsonify({'error': 'No documents to export'}), 404
        
        fieldnames = ['file_hash', 'filename', 'subject', 'date', 'sender', 
                      'recipient', 'document_type', 'tags', 'file_path']
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        
        for doc in documents:
            doc['tags'] = ';'.join(doc.get('tags', []))
            writer.writerow(doc)
        
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=documents.csv'}
        )
    else:
        return jsonify({'error': 'Invalid format. Use json or csv'}), 400