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

# Thread lock for indexing operations
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

        /* Main Layout - 3 Column Resizable */
        .main-container {
            display: flex;
            height: calc(100vh - 73px);
            position: relative;
        }

        .panel {
            flex: 1;
            min-width: 200px;
            position: relative;
            display: flex;
            flex-direction: column;
        }

        .panel[data-panel="sidebar"] {
            flex: 0 0 340px;
        }

        .panel[data-panel="details"] {
            flex: 1;
        }

        .panel[data-panel="preview"] {
            flex: 1 !important;
            min-width: 300px;
        }

        .resizer {
            width: 4px;
            background: var(--border);
            cursor: col-resize;
            position: relative;
            z-index: 10;
            opacity: 0;
            transition: opacity 0.2s;
        }

        .resizer:hover,
        .resizer.active {
            opacity: 1;
            background: var(--primary);
        }

        .resizer::before {
            content: '';
            position: absolute;
            left: -4px;
            right: -4px;
            top: 0;
            bottom: 0;
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

        .recent-searches {
            margin-top: 10px;
        }

        .recent-searches-label {
            font-size: 11px;
            color: var(--text-muted);
            margin-bottom: 6px;
        }

        .recent-searches-list {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }

        .recent-search-item {
            background: var(--bg-dark);
            border: 1px solid var(--border);
            padding: 4px 10px;
            border-radius: 14px;
            font-size: 12px;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .recent-search-item:hover {
            border-color: var(--primary);
            color: var(--text-primary);
        }

        .recent-search-remove {
            font-size: 10px;
            opacity: 0.5;
        }

        .recent-search-remove:hover {
            opacity: 1;
            color: var(--danger);
        }

        /* Filters */
        .filters {
            padding: 12px 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            max-height: 120px;
            overflow-y: auto;
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
            border-radius: 10px;
            padding: 14px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: all 0.15s ease;
            position: relative;
        }

        .result-card:hover {
            border-color: var(--primary-light);
            background: rgba(37, 99, 235, 0.05);
        }

        .result-card.active {
            border-color: var(--primary);
            background: rgba(37, 99, 235, 0.1);
            box-shadow: 0 0 0 1px var(--primary);
        }

        .result-header {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            margin-bottom: 6px;
        }

        .result-filename {
            font-weight: 600;
            font-size: 13px;
            color: var(--text-primary);
            word-break: break-word;
            flex: 1;
            line-height: 1.3;
        }

        .result-type {
            background: var(--bg-hover);
            color: var(--text-secondary);
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 500;
            text-transform: uppercase;
            white-space: nowrap;
            flex-shrink: 0;
        }

        .result-subject {
            color: var(--text-secondary);
            font-size: 12px;
            margin-bottom: 8px;
            line-height: 1.4;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }

        .result-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            margin-bottom: 6px;
        }

        .tag {
            background: var(--bg-hover);
            color: var(--text-muted);
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10px;
        }

        .result-meta {
            display: flex;
            gap: 12px;
            font-size: 11px;
            color: var(--text-muted);
            border-top: 1px solid var(--border);
            padding-top: 8px;
            margin-top: 6px;
        }

        .result-meta-item {
            display: flex;
            align-items: center;
            gap: 4px;
        }

        .result-matches {
            margin-top: 6px;
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
        }

        .match-badge {
            background: rgba(37, 99, 235, 0.2);
            color: var(--primary-light);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 500;
        }

        .match-term {
            font-weight: 600;
        }

        .match-fields {
            opacity: 0.7;
            font-size: 9px;
            margin-left: 2px;
        }

        .match-score {
            background: rgba(37, 99, 235, 0.2);
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            margin-left: 4px;
        }

        .match-score.high {
            background: rgba(34, 197, 94, 0.3);
            color: var(--success);
        }

        .match-score.medium {
            background: rgba(37, 99, 235, 0.3);
            color: var(--primary-light);
        }

        .match-score.low {
            background: rgba(245, 158, 11, 0.3);
            color: var(--warning);
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

        .preview-content {
            flex: 1;
            overflow: auto;
        }

        .preview-content iframe {
            width: 100%;
            height: 100%;
            border: none;
        }

        .pdfjs-container {
            display: flex;
            flex-direction: column;
            height: 100%;
        }

        .pdfjs-toolbar {
            padding: 8px 12px;
            background: var(--bg-card);
            border-bottom: 1px solid var(--border);
            display: flex;
            gap: 8px;
            align-items: center;
            flex-wrap: wrap;
        }

        .pdfjs-toolbar button {
            padding: 6px 12px;
            background: var(--bg-dark);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
        }

        .pdfjs-toolbar button:hover:not(:disabled) {
            background: var(--bg-hover);
            color: var(--text-primary);
        }

        .pdfjs-toolbar button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .pdfjs-toolbar .page-info {
            font-size: 12px;
            color: var(--text-muted);
            margin-left: auto;
        }

        .pdfjs-canvas {
            flex: 1;
            overflow: auto;
            background: #1a1a1a;
            position: relative;
        }

        .pdfjs-canvas.dragging {
            cursor: grabbing;
            user-select: none;
        }

        .pdfjs-canvas-inner {
            padding: 20px;
            width: 100%;
            min-width: 100%;
            box-sizing: border-box;
            display: inline-block;
        }

        .pdfjs-canvas canvas {
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
            display: block;
        }

        .pdfjs-scroll-hint {
            position: absolute;
            bottom: 16px;
            right: 16px;
            background: rgba(0, 0, 0, 0.7);
            color: var(--text-secondary);
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 11px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.3s;
        }

        .pdfjs-canvas:hover .pdfjs-scroll-hint {
            opacity: 1;
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


        .tag-toggle-btn {
            background: none;
            border: none;
            color: var(--primary);
            cursor: pointer;
            font-size: 12px;
            padding: 0;
            margin-left: 4px;
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

        .privacy-info {
            background: rgba(34, 197, 94, 0.1);
            padding: 16px;
            border-radius: 10px;
            border: 1px solid rgba(34, 197, 94, 0.3);
        }

        .privacy-info p {
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: 10px;
            line-height: 1.5;
        }

        .config-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background: var(--bg-dark);
            border-radius: 8px;
            margin-bottom: 8px;
            font-size: 13px;
        }

        .config-item-label {
            color: var(--text-muted);
            min-width: 100px;
        }

        .config-item-value {
            color: var(--text-primary);
            font-family: monospace;
            word-break: break-all;
        }

        .last-indexed-info {
            margin-top: 12px;
            padding: 12px;
            background: var(--bg-dark);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
        }

        .last-indexed-info span {
            font-size: 12px;
            color: var(--text-secondary);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .btn-danger {
            background: var(--danger);
            color: white;
        }

        .btn-danger:hover {
            background: #dc2626;
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
                <div class="stat" style="font-size: 12px; color: var(--text-muted);">
                    <div id="totalDocs">Current index has - total documents</div>
                </div>
            </div>
            <button class="btn btn-primary" onclick="openAdminPanel()">
                ⚙️ Manage Index
            </button>
        </div>
    </header>

    <div class="main-container" id="mainContainer">
        <!-- Panel 1: Results List -->
        <div class="panel" data-panel="sidebar">
            <aside class="sidebar">
                <div class="search-container">
                    <div class="search-box">
                        <span class="search-icon">🔍</span>
                        <input type="text" class="search-input" id="searchInput"
                               placeholder="Search documents..."
                               autocomplete="off">
                    </div>
                    <div class="recent-searches" id="recentSearches" style="display: none;">
                        <div class="recent-searches-label">Recent searches</div>
                        <div class="recent-searches-list" id="recentSearchesList"></div>
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
        </div>
        <div class="resizer" data-resizer="sidebar"></div>

        <!-- Panel 2: Document Details -->
        <div class="panel" data-panel="details">
            <main class="details-panel" id="detailsPanel">
                <div class="details-empty">
                    <div class="details-empty-icon">📋</div>
                    <h3>Document Details</h3>
                    <p>Select a document from the list to view its metadata</p>
                </div>
            </main>
        </div>
        <div class="resizer" data-resizer="details"></div>

        <!-- Panel 3: PDF Preview -->
        <div class="panel" data-panel="preview">
            <aside class="preview-panel" id="previewPanel">
                <div class="preview-empty">
                    <div class="preview-empty-icon">📄</div>
                    <p>PDF Preview</p>
                </div>
            </aside>
        </div>
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
                </div>

                <!-- Scan for Files Section -->
                <div class="admin-section">
                    <h3>📂 Scan PDF Files</h3>
                    <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 12px;">
                        Enter a folder path to scan for PDFs. New files will be added to the index.
                    </p>
                    <div class="index-form">
                        <input type="text" id="indexPath" class="index-input"
                               placeholder="e.g., C:\\Documents\\PDFs">
                        <button class="btn btn-primary" onclick="startIndexing()" id="indexBtn">
                            🔍 Scan
                        </button>
                    </div>
                    <div class="index-progress" id="indexProgress" style="display: none;">
                        <div class="progress-header">
                            <span id="progressStatus">Scanning...</span>
                            <span id="progressCount">0/0</span>
                            <button class="btn btn-danger btn-sm" onclick="stopIndexing()" id="stopBtn" style="display: none;">Stop</button>
                        </div>
                        <div class="progress-bar-container">
                            <div class="progress-bar" id="progressBar"></div>
                        </div>
                        <div class="progress-file" id="progressFile">-</div>
                    </div>
                </div>

                <!-- Maintenance Section -->
                <div class="admin-section">
                    <h3>🔧 Maintenance</h3>
                    <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 12px;">
                        Reset the database by re-analyzing all documents with AI. This only updates the search index - your PDF files remain untouched on disk.
                    </p>
                    <button class="btn btn-primary" onclick="clearAndRescan()" style="width: 100%;">
                        🔄 Reset Index (Re-analyze All Files)
                    </button>
                </div>

                <!-- Privacy & System Info -->
                <div class="admin-section privacy-info">
                    <h3>🔒 Privacy & System Info</h3>
                    <p>
                        <strong>Your data stays on your computer.</strong> All document information is stored locally.
                        AI analysis is performed using the server shown below - verify these settings to confirm where your data is processed.
                    </p>
                    <div id="systemConfigInfo">
                        <div class="config-item">
                            <span class="config-item-label">📁 Database:</span>
                            <span class="config-item-value" id="configDbPath">Loading...</span>
                        </div>
                        <div class="config-item">
                            <span class="config-item-label">🖥️ AI Server:</span>
                            <span class="config-item-value" id="configOllamaUrl">Loading...</span>
                        </div>
                        <div class="config-item">
                            <span class="config-item-label">🤖 AI Model:</span>
                            <span class="config-item-value" id="configModel">Loading...</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let allResults = [];
        let currentFilter = 'all';
        let currentHash = null;
        let searchTimeout = null;
        let currentSearchQuery = '';  // Track if we have an active search

        // Layout Management
        let panelSizes = {};

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            loadLayoutPreferences();
            loadSavedIndexPath();
            loadQueryFromUrl();
            setupEventListeners();
            setupResizers();
            setupModalHandlers();
            loadTotalDocs();
        });

        // URL query parameter handling
        function loadQueryFromUrl() {
            const params = new URLSearchParams(window.location.search);
            const query = params.get('q') || '';
            document.getElementById('searchInput').value = query;
            loadDocuments(query);
        }

        function updateUrlWithQuery(query) {
            const url = new URL(window.location);
            if (query && query.trim()) {
                url.searchParams.set('q', query);
            } else {
                url.searchParams.delete('q');
            }
            window.history.replaceState({}, '', url);
        }

        // LocalStorage keys
        const INDEX_PATH_KEY = 'pdfScanner_lastIndexPath';
        const RECENT_SEARCHES_KEY = 'pdfScanner_recentSearches';
        const MAX_RECENT_SEARCHES = 8;

        function loadSavedIndexPath() {
            const savedPath = localStorage.getItem(INDEX_PATH_KEY);
            if (savedPath) {
                document.getElementById('indexPath').value = savedPath;
            }
        }

        function saveIndexPath(path) {
            localStorage.setItem(INDEX_PATH_KEY, path);
        }

        // Recent Searches Functions
        function getRecentSearches() {
            try {
                const saved = localStorage.getItem(RECENT_SEARCHES_KEY);
                return saved ? JSON.parse(saved) : [];
            } catch (e) {
                return [];
            }
        }

        function saveRecentSearch(query) {
            if (!query || query.length < 2) return;
            
            let searches = getRecentSearches();
            // Remove if already exists (to move to front)
            searches = searches.filter(s => s.toLowerCase() !== query.toLowerCase());
            // Add to beginning
            searches.unshift(query);
            // Keep only MAX_RECENT_SEARCHES
            searches = searches.slice(0, MAX_RECENT_SEARCHES);
            localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(searches));
            renderRecentSearches();
        }

        function removeRecentSearch(query) {
            let searches = getRecentSearches();
            searches = searches.filter(s => s !== query);
            localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(searches));
            renderRecentSearches();
        }

        function renderRecentSearches() {
            const searches = getRecentSearches();
            const container = document.getElementById('recentSearches');
            const list = document.getElementById('recentSearchesList');
            
            if (searches.length === 0) {
                container.style.display = 'none';
                return;
            }
            
            container.style.display = 'block';
            list.innerHTML = searches.map(search => `
                <span class="recent-search-item" onclick="useRecentSearch('${escapeHtml(search).replace(/'/g, "\\'")}')">
                    ${escapeHtml(search)}
                    <span class="recent-search-remove" onclick="event.stopPropagation(); removeRecentSearch('${escapeHtml(search).replace(/'/g, "\\'")}')">✕</span>
                </span>
            `).join('');
        }

        function useRecentSearch(query) {
            document.getElementById('searchInput').value = query;
            document.getElementById('recentSearches').style.display = 'none';
            loadDocuments(query);
            // Move to front of recent searches
            saveRecentSearch(query);
        }

        function setupEventListeners() {
            const searchInput = document.getElementById('searchInput');
            searchInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    loadDocuments(e.target.value);
                }, 300);
            });

            // Save search on Enter or when user stops typing for a while
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && searchInput.value.trim()) {
                    saveRecentSearch(searchInput.value.trim());
                }
            });

            // Show recent searches when input is focused and empty
            searchInput.addEventListener('focus', () => {
                if (!searchInput.value.trim()) {
                    renderRecentSearches();
                }
            });

            // Hide recent searches when clicking outside
            document.addEventListener('click', (e) => {
                const recentSearches = document.getElementById('recentSearches');
                const searchBox = document.querySelector('.search-box');
                if (!searchBox.contains(e.target) && !recentSearches.contains(e.target)) {
                    recentSearches.style.display = 'none';
                }
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

        function setupModalHandlers() {
            const modal = document.getElementById('adminModal');
            
            // Close on Escape key
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && modal.classList.contains('active')) {
                    closeAdminPanel();
                }
            });
            
            // Close when clicking on overlay (outside modal content)
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    closeAdminPanel();
                }
            });
        }

        async function loadDocuments(query = '') {
            currentSearchQuery = query;  // Track the search query
            updateUrlWithQuery(query);  // Update URL with query
            try {
                const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
                allResults = await response.json();

                updateFilters();
                applyFilter();
                
                // Hide recent searches when we have search results
                if (query) {
                    document.getElementById('recentSearches').style.display = 'none';
                }
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
                const matches = result.search_matches || [];
                const relevanceScore = result.relevance_score || 0;
                // Only show match percentage when there's an active search
                const showScore = currentSearchQuery && currentSearchQuery.trim() && relevanceScore > 0;
                const matchPercent = showScore ? getMatchPercent(relevanceScore) : { show: false };

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
                        ${matches.length > 0 ? `
                            <div class="result-matches">
                                ${matches.map(match => `
                                    <span class="match-badge">
                                        <span class="match-term">${escapeHtml(match.term)}</span>
                                        <span class="match-fields">(${match.fields.join(', ')})</span>
                                    </span>
                                `).join('')}
                                ${showScore && matchPercent.show ? `
                                    <span class="match-score ${matchPercent.level}" title="${matchPercent.label}">
                                        ${matchPercent.percent}%
                                    </span>
                                ` : ''}
                            </div>
                        ` : ''}
                        <div class="result-meta">
                            ${result.date ? `<span class="result-meta-item">📅 ${escapeHtml(result.date)}</span>` : ''}
                            ${result.sender ? `<span class="result-meta-item">👤 ${escapeHtml(result.sender)}</span>` : ''}
                        </div>
                    </div>
                `;
            }).join('');
        }

        // Admin Panel Functions
        function openAdminPanel() {
            document.getElementById('adminModal').classList.add('active');
            loadStats();
            loadSystemConfig();
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
                
            } catch (error) {
                console.error('Error loading stats:', error);
            }
        }

        async function loadSystemConfig() {
            try {
                const response = await fetch('/api/config');
                const config = await response.json();

                document.getElementById('configDbPath').textContent = config.database_path || 'Unknown';
                document.getElementById('configOllamaUrl').textContent = config.ollama_url || 'Unknown';
                document.getElementById('configModel').textContent = config.model || 'Unknown';
            } catch (error) {
                console.error('Error loading config:', error);
                document.getElementById('configDbPath').textContent = 'Error loading';
                document.getElementById('configOllamaUrl').textContent = 'Error loading';
                document.getElementById('configModel').textContent = 'Error loading';
            }
        }

        function loadTotalDocs() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(stats => {
                    document.getElementById('totalDocs').textContent = `Current index has ${stats.total} total documents`;
                })
                .catch(error => {
                    console.error('Error loading total docs:', error);
                    document.getElementById('totalDocs').textContent = 'Current index has - total documents';
                });
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
            btn.innerHTML = '⏳ Scanning...';

            try {
                const response = await fetch('/api/index', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: path })
                });

                const result = await response.json();
                
                if (result.success) {
                    // Save the path to localStorage
                    saveIndexPath(path);
                    document.getElementById('indexProgress').style.display = 'block';
                    document.getElementById('stopBtn').style.display = 'inline-block';
                    startProgressPolling();
                } else {
                    alert('Error: ' + result.error);
                    btn.disabled = false;
                    btn.innerHTML = '🔍 Scan Folder';
                }
            } catch (error) {
                alert('Error starting indexing: ' + error);
                btn.disabled = false;
                btn.innerHTML = '🔍 Start Indexing';
            }
        }

        async function startReindexing(path) {
            if (!path) {
                alert('Please enter a directory path');
                return;
            }

            const btn = document.getElementById('indexBtn');
            btn.disabled = true;
            btn.innerHTML = '⏳ Scanning...';

            try {
                const response = await fetch('/api/index', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: path, force: true })
                });

                const result = await response.json();
                
                if (result.success) {
                    saveIndexPath(path);
                    document.getElementById('indexProgress').style.display = 'block';
                    startProgressPolling();
                } else {
                    alert('Error: ' + result.error);
                    btn.disabled = false;
                    btn.innerHTML = '🔍 Scan Folder';
                }
            } catch (error) {
                alert('Error starting analysis: ' + error);
                btn.disabled = false;
                btn.innerHTML = '🔍 Scan Folder';
            }
        }

        async function clearIndex() {
            if (!confirm('Remove all document records from the database?\\n\\nThis will clear the index - your actual PDF files will NOT be deleted.')) return;
            
            try {
                const response = await fetch('/api/clear', { method: 'DELETE' });
                const result = await response.json();
                
                if (result.success) {
                    loadStats();
                    loadDocuments();
                    alert('All records removed successfully. You can scan your folders again to rebuild the index.');
                } else {
                    alert('Error clearing index');
                }
            } catch (error) {
                alert('Error: ' + error);
            }
        }

        async function clearAndRescan() {
            const savedPath = localStorage.getItem(INDEX_PATH_KEY);
            if (!savedPath) {
                alert('No previously scanned folder found. Please enter a folder path first.');
                return;
            }

            if (!confirm(`Refresh the search index for:\\n${savedPath}\\n\\nThis will clear the database and re-analyze all PDFs with fresh AI analysis.\\n\\n⚠️ Your PDF files will NOT be modified or deleted - only the search database will be updated.\\n\\nThis may take a while. Continue?`)) return;

            // First clear the index
            try {
                await fetch('/api/clear', { method: 'DELETE' });
            } catch (error) {
                console.error('Error clearing index:', error);
            }

            // Then start re-indexing
            startReindexing(savedPath);
        }

        async function stopIndexing() {
            try {
                const response = await fetch('/api/index/stop', { method: 'POST' });
                const result = await response.json();

                if (result.success) {
                    document.getElementById('stopBtn').disabled = true;
                    document.getElementById('stopBtn').innerHTML = 'Stopping...';
                    alert('Stop signal sent. The indexing process will stop gracefully.');
                } else {
                    alert('Error: ' + result.error);
                }
            } catch (error) {
                alert('Error stopping indexing: ' + error);
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
                        document.getElementById('indexBtn').innerHTML = '🔍 Scan Folder';
                        document.getElementById('stopBtn').style.display = 'none';
                        document.getElementById('stopBtn').disabled = false;
                        document.getElementById('stopBtn').innerHTML = 'Stop';
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
                <div class="preview-header">PDF Preview - Scroll or drag to navigate</div>
                <div class="pdfjs-container">
                    <div class="pdfjs-toolbar">
                        <button onclick="pdfViewer.prevPage()" id="prevBtn" disabled>◀ Prev</button>
                        <button onclick="pdfViewer.nextPage()" id="nextBtn" disabled>Next ▶</button>
                        <button onclick="pdfViewer.zoomIn()">🔍+</button>
                        <button onclick="pdfViewer.zoomOut()">🔍-</button>
                        <button onclick="pdfViewer.fitToWidth()">↔ Fit</button>
                        <button onclick="pdfViewer.resetView()">⟲ Reset</button>
                        <span class="page-info" id="pageInfo">Loading...</span>
                    </div>
                    <div class="pdfjs-canvas" id="pdfCanvas">
                        <div class="pdfjs-canvas-inner" id="pdfCanvasInner"></div>
                        <div class="pdfjs-scroll-hint">🖱️ Scroll or drag to pan</div>
                    </div>
                </div>
            `;

            // Initialize PDF viewer
            if (window.pdfViewer) {
                window.pdfViewer.destroy();
            }
            window.pdfViewer = new PDFViewer(hash);
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

        function getMatchPercent(score) {
            // Convert numeric relevance score to 0-100% for display
            // Only show percentage when there's an active search (score > 0)
            // Score tiers from pdfscanner.py:
            // 1000+ = exact phrase match (100%)
            // 500-999 = all terms present (80-95%)
            // 100-499 = multiple term matches (50-75%)
            // 50-99 = single term match (30-45%)
            // 1-49 = fuzzy match only (10-25%)
            // 0 = no search query or no match
            
            if (score <= 0) {
                return { show: false, percent: 0, level: '', label: '' };
            } else if (score >= 1000) {
                return { show: true, percent: 100, level: 'high', label: 'Perfect match - exact phrase found' };
            } else if (score >= 500) {
                const pct = Math.min(95, 80 + Math.floor((score - 500) / 50));
                return { show: true, percent: pct, level: 'high', label: 'All search terms found' };
            } else if (score >= 100) {
                const pct = Math.min(75, 50 + Math.floor((score - 100) / 16));
                return { show: true, percent: pct, level: 'medium', label: 'Multiple terms found' };
            } else if (score >= 50) {
                const pct = Math.min(45, 30 + Math.floor((score - 50) / 5));
                return { show: true, percent: pct, level: 'medium', label: 'Partial match' };
            } else {
                const pct = Math.min(25, 10 + Math.floor(score / 4));
                return { show: true, percent: pct, level: 'low', label: 'Similar' };
            }
        }

        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }


        // PDF.js Viewer Class with drag-to-pan support
        class PDFViewer {
            constructor(hash) {
                this.hash = hash;
                this.pdfDoc = null;
                this.pageNum = 1;
                this.pageRendering = false;
                this.pageNumPending = null;
                this.scale = 1.5;
                this.defaultScale = 1.5;
                this.canvas = document.getElementById('pdfCanvas');
                this.canvasInner = document.getElementById('pdfCanvasInner');
                this.prevBtn = document.getElementById('prevBtn');
                this.nextBtn = document.getElementById('nextBtn');
                this.pageInfo = document.getElementById('pageInfo');
                
                // Drag-to-pan state
                this.isDragging = false;
                this.startX = 0;
                this.startY = 0;
                this.scrollLeft = 0;
                this.scrollTop = 0;
                
                this.setupDragToPan();
                this.loadPDF();
            }

            setupDragToPan() {
                const container = this.canvas;
                
                // Mouse wheel zoom only (Ctrl+Scroll)
                container.addEventListener('wheel', (e) => {
                    if (e.ctrlKey) {
                        e.preventDefault();
                        if (e.deltaY < 0) {
                            this.zoomIn();
                        } else {
                            this.zoomOut();
                        }
                    }
                    // Normal wheel scrolling works automatically via overflow: auto
                }, { passive: false });
            }

            async loadPDF() {
                try {
                    // Load PDF.js if not loaded
                    if (!window.pdfjsLib) {
                        await this.loadPDFJS();
                    }

                    const loadingTask = pdfjsLib.getDocument(`/api/pdf/${this.hash}`);
                    this.pdfDoc = await loadingTask.promise;

                    this.pageInfo.textContent = `Page ${this.pageNum} of ${this.pdfDoc.numPages}`;
                    this.updateButtons();

                    this.renderPage(this.pageNum);
                } catch (error) {
                    console.error('Error loading PDF:', error);
                    this.pageInfo.textContent = 'Error loading PDF';
                }
            }

            async loadPDFJS() {
                return new Promise((resolve, reject) => {
                    if (window.pdfjsLib) {
                        resolve();
                        return;
                    }

                    const script = document.createElement('script');
                    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
                    script.onload = () => {
                        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
                        resolve();
                    };
                    script.onerror = reject;
                    document.head.appendChild(script);
                });
            }

            renderPage(num) {
                this.pageRendering = true;

                this.pdfDoc.getPage(num).then((page) => {
                    const viewport = page.getViewport({ scale: this.scale });
                    const canvas = document.createElement('canvas');
                    const context = canvas.getContext('2d');

                    canvas.height = viewport.height;
                    canvas.width = viewport.width;
                    canvas.className = 'pdfjs-page';
                    canvas.style.display = 'block';
                    canvas.style.margin = '0 auto';
                    canvas.style.maxWidth = '100%';
                    canvas.style.height = 'auto';
                    canvas.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.5)';
        
                    // Clear previous content but keep the inner container
                    this.canvasInner.innerHTML = '';

                    const renderContext = {
                        canvasContext: context,
                        viewport: viewport
                    };

                    const renderTask = page.render(renderContext);
                    renderTask.promise.then(() => {
                        this.canvasInner.appendChild(canvas);
                        this.pageRendering = false;

                        if (this.pageNumPending !== null) {
                            this.renderPage(this.pageNumPending);
                            this.pageNumPending = null;
                        }
                    });
                });

                this.pageInfo.textContent = `Page ${num} of ${this.pdfDoc.numPages}`;
            }

            queueRenderPage(num) {
                if (this.pageRendering) {
                    this.pageNumPending = num;
                } else {
                    this.renderPage(num);
                }
            }

            prevPage() {
                if (this.pageNum <= 1) return;
                this.pageNum--;
                this.queueRenderPage(this.pageNum);
                this.updateButtons();
                // Reset scroll position when changing pages
                this.canvas.scrollTop = 0;
                this.canvas.scrollLeft = 0;
            }

            nextPage() {
                if (this.pageNum >= this.pdfDoc.numPages) return;
                this.pageNum++;
                this.queueRenderPage(this.pageNum);
                this.updateButtons();
                // Reset scroll position when changing pages
                this.canvas.scrollTop = 0;
                this.canvas.scrollLeft = 0;
            }

            zoomIn() {
                this.scale *= 1.25;
                this.queueRenderPage(this.pageNum);
            }

            zoomOut() {
                this.scale /= 1.25;
                if (this.scale < 0.5) this.scale = 0.5;
                this.queueRenderPage(this.pageNum);
            }

            fitToWidth() {
                if (!this.pdfDoc) return;
                this.pdfDoc.getPage(this.pageNum).then((page) => {
                    const viewport = page.getViewport({ scale: 1 });
                    const containerWidth = this.canvasInner.clientWidth - 40; // padding
                    this.scale = containerWidth / viewport.width;
                    this.queueRenderPage(this.pageNum);
                });
            }

            resetView() {
                this.scale = this.defaultScale;
                this.canvas.scrollTop = 0;
                this.canvas.scrollLeft = 0;
                this.queueRenderPage(this.pageNum);
            }

            updateButtons() {
                if (!this.pdfDoc) return;
                this.prevBtn.disabled = this.pageNum <= 1;
                this.nextBtn.disabled = this.pageNum >= this.pdfDoc.numPages;
            }

            destroy() {
                if (this.canvasInner) {
                    this.canvasInner.innerHTML = '';
                }
            }
        }

        // Layout Management Functions
        function setupResizers() {
            const resizers = document.querySelectorAll('.resizer');
            let currentResizer = null;
            let startX = 0;
            let startWidth = 0;

            resizers.forEach(resizer => {
                resizer.addEventListener('mousedown', (e) => {
                    currentResizer = resizer;
                    startX = e.clientX;

                    const panel = resizer.previousElementSibling;
                    startWidth = panel.offsetWidth;

                    document.addEventListener('mousemove', resize);
                    document.addEventListener('mouseup', stopResize);
                    resizer.classList.add('active');
                });
            });

            function resize(e) {
                if (!currentResizer) return;

                const panel = currentResizer.previousElementSibling;
                const deltaX = e.clientX - startX;
                const newWidth = Math.max(200, startWidth + deltaX);

                panel.style.flex = `0 0 ${newWidth}px`;
                saveLayoutPreferences();
            }

            function stopResize() {
                if (currentResizer) {
                    currentResizer.classList.remove('active');
                    currentResizer = null;
                }
                document.removeEventListener('mousemove', resize);
                document.removeEventListener('mouseup', stopResize);
            }
        }

        function saveLayoutPreferences() {
            // Save panel sizes, but never save the preview panel size
            const panels = document.querySelectorAll('.panel');
            panels.forEach(panel => {
                const panelType = panel.dataset.panel;
                if (panelType === 'preview') return; // Don't save preview panel size
                const width = panel.offsetWidth;
                panelSizes[panelType] = width;
            });
            localStorage.setItem('pdfScanner_panelSizes', JSON.stringify(panelSizes));
        }

        function loadLayoutPreferences() {
            // Load panel sizes
            const savedSizes = localStorage.getItem('pdfScanner_panelSizes');
            if (savedSizes) {
                try {
                    panelSizes = JSON.parse(savedSizes);
                } catch (e) {
                    console.error('Error loading panel sizes:', e);
                }
            }

            // Apply saved sizes, but never to the preview panel which should always be flexible
            Object.entries(panelSizes).forEach(([panelType, size]) => {
                if (panelType === 'preview') return; // Skip preview panel
                const panel = document.querySelector(`[data-panel="${panelType}"]`);
                if (panel) {
                    panel.style.flex = `0 0 ${size}px`;
                }
            });
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

@app.route('/api/config')
def get_config():
    """Return system configuration for privacy info display"""
    # Get absolute path of database
    db_path = os.path.abspath(db.db_path)
    
    # Default Ollama settings (matching PDFScanner defaults)
    ollama_host = "localhost"
    ollama_port = 11434
    ollama_model = "qwen3-vl:30b-a3b-instruct-q4_K_M"
    
    return jsonify({
        'database_path': db_path,
        'ollama_url': f"http://{ollama_host}:{ollama_port}",
        'model': ollama_model
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
    data = request.get_json()
    path = data.get('path', '')
    force = data.get('force', False)  # Force re-indexing even if already indexed

    if not path:
        return jsonify({'success': False, 'error': 'No path provided'})

    if not os.path.exists(path):
        return jsonify({'success': False, 'error': 'Directory does not exist'})

    if not os.path.isdir(path):
        return jsonify({'success': False, 'error': 'Path is not a directory'})

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
        scanner = PDFScanner()

        # Test Ollama connection
        if not scanner.test_ollama_connection():
            with indexing_lock:
                db.update_indexing_status({
                    'is_running': False,
                    'errors': 1
                })
            return

        # Find all PDFs
        pdf_files = scanner.scan_directory(directory)
        total_files = len(pdf_files)

        with indexing_lock:
            db.update_indexing_status({
                'total': total_files
            })

        print(f"Starting indexing of {total_files} PDF files from {directory}")

        for i, pdf_file in enumerate(pdf_files, 1):
            # Check for stop request
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
            if db.store_metadata(result):
                if result.get('error'):
                    print(f"Processed {filename} with error: {result.get('error')}")
                    with indexing_lock:
                        db.update_indexing_status({
                            'errors': current_status['errors'] + 1
                        })
                else:
                    print(f"Successfully processed {filename}")
            else:
                print(f"Failed to store metadata for {filename}")
                with indexing_lock:
                    db.update_indexing_status({
                        'errors': current_status['errors'] + 1
                    })

            with indexing_lock:
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
        scanner = PDFScanner()
        if scanner.test_ollama_connection():
            result = scanner.process_pdf(filename)
            db.store_metadata(result)
    except Exception as e:
        print(f"Reindex error: {e}")

if __name__ == '__main__':
    print("Starting PDF Scanner Web App on http://localhost:4337")
    app.run(host='0.0.0.0', port=4337, debug=True)