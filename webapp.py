#!/usr/bin/env python3
"""
LocalPDFVault Web Interface

A privacy-focused web interface for searching and browsing your local PDF collection.
All data stays on your computer - never sent to external services.

Author: yonie (https://github.com/yonie)
Developed with AI assistance
"""

from flask import Flask, request, jsonify, send_file, render_template, Response
import os
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from pdfscanner import DatabaseManager, PDFScanner
import config


app = Flask(__name__)
db = DatabaseManager()

# Reset indexing status on startup (in case server was restarted during indexing)
db.reset_indexing_status()

# Thread lock for indexing operations
indexing_lock = threading.Lock()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search')
def search():
    query = request.args.get('q', '')
    if query:
        results = db.search_metadata(query)
    else:
        results = db.get_all_metadata()
    return jsonify(results)

@app.route('/api/pdf/<file_hash>')
def serve_pdf(file_hash):
    metadata = db.get_metadata(file_hash)
    file_path = metadata.get('file_path') or metadata.get('filename')
    if metadata and file_path and os.path.exists(file_path):
        with open(file_path, 'rb') as f:
            pdf_data = f.read()
        response = Response(pdf_data, mimetype='application/pdf')
        response.headers['Content-Disposition'] = 'inline'
        response.headers['Content-Type'] = 'application/pdf'
        return response
    return 'PDF not found', 404

@app.route('/api/stats')
def get_stats():
    stats = db.get_stats()
    return jsonify(stats)

@app.route('/api/config')
def get_config():
    """Return system configuration for privacy info display"""
    # Get absolute path of database
    db_path = os.path.abspath(db.db_path)

    return jsonify({
        'database_path': db_path,
        'ollama_url': f"http://{config.OLLAMA_HOST}:{config.OLLAMA_PORT}",
        'model': config.OLLAMA_MODEL,
        'vault_path': config.SCAN_DIRECTORY
    })


@app.route('/api/ollama/status')
def ollama_status():
    """Check Ollama service status and verify configured model is available"""
    try:
        import requests
        base_url = f"http://{config.OLLAMA_HOST}:{config.OLLAMA_PORT}"
        
        # Try to get tags (available models)
        response = requests.get(f"{base_url}/api/tags", timeout=2)

        if response.status_code == 200:
            data = response.json()
            models = data.get('models', [])
            model_names = [m.get('name', '') for m in models]

            # Check if configured model is available
            model_available = config.OLLAMA_MODEL in model_names

            return jsonify({
                'status': 'running',
                'url': base_url,
                'model': config.OLLAMA_MODEL,
                'model_available': model_available
            })
        else:
            return jsonify({
                'status': 'error',
                'url': base_url,
                'model': config.OLLAMA_MODEL,
                'error': f'HTTP {response.status_code}'
            })
    except requests.exceptions.ConnectionError:
        return jsonify({
            'status': 'offline',
            'url': base_url,
            'model': config.OLLAMA_MODEL,
            'error': 'Connection refused'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'url': base_url,
            'model': config.OLLAMA_MODEL,
            'error': str(e)
        })

@app.route('/api/delete/<file_hash>', methods=['DELETE'])
def delete_document(file_hash):
    success = db.delete_metadata(file_hash)
    return jsonify({'success': success})

@app.route('/api/clear', methods=['DELETE'])
def clear_database():
    success = db.delete_all_metadata()
    return jsonify({'success': success})

@app.route('/api/index', methods=['POST'])
def start_indexing():
    data = request.get_json() or {}
    force = data.get('force', False)  # Force re-indexing even if already indexed
    path = config.SCAN_DIRECTORY

    if not os.path.exists(path):
        return jsonify({'success': False, 'error': f'Vault directory "{path}" does not exist inside the container. Check your docker-compose volume mapping.'})

    if not os.path.isdir(path):
        return jsonify({'success': False, 'error': f'Vault path "{path}" is not a directory.'})

    with indexing_lock:

        current_status = db.get_indexing_status()
        if current_status['is_running']:
            return jsonify({'success': False, 'error': 'Indexing already in progress'})

        # Reset status and start new indexing
        db.update_indexing_status({
            'is_running': True,
            'current_file': '',
            'processed': 0,
            'total': 0,
            'skipped': 0,
            'errors': 0,
            'last_directory': path,
            'stop_requested': False
        })

    # Start indexing in background thread
    thread = threading.Thread(target=run_indexing, args=(path, force))
    thread.daemon = True
    thread.start()

    return jsonify({'success': True})

@app.route('/api/index/status')
def indexing_status():
    return jsonify(db.get_indexing_status())

@app.route('/api/index/stop', methods=['POST'])
def stop_indexing():
    with indexing_lock:
        current_status = db.get_indexing_status()
        if not current_status['is_running']:
            return jsonify({'success': False, 'error': 'No indexing in progress'})

        # Set stop flag
        db.update_indexing_status({'stop_requested': True})

    return jsonify({'success': True, 'message': 'Stop signal sent to indexing process'})

@app.route('/api/reindex/<file_hash>', methods=['POST'])
def reindex_document(file_hash):
    # Delete existing and re-process
    metadata = db.get_metadata(file_hash)
    if not metadata:
        return jsonify({'success': False, 'error': 'Document not found'})
    
    filename = metadata.get('filename')
    if not filename or not os.path.exists(filename):
        return jsonify({'success': False, 'error': 'PDF file not found on disk'})
    
    # Delete from database
    db.delete_metadata(file_hash)
    
    # Re-process in background
    thread = threading.Thread(target=reindex_single, args=(filename,))
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True})

def run_indexing(directory, force_reindex=False):
    """
    High-performance indexing pipeline with parallel hashing and throttled updates.
    """
    try:
        scanner = PDFScanner(
            host=config.OLLAMA_HOST,
            port=config.OLLAMA_PORT,
            model=config.OLLAMA_MODEL
        )
        
        # 1. Test Ollama connection
        if not scanner.test_ollama_connection():
            with indexing_lock:
                db.update_indexing_status({'is_running': False, 'errors': 1})
            return

        # 2. Fast Parallel Directory Scan
        with indexing_lock:
            db.update_indexing_status({'current_file': 'Discovering files...'})
        
        pdf_entries = scanner.scan_directory(directory) # Now returns (path, size, mtime)
        total_files = len(pdf_entries)
        
        # 3. Load known file cache for instant O(1) skip checks
        # file_cache is { path: {hash, size, mtime} }
        file_cache = db.get_file_cache()
        
        with indexing_lock:
            db.update_indexing_status({'total': total_files, 'current_file': f'Syncing {total_files} files...'})

        # 4. Parallel Hashing & Processing Pipeline
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed
        stop_event = threading.Event()
        
        def smart_hash_task(entry):
            if stop_event.is_set(): return None, None, False
            f_path, f_size, f_mtime = entry
            
            # Smart Cache Check
            cached = file_cache.get(f_path)
            if cached and cached['size'] == f_size and abs(cached['mtime'] - f_mtime) < 0.01:
                return f_path, cached['hash'], True
            
            # Cache miss or changed - perform real hash
            return f_path, scanner.generate_file_hash(f_path), False

        processed = 0
        skipped = 0
        errors = 0
        last_ui_update = 0

        with ThreadPoolExecutor(max_workers=config.MAX_PARALLEL_HASHING) as executor:
            futures = {executor.submit(smart_hash_task, entry): entry for entry in pdf_entries}
            
            for i, future in enumerate(as_completed(futures), 1):
                # Check for Stop Request
                with indexing_lock:
                    if db.get_indexing_status()['stop_requested']:
                        stop_event.set()
                        db.update_indexing_status({'is_running': False, 'current_file': '', 'stop_requested': False})
                        return

                f_path, f_hash, from_cache = future.result()
                if not f_path or not f_hash or stop_event.is_set():
                    if not stop_event.is_set() and f_path: errors += 1
                    continue

                filename = os.path.basename(f_path)
                
                if from_cache and not force_reindex:
                    skipped += 1
                else:
                    # AI Analysis required (New or Changed File)
                    print(f"AI Analyzing: {filename}")
                    with indexing_lock:
                        db.update_indexing_status({'current_file': f"🤖 Analyzing: {filename}"})
                    
                    # Process
                    result = scanner.process_pdf(f_path)
                    if result.get('error') is None:
                        db.store_metadata(result)
                        processed += 1
                    else:
                        errors += 1

                # Throttled UI Updates (every 500ms)
                now = time.time()
                if now - last_ui_update > 0.5 or i == total_files:
                    with indexing_lock:
                        db.update_indexing_status({
                            'processed': skipped + processed + errors,
                            'skipped': skipped,
                            'errors': errors,
                            'total': total_files,
                            'current_file': filename if i < total_files else 'Sync complete'
                        })
                    last_ui_update = now

        print(f"Indexing complete: {processed} new, {skipped} skipped, {errors} errors")

    except Exception as e:
        print(f"Indexing error: {e}")
    finally:
        with indexing_lock:
            db.update_indexing_status({'is_running': False, 'current_file': ''})

def reindex_single(filename):

    try:
        scanner = PDFScanner(
            host=config.OLLAMA_HOST,
            port=config.OLLAMA_PORT,
            model=config.OLLAMA_MODEL
        )

        if scanner.test_ollama_connection():
            result = scanner.process_pdf(filename)
            db.store_metadata(result)
    except Exception as e:
        print(f"Reindex error: {e}")

if __name__ == '__main__':
    # Suppress Flask/Werkzeug request logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

    print(f"Starting LocalPDFVault Web Interface on http://{config.WEB_HOST}:{config.WEB_PORT}")
    app.run(host=config.WEB_HOST, port=config.WEB_PORT, debug=False)