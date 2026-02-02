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
    if metadata and metadata['filename'] and os.path.exists(metadata['filename']):
        with open(metadata['filename'], 'rb') as f:
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
    try:
        scanner = PDFScanner(
            host=config.OLLAMA_HOST,
            port=config.OLLAMA_PORT,
            model=config.OLLAMA_MODEL
        )


        # Test Ollama connection
        if not scanner.test_ollama_connection():
            with indexing_lock:
                db.update_indexing_status({
                    'is_running': False,
                    'errors': 1
                })
            return

        print(f"Indexing started for {directory}")

        with indexing_lock:
            db.update_indexing_status({
                'current_file': 'Searching for PDF files...',
                'total': 0,
                'processed': 0
            })

        def scan_progress(current_path):
            # Only update every few directories to avoid flooding the DB
            # We can use a simple counter or just update with a limited frequency
            # For now, let's just update the status with the current directory name
            rel_path = os.path.relpath(current_path, directory)
            display_path = f"Scanning: {rel_path}" if rel_path != "." else "Scanning root..."
            
            # Use a non-blocking way to update if possible, but since we are in a thread it's fine
            # We skip the lock here if we are careful, or just use it briefly
            with indexing_lock:
                db.update_indexing_status({'current_file': display_path})

        # Find all PDFs
        pdf_files = scanner.scan_directory(directory, on_progress=scan_progress)
        total_files = len(pdf_files)


        with indexing_lock:
            db.update_indexing_status({
                'total': total_files
            })

        print(f"Starting indexing of {total_files} PDF files from {directory}")

        for i, pdf_file in enumerate(pdf_files, 1):
            # Check for stop request - fetch fresh status each time
            with indexing_lock:
                current_status = db.get_indexing_status()
                if current_status['stop_requested']:
                    print("Indexing stopped by user request")
                    db.update_indexing_status({
                        'is_running': False,
                        'current_file': '',
                        'stop_requested': False
                    })
                    return

            filename = os.path.basename(pdf_file)
            print(f"Processing file {i} of {total_files}: {filename}")

            with indexing_lock:
                db.update_indexing_status({
                    'current_file': filename
                })

            # Generate hash
            file_hash = scanner.generate_file_hash(pdf_file)
            if not file_hash:
                print(f"Failed to generate hash for {filename}")
                with indexing_lock:
                    # Fetch fresh status before incrementing
                    current_status = db.get_indexing_status()
                    db.update_indexing_status({
                        'errors': current_status['errors'] + 1,
                        'processed': current_status['processed'] + 1
                    })
                continue

            # Check if already exists (skip if not force re-indexing)
            existing = db.get_metadata(file_hash)
            if existing and not force_reindex:
                print(f"Skipping {filename} - already processed")
                with indexing_lock:
                    # Fetch fresh status before incrementing
                    current_status = db.get_indexing_status()
                    db.update_indexing_status({
                        'skipped': current_status['skipped'] + 1,
                        'processed': current_status['processed'] + 1
                    })
                continue

            # If force re-indexing, delete existing entry first
            if existing and force_reindex:
                db.delete_metadata(file_hash)

            # Process
            result = scanner.process_pdf(pdf_file)
            
            # Only store if vision analysis succeeded (no error)
            if result.get('error') is None:
                if db.store_metadata(result):
                    print(f"Successfully processed {filename}")
                else:
                    print(f"Failed to store metadata for {filename}")
                    with indexing_lock:
                        # Fetch fresh status before incrementing
                        current_status = db.get_indexing_status()
                        db.update_indexing_status({
                            'errors': current_status['errors'] + 1
                        })
            else:
                # Vision analysis failed - do not store, count as error for retry later
                print(f"Vision analysis failed for {filename} - not indexed: {result.get('error')}")
                with indexing_lock:
                    # Fetch fresh status before incrementing
                    current_status = db.get_indexing_status()
                    db.update_indexing_status({
                        'errors': current_status['errors'] + 1
                    })

            # Always increment processed counter
            with indexing_lock:
                # Fetch fresh status before incrementing
                current_status = db.get_indexing_status()
                db.update_indexing_status({
                    'processed': current_status['processed'] + 1
                })

        print(f"Indexing completed: {db.get_indexing_status()['processed']} processed, {db.get_indexing_status()['skipped']} skipped, {db.get_indexing_status()['errors']} errors")

    except Exception as e:
        print(f"Indexing error: {e}")
    finally:
        with indexing_lock:
            db.update_indexing_status({
                'is_running': False,
                'current_file': ''
            })

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