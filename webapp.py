#!/usr/bin/env python3
"""
PDF Scanner Web App

A web interface for querying the PDF metadata database and viewing PDFs.
"""

from flask import Flask, request, jsonify, send_file, render_template_string
import os
import threading
from pdfscanner import DatabaseManager, PDFScanner

app = Flask(__name__)
db = DatabaseManager()

# Global state for indexing progress
indexing_state = {
    'is_running': False,
    'current_file': '',
    'processed': 0,
    'total': 0,
    'skipped': 0,
    'errors': 0,
    'last_directory': ''
}
indexing_lock = threading.Lock()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Scanner - Document Browser</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --primary: #2563eb;
            --primary-dark: #1d4ed8;
            --primary-light: #3b82f6;
            --bg-dark: #0f172a;
            --bg-card: #1e293b;
            --bg-hover: #334155;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --border: #334155;
            --success: #22c55e;
            --warning: #f59e0b;
            --danger: #ef4444;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            min-height: 100vh;
            overflow: hidden;
        }

        /* Header */
        .header {
            background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-dark) 100%);
            border-bottom: 1px solid var(--border);
            padding: 16px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo-icon {
            width: 40px;
            height: 40px;
            background: var(--primary);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
        }

        .logo-text {
            font-size: 20px;
            font-weight: 600;
        }

        .logo-text span {
            color: var(--primary-light);
        }

        .stats {
            display: flex;
            gap: 24px;
        }

        .stat {
            text-align: center;
        }

        .stat-value {
            font-size: 24px;
            font-weight: 700;
            color: var(--primary-light);
        }

        .stat-label {
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
        }

        /* Main Layout - 3 Column */
        .main-container {
            display: grid;
            grid-template-columns: 340px 1fr 1fr;
            height: calc(100vh - 73px);
        }

        /* Left Panel - Results List */
        .sidebar {
            background: var(--bg-card);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .search-container {
            padding: 20px;
            border-bottom: 1px solid var(--border);
        }

        .search-box {
            position: relative;
        }

        .search-icon {
            position: absolute;
            left: 14px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
            font-size: 18px;
        }

        .search-input {
            width: 100%;
            padding: 14px 14px 14px 46px;
            background: var(--bg-dark);
            border: 2px solid var(--border);
            border-radius: 12px;
            color: var(--text-primary);
            font-size: 15px;
            transition: all 0.2s;
        }

        .search-input:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2);
        }

        .search-input::placeholder {
            color: var(--text-muted);
        }

        /* Filters */
        .filters {
            padding: 12px 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        .filter-btn {
            padding: 6px 14px;
            background: var(--bg-dark);
            border: 1px solid var(--border);
            border-radius: 20px;
            color: var(--text-secondary);
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
        }

        .filter-btn:hover {
            background: var(--bg-hover);
            color: var(--text-primary);
        }

        .filter-btn.active {
            background: var(--primary);
            border-color: var(--primary);
            color: white;
        }

        /* Results */
        .results-header {
            padding: 12px 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .results-count {
            font-size: 13px;
            color: var(--text-muted);
        }

        .results-list {
            flex: 1;
            overflow-y: auto;
            padding: 12px;
        }

        .result-card {
            background: var(--bg-dark);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 10px;
            cursor: pointer;
            transition: all 0.2s;
        }

        .result-card:hover {
            border-color: var(--primary);
            transform: translateX(4px);
        }

        .result-card.active {
            border-color: var(--primary);
            background: rgba(37, 99, 235, 0.1);
        }

        .result-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 8px;
        }

        .result-filename {
            font-weight: 500;
            font-size: 14px;
            word-break: break-all;
            flex: 1;
        }

        .result-type {
            background: var(--primary);
            color: white;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
            text-transform: uppercase;
            margin-left: 10px;
            white-space: nowrap;
        }

        .result-subject {
            color: var(--text-secondary);
            font-size: 13px;
            margin-bottom: 10px;
            line-height: 1.4;
        }

        .result-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }

        .tag {
            background: var(--bg-hover);
            color: var(--text-secondary);
            padding: 3px 10px;
            border-radius: 6px;
            font-size: 11px;
        }

        .result-meta {
            display: flex;
            gap: 16px;
            margin-top: 10px;
            font-size: 12px;
            color: var(--text-muted);
        }

        .result-meta-item {
            display: flex;
            align-items: center;
            gap: 4px;
        }

        /* Middle Panel - Details */
        .details-panel {
            background: var(--bg-card);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            overflow-y: auto;
        }

        .details-empty {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: var(--text-muted);
            padding: 40px;
        }

        .details-empty-icon {
            font-size: 48px;
            margin-bottom: 16px;
            opacity: 0.5;
        }

        .details-empty h3 {
            font-size: 16px;
            margin-bottom: 8px;
            color: var(--text-secondary);
        }

        .details-empty p {
            font-size: 13px;
            text-align: center;
        }

        .details-header {
            padding: 20px;
            border-bottom: 1px solid var(--border);
            background: var(--bg-dark);
        }

        .details-title {
            font-size: 16px;
            font-weight: 600;
            word-break: break-all;
            margin-bottom: 12px;
        }

        .details-actions {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        .details-content {
            padding: 20px;
            flex: 1;
        }

        /* Right Panel - Preview */
        .preview-panel {
            background: #1a1a1a;
            display: flex;
            flex-direction: column;
        }

        .preview-empty {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: var(--text-muted);
        }

        .preview-empty-icon {
            font-size: 48px;
            margin-bottom: 16px;
            opacity: 0.5;
        }

        .preview-header {
            padding: 12px 16px;
            background: var(--bg-card);
            border-bottom: 1px solid var(--border);
            font-size: 13px;
            font-weight: 500;
            color: var(--text-secondary);
        }

        .preview-content {
            flex: 1;
        }

        .preview-content iframe {
            width: 100%;
            height: 100%;
            border: none;
        }

        /* Legacy content area support */
        .content-empty {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: var(--text-muted);
        }

        .content-empty-icon {
            font-size: 64px;
            margin-bottom: 16px;
            opacity: 0.5;
        }

        .content-empty h3 {
            font-size: 18px;
            margin-bottom: 8px;
            color: var(--text-secondary);
        }

        .content-empty p {
            font-size: 14px;
        }

        /* Metadata Grid */
        .metadata-grid {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .metadata-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 16px;
        }

        .metadata-title {
            font-size: 18px;
            font-weight: 600;
            word-break: break-all;
        }

        .metadata-actions {
            display: flex;
            gap: 10px;
        }

        .btn {
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            border: none;
        }

        .btn-sm {
            padding: 6px 12px;
            font-size: 12px;
        }

        .btn-primary {
            background: var(--primary);
            color: white;
        }

        .btn-primary:hover {
            background: var(--primary-dark);
        }

        .btn-secondary {
            background: var(--bg-dark);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }

        .btn-secondary:hover {
            background: var(--bg-hover);
        }

        .metadata-item {
            background: var(--bg-dark);
            padding: 12px 14px;
            border-radius: 8px;
        }

        .metadata-label {
            font-size: 10px;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-bottom: 4px;
            letter-spacing: 0.5px;
        }

        .metadata-value {
            font-size: 13px;
            color: var(--text-primary);
            line-height: 1.5;
        }

        .metadata-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 6px;
        }

        .metadata-tag {
            background: var(--primary);
            color: white;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
        }

        /* File path display */
        .file-path {
            background: var(--bg-dark);
            padding: 10px 12px;
            border-radius: 8px;
            font-size: 11px;
            color: var(--text-muted);
            word-break: break-all;
            margin-top: 12px;
            border: 1px solid var(--border);
        }

        /* Loading State */
        .loading {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 40px;
            color: var(--text-muted);
        }

        .spinner {
            width: 24px;
            height: 24px;
            border: 3px solid var(--border);
            border-top-color: var(--primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-right: 12px;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* No Results */
        .no-results {
            padding: 40px 20px;
            text-align: center;
            color: var(--text-muted);
        }

        .no-results-icon {
            font-size: 48px;
            margin-bottom: 12px;
            opacity: 0.5;
        }

        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
        }

        ::-webkit-scrollbar-track {
            background: var(--bg-dark);
        }

        ::-webkit-scrollbar-thumb {
            background: var(--border);
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: var(--text-muted);
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 24px;
        }

        /* Modal Styles */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            backdrop-filter: blur(4px);
        }

        .modal-overlay.active {
            display: flex;
        }

        .modal {
            background: var(--bg-card);
            border-radius: 16px;
            width: 90%;
            max-width: 600px;
            max-height: 90vh;
            overflow-y: auto;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
        }

        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 24px;
            border-bottom: 1px solid var(--border);
        }

        .modal-header h2 {
            font-size: 18px;
            font-weight: 600;
        }

        .modal-close {
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 24px;
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 8px;
            transition: all 0.2s;
        }

        .modal-close:hover {
            background: var(--bg-hover);
            color: var(--text-primary);
        }

        .modal-body {
            padding: 24px;
        }

        .admin-section {
            margin-bottom: 28px;
        }

        .admin-section h3 {
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 16px;
            color: var(--text-secondary);
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-bottom: 16px;
        }

        .stat-card {
            background: var(--bg-dark);
            padding: 16px;
            border-radius: 10px;
            text-align: center;
        }

        .stat-card-value {
            font-size: 28px;
            font-weight: 700;
            color: var(--primary-light);
        }

        .stat-card-label {
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 4px;
        }

        .type-breakdown {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .type-badge {
            background: var(--bg-dark);
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 12px;
        }

        .type-badge-count {
            color: var(--primary-light);
            font-weight: 600;
            margin-left: 6px;
        }

        .index-form {
            display: flex;
            gap: 12px;
        }

        .index-input {
            flex: 1;
            padding: 12px 16px;
            background: var(--bg-dark);
            border: 2px solid var(--border);
            border-radius: 10px;
            color: var(--text-primary);
            font-size: 14px;
        }

        .index-input:focus {
            outline: none;
            border-color: var(--primary);
        }

        .index-progress {
            margin-top: 16px;
            background: var(--bg-dark);
            padding: 16px;
            border-radius: 10px;
        }

        .progress-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 13px;
        }

        .progress-bar-container {
            height: 8px;
            background: var(--border);
            border-radius: 4px;
            overflow: hidden;
        }

        .progress-bar {
            height: 100%;
            background: var(--primary);
            width: 0%;
            transition: width 0.3s;
        }

        .progress-file {
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 8px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .danger-zone {
            background: rgba(239, 68, 68, 0.1);
            padding: 16px;
            border-radius: 10px;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .danger-zone p {
            font-size: 13px;
            color: var(--text-muted);
            margin-bottom: 12px;
        }

        .btn-danger {
            background: var(--danger);
            color: white;
        }

        .btn-danger:hover {
            background: #dc2626;
        }

        /* Delete button in results */
        .result-delete {
            opacity: 0;
            background: none;
            border: none;
            color: var(--danger);
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 14px;
            transition: all 0.2s;
        }

        .result-card:hover .result-delete {
            opacity: 1;
        }

        .result-delete:hover {
            background: rgba(239, 68, 68, 0.2);
        }

        /* Responsive */
        @media (max-width: 1400px) {
            .main-container {
                grid-template-columns: 300px 1fr 1fr;
            }
        }

        @media (max-width: 1100px) {
            .main-container {
                grid-template-columns: 280px 1fr;
            }
            .preview-panel {
                display: none;
            }
        }

        @media (max-width: 768px) {
            .main-container {
                grid-template-columns: 1fr;
            }
            .sidebar {
                height: 50vh;
            }
            .details-panel {
                height: 50vh;
            }
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="logo">
            <div class="logo-icon">📄</div>
            <div class="logo-text">PDF <span>Scanner</span></div>
        </div>
        <div class="header-actions">
            <div class="stats">
                <div class="stat">
                    <div class="stat-value" id="totalDocs">-</div>
                    <div class="stat-label">Documents</div>
                </div>
            </div>
            <button class="btn btn-primary" onclick="openAdminPanel()">
                ⚙️ Manage Index
            </button>
        </div>
    </header>

    <div class="main-container">
        <!-- Left: Results List -->
        <aside class="sidebar">
            <div class="search-container">
                <div class="search-box">
                    <span class="search-icon">🔍</span>
                    <input type="text" class="search-input" id="searchInput"
                           placeholder="Search documents..."
                           autocomplete="off">
                </div>
            </div>
            <div class="filters" id="filters">
                <button class="filter-btn active" data-filter="all">All</button>
            </div>
            <div class="results-header">
                <span class="results-count" id="resultsCount">Loading...</span>
            </div>
            <div class="results-list" id="resultsList">
                <div class="loading">
                    <div class="spinner"></div>
                    <span>Loading...</span>
                </div>
            </div>
        </aside>

        <!-- Middle: Document Details -->
        <main class="details-panel" id="detailsPanel">
            <div class="details-empty">
                <div class="details-empty-icon">📋</div>
                <h3>Document Details</h3>
                <p>Select a document from the list to view its metadata</p>
            </div>
        </main>

        <!-- Right: PDF Preview -->
        <aside class="preview-panel" id="previewPanel">
            <div class="preview-empty">
                <div class="preview-empty-icon">📄</div>
                <p>PDF Preview</p>
            </div>
        </aside>
    </div>

    <!-- Admin Panel Modal -->
    <div class="modal-overlay" id="adminModal">
        <div class="modal">
            <div class="modal-header">
                <h2>Index Management</h2>
                <button class="modal-close" onclick="closeAdminPanel()">&times;</button>
            </div>
            <div class="modal-body">
                <!-- Stats Section -->
                <div class="admin-section">
                    <h3>📊 Database Statistics</h3>
                    <div class="stats-grid" id="statsGrid">
                        <div class="stat-card">
                            <div class="stat-card-value" id="statTotal">-</div>
                            <div class="stat-card-label">Total Documents</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-card-value" id="statErrors">-</div>
                            <div class="stat-card-label">With Errors</div>
                        </div>
                    </div>
                    <div id="typeBreakdown" class="type-breakdown"></div>
                </div>

                <!-- Indexing Section -->
                <div class="admin-section">
                    <h3>📁 Index Directory</h3>
                    <div class="index-form">
                        <input type="text" id="indexPath" class="index-input"
                               placeholder="Enter directory path to scan (e.g., C:\\Documents\\PDFs)">
                        <button class="btn btn-primary" onclick="startIndexing()" id="indexBtn">
                            🔍 Start Indexing
                        </button>
                    </div>
                    <div class="index-progress" id="indexProgress" style="display: none;">
                        <div class="progress-header">
                            <span id="progressStatus">Indexing...</span>
                            <span id="progressCount">0/0</span>
                        </div>
                        <div class="progress-bar-container">
                            <div class="progress-bar" id="progressBar"></div>
                        </div>
                        <div class="progress-file" id="progressFile">-</div>
                    </div>
                </div>

                <!-- Danger Zone -->
                <div class="admin-section danger-zone">
                    <h3>⚠️ Danger Zone</h3>
                    <p>These actions cannot be undone.</p>
                    <button class="btn btn-danger" onclick="clearDatabase()">
                        🗑️ Clear All Data
                    </button>
                </div>
            </div>
        </div>
    </div>

    <script>
        let allResults = [];
        let currentFilter = 'all';
        let currentHash = null;
        let searchTimeout = null;

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            loadDocuments();
            setupEventListeners();
        });

        function setupEventListeners() {
            const searchInput = document.getElementById('searchInput');
            searchInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    loadDocuments(e.target.value);
                }, 300);
            });

            document.getElementById('filters').addEventListener('click', (e) => {
                if (e.target.classList.contains('filter-btn')) {
                    document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
                    e.target.classList.add('active');
                    currentFilter = e.target.dataset.filter;
                    applyFilter();
                }
            });
        }

        async function loadDocuments(query = '') {
            try {
                const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
                allResults = await response.json();
                
                document.getElementById('totalDocs').textContent = allResults.length;
                updateFilters();
                applyFilter();
            } catch (error) {
                console.error('Error loading documents:', error);
                document.getElementById('resultsList').innerHTML = `
                    <div class="no-results">
                        <div class="no-results-icon">⚠️</div>
                        <p>Error loading documents</p>
                    </div>
                `;
            }
        }

        function updateFilters() {
            const types = new Set(allResults.map(r => r.document_type).filter(Boolean));
            const filtersContainer = document.getElementById('filters');
            
            filtersContainer.innerHTML = '<button class="filter-btn active" data-filter="all">All</button>';
            
            types.forEach(type => {
                const btn = document.createElement('button');
                btn.className = 'filter-btn';
                btn.dataset.filter = type;
                btn.textContent = type.charAt(0).toUpperCase() + type.slice(1);
                filtersContainer.appendChild(btn);
            });
        }

        function applyFilter() {
            let filtered = allResults;
            
            if (currentFilter !== 'all') {
                filtered = allResults.filter(r => r.document_type === currentFilter);
            }
            
            displayResults(filtered);
        }

        function displayResults(results) {
            const container = document.getElementById('resultsList');
            const countEl = document.getElementById('resultsCount');
            
            countEl.textContent = `${results.length} document${results.length !== 1 ? 's' : ''}`;
            
            if (results.length === 0) {
                container.innerHTML = `
                    <div class="no-results">
                        <div class="no-results-icon">📭</div>
                        <p>No documents found</p>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = results.map(result => {
                const filename = result.filename.split(/[/\\\\]/).pop();
                const tags = (result.tags || []).slice(0, 4);
                
                return `
                    <div class="result-card ${result.file_hash === currentHash ? 'active' : ''}" 
                         onclick="showDocument('${result.file_hash}')">
                        <div class="result-header">
                            <span class="result-filename">${escapeHtml(filename)}</span>
                            ${result.document_type ? `<span class="result-type">${escapeHtml(result.document_type)}</span>` : ''}
                        </div>
                        ${result.subject ? `<div class="result-subject">${escapeHtml(result.subject)}</div>` : ''}
                        ${tags.length > 0 ? `
                            <div class="result-tags">
                                ${tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
                            </div>
                        ` : ''}
                        <div class="result-meta">
                            ${result.date ? `<span class="result-meta-item">📅 ${escapeHtml(result.date)}</span>` : ''}
                            ${result.sender ? `<span class="result-meta-item">👤 ${escapeHtml(result.sender)}</span>` : ''}
                            <button class="result-delete" onclick="event.stopPropagation(); deleteDocument('${result.file_hash}')" title="Delete">🗑️</button>
                        </div>
                    </div>
                `;
            }).join('');
        }

        // Admin Panel Functions
        function openAdminPanel() {
            document.getElementById('adminModal').classList.add('active');
            loadStats();
        }

        function closeAdminPanel() {
            document.getElementById('adminModal').classList.remove('active');
        }

        async function loadStats() {
            try {
                const response = await fetch('/api/stats');
                const stats = await response.json();
                
                document.getElementById('statTotal').textContent = stats.total;
                document.getElementById('statErrors').textContent = stats.errors;
                
                const typeBreakdown = document.getElementById('typeBreakdown');
                if (Object.keys(stats.by_type).length > 0) {
                    typeBreakdown.innerHTML = Object.entries(stats.by_type)
                        .map(([type, count]) => `
                            <span class="type-badge">
                                ${escapeHtml(type)}<span class="type-badge-count">${count}</span>
                            </span>
                        `).join('');
                } else {
                    typeBreakdown.innerHTML = '<span class="type-badge">No documents indexed</span>';
                }
            } catch (error) {
                console.error('Error loading stats:', error);
            }
        }

        let indexingInterval = null;

        async function startIndexing() {
            const path = document.getElementById('indexPath').value.trim();
            if (!path) {
                alert('Please enter a directory path');
                return;
            }

            const btn = document.getElementById('indexBtn');
            btn.disabled = true;
            btn.innerHTML = '⏳ Starting...';

            try {
                const response = await fetch('/api/index', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: path })
                });

                const result = await response.json();
                
                if (result.success) {
                    document.getElementById('indexProgress').style.display = 'block';
                    startProgressPolling();
                } else {
                    alert('Error: ' + result.error);
                    btn.disabled = false;
                    btn.innerHTML = '🔍 Start Indexing';
                }
            } catch (error) {
                alert('Error starting indexing: ' + error);
                btn.disabled = false;
                btn.innerHTML = '🔍 Start Indexing';
            }
        }

        function startProgressPolling() {
            if (indexingInterval) clearInterval(indexingInterval);
            
            indexingInterval = setInterval(async () => {
                try {
                    const response = await fetch('/api/index/status');
                    const status = await response.json();
                    
                    document.getElementById('progressStatus').textContent =
                        status.is_running ? 'Indexing...' : 'Complete';
                    document.getElementById('progressCount').textContent =
                        `${status.processed}/${status.total} (${status.skipped} skipped, ${status.errors} errors)`;
                    
                    const pct = status.total > 0 ? (status.processed / status.total * 100) : 0;
                    document.getElementById('progressBar').style.width = pct + '%';
                    document.getElementById('progressFile').textContent = status.current_file || '-';

                    if (!status.is_running) {
                        clearInterval(indexingInterval);
                        indexingInterval = null;
                        document.getElementById('indexBtn').disabled = false;
                        document.getElementById('indexBtn').innerHTML = '🔍 Start Indexing';
                        loadStats();
                        loadDocuments();
                    }
                } catch (error) {
                    console.error('Error polling status:', error);
                }
            }, 500);
        }

        async function deleteDocument(hash) {
            if (!confirm('Delete this document from the index?')) return;
            
            try {
                const response = await fetch(`/api/delete/${hash}`, { method: 'DELETE' });
                const result = await response.json();
                
                if (result.success) {
                    loadDocuments();
                    if (currentHash === hash) {
                        document.getElementById('detailsPanel').innerHTML = `
                            <div class="details-empty">
                                <div class="details-empty-icon">📋</div>
                                <h3>Document Details</h3>
                                <p>Select a document from the list to view its metadata</p>
                            </div>
                        `;
                        document.getElementById('previewPanel').innerHTML = `
                            <div class="preview-empty">
                                <div class="preview-empty-icon">📄</div>
                                <p>PDF Preview</p>
                            </div>
                        `;
                        currentHash = null;
                    }
                } else {
                    alert('Error deleting document');
                }
            } catch (error) {
                alert('Error: ' + error);
            }
        }

        async function clearDatabase() {
            if (!confirm('Are you sure you want to delete ALL indexed documents?\\n\\nThis cannot be undone!')) return;
            if (!confirm('FINAL WARNING: This will permanently delete all document metadata. Continue?')) return;
            
            try {
                const response = await fetch('/api/clear', { method: 'DELETE' });
                const result = await response.json();
                
                if (result.success) {
                    loadStats();
                    loadDocuments();
                    closeAdminPanel();
                } else {
                    alert('Error clearing database');
                }
            } catch (error) {
                alert('Error: ' + error);
            }
        }

        function showDocument(hash) {
            const result = allResults.find(r => r.file_hash === hash);
            if (!result) return;
            
            currentHash = hash;
            
            // Update active state in list
            document.querySelectorAll('.result-card').forEach(card => {
                card.classList.toggle('active', card.onclick.toString().includes(hash));
            });
            
            const filename = result.filename.split(/[/\\\\]/).pop();
            const tags = result.tags || [];
            
            // Update details panel (middle)
            document.getElementById('detailsPanel').innerHTML = `
                <div class="details-header">
                    <div class="details-title">${escapeHtml(filename)}</div>
                    <div class="details-actions">
                        <a href="/api/pdf/${hash}" target="_blank" class="btn btn-primary btn-sm">
                            📄 Open in New Tab
                        </a>
                        <button class="btn btn-secondary btn-sm" onclick="copyPath('${escapeHtml(result.filename).replace(/'/g, "\\'")}')">
                            📋 Copy Path
                        </button>
                        <button class="btn btn-secondary btn-sm" onclick="deleteDocument('${hash}')">
                            🗑️ Delete
                        </button>
                    </div>
                </div>
                <div class="details-content">
                    <div class="metadata-grid">
                        ${result.document_type ? `
                            <div class="metadata-item">
                                <div class="metadata-label">Document Type</div>
                                <div class="metadata-value">${escapeHtml(result.document_type)}</div>
                            </div>
                        ` : ''}
                        ${result.subject ? `
                            <div class="metadata-item">
                                <div class="metadata-label">Subject</div>
                                <div class="metadata-value">${escapeHtml(result.subject)}</div>
                            </div>
                        ` : ''}
                        ${result.date ? `
                            <div class="metadata-item">
                                <div class="metadata-label">Date</div>
                                <div class="metadata-value">${escapeHtml(result.date)}</div>
                            </div>
                        ` : ''}
                        ${result.sender ? `
                            <div class="metadata-item">
                                <div class="metadata-label">Sender</div>
                                <div class="metadata-value">${escapeHtml(result.sender)}</div>
                            </div>
                        ` : ''}
                        ${result.recipient ? `
                            <div class="metadata-item">
                                <div class="metadata-label">Recipient</div>
                                <div class="metadata-value">${escapeHtml(result.recipient)}</div>
                            </div>
                        ` : ''}
                        ${result.summary ? `
                            <div class="metadata-item">
                                <div class="metadata-label">Summary</div>
                                <div class="metadata-value">${escapeHtml(result.summary)}</div>
                            </div>
                        ` : ''}
                        ${tags.length > 0 ? `
                            <div class="metadata-item">
                                <div class="metadata-label">Tags</div>
                                <div class="metadata-tags">
                                    ${tags.map(tag => `<span class="metadata-tag">${escapeHtml(tag)}</span>`).join('')}
                                </div>
                            </div>
                        ` : ''}
                    </div>
                    <div class="file-path">
                        📁 ${escapeHtml(result.filename)}
                    </div>
                </div>
            `;
            
            // Update preview panel (right)
            document.getElementById('previewPanel').innerHTML = `
                <div class="preview-header">PDF Preview</div>
                <div class="preview-content">
                    <iframe src="/api/pdf/${hash}"></iframe>
                </div>
            `;
        }

        function copyPath(path) {
            navigator.clipboard.writeText(path).then(() => {
                const btn = event.target;
                const originalText = btn.innerHTML;
                btn.innerHTML = '✓ Copied!';
                setTimeout(() => {
                    btn.innerHTML = originalText;
                }, 2000);
            });
        }

        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

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
        from flask import Response
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
    global indexing_state
    
    data = request.get_json()
    path = data.get('path', '')
    
    if not path:
        return jsonify({'success': False, 'error': 'No path provided'})
    
    if not os.path.exists(path):
        return jsonify({'success': False, 'error': 'Directory does not exist'})
    
    if not os.path.isdir(path):
        return jsonify({'success': False, 'error': 'Path is not a directory'})
    
    with indexing_lock:
        if indexing_state['is_running']:
            return jsonify({'success': False, 'error': 'Indexing already in progress'})
        
        indexing_state = {
            'is_running': True,
            'current_file': '',
            'processed': 0,
            'total': 0,
            'skipped': 0,
            'errors': 0,
            'last_directory': path
        }
    
    # Start indexing in background thread
    thread = threading.Thread(target=run_indexing, args=(path,))
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True})

@app.route('/api/index/status')
def indexing_status():
    return jsonify(indexing_state)

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

def run_indexing(directory):
    global indexing_state
    
    try:
        scanner = PDFScanner()
        
        # Test Ollama connection
        if not scanner.test_ollama_connection():
            with indexing_lock:
                indexing_state['is_running'] = False
                indexing_state['errors'] = 1
            return
        
        # Find all PDFs
        pdf_files = scanner.scan_directory(directory)
        
        with indexing_lock:
            indexing_state['total'] = len(pdf_files)
        
        for pdf_file in pdf_files:
            with indexing_lock:
                indexing_state['current_file'] = os.path.basename(pdf_file)
            
            # Generate hash
            file_hash = scanner.generate_file_hash(pdf_file)
            if not file_hash:
                with indexing_lock:
                    indexing_state['errors'] += 1
                    indexing_state['processed'] += 1
                continue
            
            # Check if already exists
            if db.get_metadata(file_hash):
                with indexing_lock:
                    indexing_state['skipped'] += 1
                    indexing_state['processed'] += 1
                continue
            
            # Process
            result = scanner.process_pdf(pdf_file)
            if db.store_metadata(result):
                if result.get('error'):
                    with indexing_lock:
                        indexing_state['errors'] += 1
            else:
                with indexing_lock:
                    indexing_state['errors'] += 1
            
            with indexing_lock:
                indexing_state['processed'] += 1
        
    except Exception as e:
        print(f"Indexing error: {e}")
    finally:
        with indexing_lock:
            indexing_state['is_running'] = False
            indexing_state['current_file'] = ''

def reindex_single(filename):
    try:
        scanner = PDFScanner()
        if scanner.test_ollama_connection():
            result = scanner.process_pdf(filename)
            db.store_metadata(result)
    except Exception as e:
        print(f"Reindex error: {e}")

if __name__ == '__main__':
    print("Starting PDF Scanner Web App on http://localhost:4337")
    app.run(host='0.0.0.0', port=4337, debug=True)