"""
Admin routes for indexing and system management.
"""

import os
import threading
import logging
from flask import Blueprint, jsonify, request

from .. import get_db
from ...config import settings
from ...services import PDFScanner, start_watcher, stop_watcher, get_watcher

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

# Thread lock for indexing operations
indexing_lock = threading.Lock()
indexing_thread: threading.Thread = None


def run_indexing(directory: str, force_reindex: bool = False):
    """Run indexing in a background thread."""
    global indexing_thread
    
    db = get_db()
    
    try:
        scanner = PDFScanner(db_manager=db)
        
        # Test Ollama connection
        if not scanner.test_ollama_connection():
            with indexing_lock:
                db.update_indexing_status({'is_running': False, 'errors': 1})
            logger.error("Ollama connection failed")
            return
        
        # Get current status and reset
        with indexing_lock:
            db.update_indexing_status({
                'is_running': True,
                'current_file': '',
                'processed': 0,
                'total': 0,
                'skipped': 0,
                'errors': 0,
                'last_directory': directory,
                'stop_requested': False
            })
        
        # Scan directory
        def status_callback(status):
            with indexing_lock:
                db.update_indexing_status(status)
        
        # Scan for files first
        status_callback({'current_file': 'Discovering files...'})
        pdf_entries = scanner.scan_directory(directory)
        total = len(pdf_entries)
        
        status_callback({'total': total, 'current_file': f'Processing {total} files...'})
        
        # Load file cache for smart skipping
        file_cache = db.get_file_cache()
        
        processed = 0
        skipped = 0
        errors = 0
        
        for idx, (pdf_path, f_size, f_mtime) in enumerate(pdf_entries, 1):
            # Check for stop request
            with indexing_lock:
                status = db.get_indexing_status()
                if status.get('stop_requested'):
                    db.update_indexing_status({
                        'is_running': False, 
                        'current_file': '', 
                        'stop_requested': False
                    })
                    logger.info("Indexing stopped by user request")
                    return
            
            filename = os.path.basename(pdf_path)
            
            # Smart skip check
            cached = file_cache.get(pdf_path)
            if not force_reindex and cached:
                if cached['size'] == f_size and abs(cached['mtime'] - f_mtime) < 0.01:
                    skipped += 1
                    continue
            
            # Process PDF
            logger.info(f"Analyzing [{idx}/{total}]: {filename}")
            status_callback({'current_file': f"Analyzing: {filename}"})
            
            result = scanner.process_pdf(pdf_path)
            
            if result.get('error') is None:
                db.store_metadata(result)
                processed += 1
            else:
                errors += 1
            
            # Update progress
            status_callback({
                'processed': idx,
                'skipped': skipped,
                'errors': errors
            })
        
        logger.info(f"Indexing complete: {processed} new, {skipped} skipped, {errors} errors")
        
    except Exception as e:
        logger.error(f"Indexing error: {e}")
    finally:
        with indexing_lock:
            db.update_indexing_status({'is_running': False, 'current_file': ''})


def reindex_single(filename: str):
    """Reindex a single file."""
    db = get_db()
    
    try:
        scanner = PDFScanner(db_manager=db)
        
        if scanner.test_ollama_connection():
            result = scanner.process_pdf(filename)
            db.store_metadata(result)
    except Exception as e:
        logger.error(f"Reindex error: {e}")


@admin_bp.route('/index', methods=['POST'])
def start_indexing():
    """Start indexing the vault directory."""
    global indexing_thread
    
    data = request.get_json() or {}
    force = data.get('force', False)
    path = settings.scan_directory
    
    if not os.path.exists(path):
        return jsonify({'success': False, 'error': f'Vault directory "{path}" does not exist'}), 400
    
    if not os.path.isdir(path):
        return jsonify({'success': False, 'error': f'Vault path "{path}" is not a directory'}), 400
    
    with indexing_lock:
        db = get_db()
        current_status = db.get_indexing_status()
        
        if current_status['is_running']:
            return jsonify({'success': False, 'error': 'Indexing already in progress'}), 409
        
        # Start indexing in background
        indexing_thread = threading.Thread(target=run_indexing, args=(path, force))
        indexing_thread.daemon = True
        indexing_thread.start()
    
    return jsonify({'success': True})


@admin_bp.route('/index/status')
def indexing_status():
    """Get current indexing status."""
    db = get_db()
    return jsonify(db.get_indexing_status())


@admin_bp.route('/index/stop', methods=['POST'])
def stop_indexing():
    """Request to stop indexing."""
    with indexing_lock:
        db = get_db()
        current_status = db.get_indexing_status()
        
        if not current_status['is_running']:
            return jsonify({'success': False, 'error': 'No indexing in progress'}), 400
        
        db.update_indexing_status({'stop_requested': True})
    
    return jsonify({'success': True, 'message': 'Stop signal sent'})


@admin_bp.route('/reindex/<file_hash>', methods=['POST'])
def reindex_document(file_hash):
    """Reindex a specific document."""
    import re
    
    if not re.match(r'^[a-fA-F0-9]{64}$', file_hash):
        return jsonify({'success': False, 'error': 'Invalid hash format'}), 400
    
    file_hash = file_hash.lower()
    db = get_db()
    metadata = db.get_metadata(file_hash)
    
    if not metadata:
        return jsonify({'success': False, 'error': 'Document not found'}), 404
    
    filename = metadata.get('file_path') or metadata.get('filename')
    if not filename or not os.path.exists(filename):
        return jsonify({'success': False, 'error': 'PDF file not found on disk'}), 404
    
    # Store metadata will replace the existing entry
    thread = threading.Thread(target=reindex_single, args=(filename,))
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True})


@admin_bp.route('/watch/start', methods=['POST'])
def start_file_watcher():
    """Start the file watcher for automatic reindexing."""
    if not settings.watch_enabled:
        return jsonify({'success': False, 'error': 'File watching is disabled in config'}), 400
    
    db = get_db()
    
    def on_file_changed(path: str, event_type: str):
        logger.info(f"File {event_type}: {path}")
        if event_type in ('created', 'modified'):
            # Queue for reindexing
            scanner = PDFScanner(db_manager=db)
            result = scanner.process_pdf(path)
            if result.get('error') is None:
                db.store_metadata(result)
        elif event_type == 'deleted':
            # Remove from index
            # Note: We'd need to find by path, not hash
            pass
    
    success = start_watcher(settings.scan_directory, on_file_changed)
    
    if success:
        return jsonify({'success': True, 'message': 'File watcher started'})
    else:
        return jsonify({'success': False, 'error': 'Failed to start file watcher'}), 500


@admin_bp.route('/watch/stop', methods=['POST'])
def stop_file_watcher():
    """Stop the file watcher."""
    stop_watcher()
    return jsonify({'success': True, 'message': 'File watcher stopped'})


@admin_bp.route('/watch/status')
def watcher_status():
    """Get file watcher status."""
    watcher = get_watcher()
    return jsonify({
        'enabled': settings.watch_enabled,
        'running': watcher.is_watching if watcher else False
    })