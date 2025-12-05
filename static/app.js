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
const SELECTED_DOC_KEY = 'pdfScanner_selectedDocument';
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

function saveSelectedDocument(hash) {
    localStorage.setItem(SELECTED_DOC_KEY, hash);
}

function loadSelectedDocument() {
    return localStorage.getItem(SELECTED_DOC_KEY);
}

function clearSelectedDocument() {
    localStorage.removeItem(SELECTED_DOC_KEY);
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
        
        // Restore previously selected document if it exists in results
        const savedHash = loadSelectedDocument();
        if (savedHash && allResults.some(r => r.file_hash === savedHash)) {
            showDocument(savedHash);
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
            clearSelectedDocument();
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
                clearSelectedDocument();
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
    
    // Save selected document to localStorage
    saveSelectedDocument(hash);
    
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
        <div class="preview-header">PDF Preview - Drag to pan • Ctrl+Scroll to zoom • Scroll to navigate</div>
        <div class="pdfjs-container">
            <div class="pdfjs-toolbar">
                <button onclick="pdfViewer.prevPage()" id="prevBtn" disabled>◀ Prev</button>
                <button onclick="pdfViewer.nextPage()" id="nextBtn" disabled>Next ▶</button>
                <button onclick="pdfViewer.zoomOut()">🔍−</button>
                <span class="zoom-level" id="zoomLevel">100%</span>
                <button onclick="pdfViewer.zoomIn()">🔍+</button>
                <button onclick="pdfViewer.fitToWidth()">↔ Fit</button>
                <button onclick="pdfViewer.resetView()">⟲ Reset</button>
                <span class="page-info" id="pageInfo">Loading...</span>
            </div>
            <div class="pdfjs-canvas" id="pdfCanvas">
                <div class="pdfjs-canvas-inner" id="pdfCanvasInner"></div>
                <div class="pdfjs-scroll-hint">🖱️ Drag to pan • Ctrl+Scroll to zoom • Scroll to navigate</div>
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


// PDF.js Viewer Class - Completely rebuilt with robust zoom
class PDFViewer {
    constructor(hash) {
        this.hash = hash;
        this.pdfDoc = null;
        this.pageNum = 1;
        this.pageRendering = false;
        this.pageNumPending = null;
        
        // Zoom configuration
        this.scale = null; // Will be calculated to fit width
        this.defaultScale = null; // Will be set after fit-to-width
        this.minScale = 0.25;
        this.maxScale = 5.0;
        this.zoomStep = 0.15; // Smoother zoom increment (15%)
        
        // DOM elements
        this.canvas = document.getElementById('pdfCanvas');
        this.canvasInner = document.getElementById('pdfCanvasInner');
        this.prevBtn = document.getElementById('prevBtn');
        this.nextBtn = document.getElementById('nextBtn');
        this.pageInfo = document.getElementById('pageInfo');
        this.zoomLevel = document.getElementById('zoomLevel');
        
        // Current page dimensions (for scroll position preservation)
        this.currentPageWidth = 0;
        this.currentPageHeight = 0;
        
        // Drag state
        this.isDragging = false;
        this.dragStartX = 0;
        this.dragStartY = 0;
        this.scrollStartX = 0;
        this.scrollStartY = 0;
        
        this.setupEventListeners();
        this.loadPDF();
    }

    setupEventListeners() {
        const container = this.canvas;
        
        // Mouse drag for panning
        container.addEventListener('mousedown', (e) => {
            // Only enable dragging if content is larger than container
            if (container.scrollWidth > container.clientWidth ||
                container.scrollHeight > container.clientHeight) {
                this.isDragging = true;
                this.dragStartX = e.clientX;
                this.dragStartY = e.clientY;
                this.scrollStartX = container.scrollLeft;
                this.scrollStartY = container.scrollTop;
                container.style.cursor = 'grabbing';
                e.preventDefault();
            }
        });
        
        container.addEventListener('mousemove', (e) => {
            if (this.isDragging) {
                const deltaX = e.clientX - this.dragStartX;
                const deltaY = e.clientY - this.dragStartY;
                container.scrollLeft = this.scrollStartX - deltaX;
                container.scrollTop = this.scrollStartY - deltaY;
            }
        });
        
        const stopDragging = () => {
            if (this.isDragging) {
                this.isDragging = false;
                container.style.cursor = '';
            }
        };
        
        container.addEventListener('mouseup', stopDragging);
        container.addEventListener('mouseleave', stopDragging);
        
        // Update cursor based on content size
        container.addEventListener('mouseenter', () => {
            if (!this.isDragging &&
                (container.scrollWidth > container.clientWidth ||
                 container.scrollHeight > container.clientHeight)) {
                container.style.cursor = 'grab';
            }
        });
        
        // Ctrl+Scroll for zoom
        container.addEventListener('wheel', (e) => {
            if (e.ctrlKey) {
                e.preventDefault();
                
                // Get the mouse position relative to the container
                const rect = container.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const mouseY = e.clientY - rect.top;
                
                // Calculate scroll position percentages before zoom
                const scrollXPercent = (container.scrollLeft + mouseX) / container.scrollWidth;
                const scrollYPercent = (container.scrollTop + mouseY) / container.scrollHeight;
                
                // Apply zoom
                if (e.deltaY < 0) {
                    this.zoomIn();
                } else {
                    this.zoomOut();
                }
                
                // Preserve the scroll position relative to the original mouse position
                // This will be applied after rendering completes
                this.pendingScrollPosition = {
                    percentX: scrollXPercent,
                    percentY: scrollYPercent,
                    mouseX: mouseX,
                    mouseY: mouseY
                };
            }
        }, { passive: false });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Only handle if this viewer is active
            if (!this.pdfDoc) return;
            
            // Zoom: Ctrl/Cmd + Plus/Minus
            if ((e.ctrlKey || e.metaKey) && !e.shiftKey) {
                if (e.key === '+' || e.key === '=') {
                    e.preventDefault();
                    this.zoomIn();
                } else if (e.key === '-' || e.key === '_') {
                    e.preventDefault();
                    this.zoomOut();
                } else if (e.key === '0') {
                    e.preventDefault();
                    this.resetView();
                }
            }
            
            // Page navigation: Arrow keys
            if (e.key === 'ArrowLeft' && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                this.prevPage();
            } else if (e.key === 'ArrowRight' && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                this.nextPage();
            }
        });
    }

    async loadPDF() {
        try {
            // Load PDF.js library if not already loaded
            if (!window.pdfjsLib) {
                await this.loadPDFJS();
            }

            const loadingTask = pdfjsLib.getDocument(`/api/pdf/${this.hash}`);
            this.pdfDoc = await loadingTask.promise;

            this.updatePageInfo();
            this.updateButtons();
            
            // Calculate fit-to-width and render
            await this.calculateAndRenderFitToWidth();
        } catch (error) {
            console.error('Error loading PDF:', error);
            this.pageInfo.textContent = 'Error loading PDF';
        }
    }
    
    async calculateAndRenderFitToWidth() {
        try {
            const page = await this.pdfDoc.getPage(this.pageNum);
            const viewport = page.getViewport({ scale: 1 });
            
            // Wait for next animation frame to ensure DOM layout is complete
            await new Promise(resolve => requestAnimationFrame(resolve));
            
            // Now measure the container - it should have proper dimensions
            const containerWidth = this.canvas.clientWidth - 40; // Account for padding
            
            if (containerWidth > 0) {
                const fitScale = Math.min(this.maxScale, Math.max(this.minScale, containerWidth / viewport.width));
                this.scale = fitScale;
                this.defaultScale = fitScale;
            } else {
                // Fallback if container width is still 0
                this.scale = 1.5;
                this.defaultScale = 1.5;
            }
            
            this.updateZoomLevel();
            this.renderPage(this.pageNum);
        } catch (error) {
            console.error('Error calculating fit-to-width:', error);
            this.scale = 1.5;
            this.defaultScale = 1.5;
            this.renderPage(this.pageNum);
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

    async renderPage(num) {
        if (this.pageRendering) {
            this.pageNumPending = num;
            return;
        }

        this.pageRendering = true;

        try {
            const page = await this.pdfDoc.getPage(num);
            const viewport = page.getViewport({ scale: this.scale });
            
            // Store current dimensions
            this.currentPageWidth = viewport.width;
            this.currentPageHeight = viewport.height;
            
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');

            canvas.height = viewport.height;
            canvas.width = viewport.width;
            canvas.style.display = 'block';
            canvas.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.5)';

            // Clear previous content
            this.canvasInner.innerHTML = '';

            const renderContext = {
                canvasContext: context,
                viewport: viewport
            };

            await page.render(renderContext).promise;
            
            this.canvasInner.appendChild(canvas);
            this.pageRendering = false;
            
            // Apply pending scroll position if exists (from zoom operation)
            if (this.pendingScrollPosition) {
                const pos = this.pendingScrollPosition;
                this.canvas.scrollLeft = (pos.percentX * this.canvas.scrollWidth) - pos.mouseX;
                this.canvas.scrollTop = (pos.percentY * this.canvas.scrollHeight) - pos.mouseY;
                this.pendingScrollPosition = null;
            }

            // Handle pending page render if queued during rendering
            if (this.pageNumPending !== null) {
                const pending = this.pageNumPending;
                this.pageNumPending = null;
                this.renderPage(pending);
            }
        } catch (error) {
            console.error('Error rendering page:', error);
            this.pageRendering = false;
        }

        this.updatePageInfo();
        this.updateZoomLevel();
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
        this.canvas.scrollTop = 0;
        this.canvas.scrollLeft = 0;
    }

    nextPage() {
        if (this.pageNum >= this.pdfDoc.numPages) return;
        this.pageNum++;
        this.queueRenderPage(this.pageNum);
        this.updateButtons();
        this.canvas.scrollTop = 0;
        this.canvas.scrollLeft = 0;
    }

    zoomIn() {
        const newScale = this.scale * (1 + this.zoomStep);
        if (newScale <= this.maxScale) {
            this.scale = newScale;
            this.queueRenderPage(this.pageNum);
            this.updateZoomLevel();
        }
    }

    zoomOut() {
        const newScale = this.scale * (1 - this.zoomStep);
        if (newScale >= this.minScale) {
            this.scale = newScale;
            this.queueRenderPage(this.pageNum);
            this.updateZoomLevel();
        }
    }

    async fitToWidth() {
        if (!this.pdfDoc) return;
        
        try {
            const page = await this.pdfDoc.getPage(this.pageNum);
            const viewport = page.getViewport({ scale: 1 });
            // Use the actual canvas container width (the scrollable div)
            const containerWidth = this.canvas.clientWidth - 40; // Account for padding
            this.scale = Math.min(this.maxScale, Math.max(this.minScale, containerWidth / viewport.width));
            this.canvas.scrollTop = 0;
            this.canvas.scrollLeft = 0;
            this.queueRenderPage(this.pageNum);
            this.updateZoomLevel();
        } catch (error) {
            console.error('Error fitting to width:', error);
        }
    }

    resetView() {
        if (this.defaultScale === null) {
            // If default wasn't set yet, recalculate fit-to-width
            this.fitToWidth();
        } else {
            this.scale = this.defaultScale;
            this.canvas.scrollTop = 0;
            this.canvas.scrollLeft = 0;
            this.queueRenderPage(this.pageNum);
            this.updateZoomLevel();
        }
    }

    updateButtons() {
        if (!this.pdfDoc) return;
        this.prevBtn.disabled = this.pageNum <= 1;
        this.nextBtn.disabled = this.pageNum >= this.pdfDoc.numPages;
    }

    updatePageInfo() {
        if (!this.pdfDoc) return;
        this.pageInfo.textContent = `Page ${this.pageNum} of ${this.pdfDoc.numPages}`;
    }

    updateZoomLevel() {
        if (!this.zoomLevel) return;
        const percent = Math.round(this.scale * 100);
        this.zoomLevel.textContent = `${percent}%`;
    }

    destroy() {
        if (this.canvasInner) {
            this.canvasInner.innerHTML = '';
        }
        this.pdfDoc = null;
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