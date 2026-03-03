/**
 * LocalPDFVault - AI-Powered Document Search
 * Main application JavaScript
 */

// State
let allResults = [];
let currentFilter = 'all';
let currentHash = null;
let searchTimeout = null;
let currentSearchQuery = '';
let selectedDocuments = new Set();

// Pagination state
let currentPage = 0;
let pageSize = 50;
let totalCount = 0;
let hasMore = false;

// Filter state
let currentSortBy = 'relevance';
let currentSortOrder = 'desc';
let currentFilters = {
    type: '',
    sender: '',
    dateFrom: '',
    dateTo: ''
};

// Layout Management
let panelSizes = {};

// Periodic status polling
let statusPollingInterval = null;

// Keyboard navigation
let selectedIndex = -1;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadLayoutPreferences();
    loadQueryFromUrl();
    setupEventListeners();
    setupResizers();
    setupModalHandlers();
    setupKeyboardShortcuts();
    loadDocumentTypes();
    startStatusPolling();
});

// Keyboard Shortcuts
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ignore if typing in input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
            if (e.key === 'Escape') {
                e.target.blur();
            }
            return;
        }

        // / - Focus search
        if (e.key === '/') {
            e.preventDefault();
            document.getElementById('searchInput').focus();
        }
        
        // G - Open admin panel
        if (e.key === 'g' || e.key === 'G') {
            e.preventDefault();
            openAdminPanel();
        }
        
        // Escape - Close modal or clear search
        if (e.key === 'Escape') {
            if (document.getElementById('adminModal').classList.contains('active')) {
                closeAdminPanel();
            } else if (document.getElementById('searchInput').value) {
                document.getElementById('searchInput').value = '';
                document.getElementById('searchClear').style.display = 'none';
                loadDocuments('');
            }
        }
        
        // Arrow navigation
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            navigateResults(e.key === 'ArrowDown' ? 1 : -1);
        }
        
        // Enter - Open selected document
        if (e.key === 'Enter' && selectedIndex >= 0) {
            const results = document.querySelectorAll('.result-card');
            if (results[selectedIndex]) {
                results[selectedIndex].click();
            }
        }
    });
}

function navigateResults(direction) {
    const results = document.querySelectorAll('.result-card');
    if (results.length === 0) return;
    
    // Remove previous selection
    results.forEach(r => r.classList.remove('keyboard-selected'));
    
    // Calculate new index
    selectedIndex += direction;
    if (selectedIndex < 0) selectedIndex = results.length - 1;
    if (selectedIndex >= results.length) selectedIndex = 0;
    
    // Highlight and scroll into view
    results[selectedIndex].classList.add('keyboard-selected');
    results[selectedIndex].scrollIntoView({ block: 'nearest' });
}

// URL query parameter handling
function loadQueryFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const query = params.get('q') || '';
    document.getElementById('searchInput').value = query;
    
    // Load filters from URL
    currentFilters.type = params.get('type') || '';
    currentFilters.sender = params.get('sender') || '';
    currentFilters.dateFrom = params.get('from') || '';
    currentFilters.dateTo = params.get('to') || '';
    currentSortBy = params.get('sort') || 'relevance';
    currentSortOrder = params.get('order') || 'desc';
    
    // Apply filter values to UI
    if (currentFilters.type) document.getElementById('filterType').value = currentFilters.type;
    if (currentFilters.sender) document.getElementById('filterSender').value = currentFilters.sender;
    if (currentFilters.dateFrom) document.getElementById('filterDateFrom').value = currentFilters.dateFrom;
    if (currentFilters.dateTo) document.getElementById('filterDateTo').value = currentFilters.dateTo;
    document.getElementById('sortBy').value = currentSortBy;
    document.getElementById('sortOrderBtn').textContent = currentSortOrder === 'desc' ? '↓' : '↑';
    
    loadDocuments(query);
}

function updateUrlWithQuery(query) {
    const url = new URL(window.location);
    
    // Set or clear parameters
    if (query && query.trim()) {
        url.searchParams.set('q', query);
    } else {
        url.searchParams.delete('q');
    }
    
    // Add filters
    if (currentFilters.type) url.searchParams.set('type', currentFilters.type);
    else url.searchParams.delete('type');
    
    if (currentFilters.sender) url.searchParams.set('sender', currentFilters.sender);
    else url.searchParams.delete('sender');
    
    if (currentFilters.dateFrom) url.searchParams.set('from', currentFilters.dateFrom);
    else url.searchParams.delete('from');
    
    if (currentFilters.dateTo) url.searchParams.set('to', currentFilters.dateTo);
    else url.searchParams.delete('to');
    
    url.searchParams.set('sort', currentSortBy);
    url.searchParams.set('order', currentSortOrder);
    
    window.history.replaceState({}, '', url);
}

// LocalStorage keys
const RECENT_SEARCHES_KEY = 'pdfScanner_recentSearches';
const SELECTED_DOC_KEY = 'pdfScanner_selectedDocument';
const MAX_RECENT_SEARCHES = 8;

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
    searches = searches.filter(s => s.toLowerCase() !== query.toLowerCase());
    searches.unshift(query);
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
    saveRecentSearch(query);
}

// Event Listeners
function setupEventListeners() {
    const searchInput = document.getElementById('searchInput');
    const searchClear = document.getElementById('searchClear');
    
    searchInput.addEventListener('input', (e) => {
        searchClear.style.display = e.target.value ? 'block' : 'none';
        
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            currentPage = 0;
            loadDocuments(e.target.value);
        }, 300);
    });

    searchClear.addEventListener('click', () => {
        searchInput.value = '';
        searchClear.style.display = 'none';
        searchInput.focus();
        currentPage = 0;
        loadDocuments('');
    });

    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && searchInput.value.trim()) {
            saveRecentSearch(searchInput.value.trim());
        }
        if (e.key === 'Escape') {
            searchInput.value = '';
            searchClear.style.display = 'none';
            currentPage = 0;
            loadDocuments('');
        }
    });

    searchInput.addEventListener('focus', () => {
        if (!searchInput.value.trim()) {
            renderRecentSearches();
        }
    });

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
            currentPage = 0;
            applyFilter();
        }
    });
    
    // Sort order toggle
    document.getElementById('sortOrderBtn').addEventListener('click', () => {
        currentSortOrder = currentSortOrder === 'desc' ? 'asc' : 'desc';
        document.getElementById('sortOrderBtn').textContent = currentSortOrder === 'desc' ? '↓' : '↑';
        currentPage = 0;
        loadDocuments(currentSearchQuery);
    });
    
    // Sort by change
    document.getElementById('sortBy').addEventListener('change', (e) => {
        currentSortBy = e.target.value;
        currentPage = 0;
        loadDocuments(currentSearchQuery);
    });
}

function setupModalHandlers() {
    const modal = document.getElementById('adminModal');
    
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.classList.contains('active')) {
            closeAdminPanel();
        }
    });
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeAdminPanel();
        }
    });
}

// Filter Functions
function toggleFilters() {
    const filters = document.getElementById('advancedFilters');
    const btn = document.getElementById('filterToggleBtn');
    if (filters.style.display === 'none' || !filters.style.display) {
        filters.style.display = 'block';
        btn.textContent = '▼ Filters';
    } else {
        filters.style.display = 'none';
        btn.textContent = '⚙️ Filters';
    }
}

function applyFilters() {
    currentFilters.type = document.getElementById('filterType').value;
    currentFilters.sender = document.getElementById('filterSender').value;
    currentFilters.dateFrom = document.getElementById('filterDateFrom').value;
    currentFilters.dateTo = document.getElementById('filterDateTo').value;
    currentPage = 0;
    loadDocuments(currentSearchQuery);
}

function clearFilters() {
    document.getElementById('filterType').value = '';
    document.getElementById('filterSender').value = '';
    document.getElementById('filterDateFrom').value = '';
    document.getElementById('filterDateTo').value = '';
    currentFilters = { type: '', sender: '', dateFrom: '', dateTo: '' };
    currentPage = 0;
    loadDocuments(currentSearchQuery);
}

async function loadDocumentTypes() {
    try {
        const response = await fetch('/api/document-types');
        const data = await response.json();
        const select = document.getElementById('filterType');
        
        data.types.forEach(type => {
            const option = document.createElement('option');
            option.value = type;
            option.textContent = type;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading document types:', error);
    }
}

// Pagination
function prevPage() {
    if (currentPage > 0) {
        currentPage--;
        loadDocuments(currentSearchQuery);
    }
}

function nextPage() {
    if (hasMore) {
        currentPage++;
        loadDocuments(currentSearchQuery);
    }
}

function renderPagination() {
    const pagination = document.getElementById('pagination');
    const pageInfo = document.getElementById('pageInfo');
    const prevBtn = document.getElementById('prevPage');
    const nextBtn = document.getElementById('nextPage');
    
    if (totalCount > pageSize) {
        pagination.style.display = 'flex';
        const start = currentPage * pageSize + 1;
        const end = Math.min((currentPage + 1) * pageSize, totalCount);
        pageInfo.textContent = `${start}-${end} of ${totalCount}`;
        prevBtn.disabled = currentPage === 0;
        nextBtn.disabled = !hasMore;
    } else {
        pagination.style.display = 'none';
    }
}

// Load Documents
async function loadDocuments(query = '') {
    currentSearchQuery = query;
    updateUrlWithQuery(query);
    
    try {
        // Build query params
        const params = new URLSearchParams();
        if (query) params.set('q', query);
        params.set('limit', pageSize);
        params.set('offset', currentPage * pageSize);
        params.set('sort_by', currentSortBy);
        params.set('sort_order', currentSortOrder);
        if (currentFilters.type) params.set('document_type', currentFilters.type);
        if (currentFilters.sender) params.set('sender', currentFilters.sender);
        if (currentFilters.dateFrom) params.set('date_from', currentFilters.dateFrom);
        if (currentFilters.dateTo) params.set('date_to', currentFilters.dateTo);
        
        const response = await fetch(`/api/search?${params.toString()}`);
        const data = await response.json();
        
        allResults = data.results || data;  // Handle both paginated and old format
        totalCount = data.total || allResults.length;
        hasMore = data.has_more || false;

        updateFilters();
        applyFilter();
        
        if (query) {
            document.getElementById('recentSearches').style.display = 'none';
        }
        
        // Restore selection
        const savedHash = loadSelectedDocument();
        if (savedHash && allResults.some(r => r.file_hash === savedHash)) {
            showDocument(savedHash);
        }
        
        renderPagination();
    } catch (error) {
        console.error('Error loading documents:', error);
        showToast('Error loading documents', 'error');
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
    // Server-side filtering is already applied, just display results
    displayResults(allResults);
}

function displayResults(results) {
    const container = document.getElementById('resultsList');
    const countEl = document.getElementById('resultsCount');

    countEl.textContent = `${totalCount} document${totalCount !== 1 ? 's' : ''}`;

    if (results.length === 0) {
        container.innerHTML = `
            <div class="no-results">
                <div class="no-results-icon">📭</div>
                <p>No documents found</p>
            </div>
        `;
        return;
    }

    container.innerHTML = results.map((result, index) => {
        const filename = result.filename.split(/[/\\]/).pop();
        const tags = (result.tags || []).slice(0, 4);
        const matches = result.search_matches || [];
        const relevanceScore = result.relevance_score || 0;
        const showScore = currentSearchQuery && currentSearchQuery.trim() && relevanceScore > 0;
        const matchPercent = showScore ? getMatchPercent(relevanceScore) : { show: false };
        const isSelected = selectedDocuments.has(result.file_hash);

        return `
            <div class="result-card ${result.file_hash === currentHash ? 'active' : ''}"
                 data-index="${index}"
                 onclick="showDocument('${result.file_hash}')">
                <div class="result-checkbox">
                    <input type="checkbox" 
                           ${isSelected ? 'checked' : ''} 
                           onclick="event.stopPropagation(); toggleSelect('${result.file_hash}')"
                           title="Select for bulk action">
                </div>
                <div class="result-content">
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
            </div>
        `;
    }).join('');
}

// Bulk Selection (for export only)
function toggleSelect(hash) {
    if (selectedDocuments.has(hash)) {
        selectedDocuments.delete(hash);
    } else {
        selectedDocuments.add(hash);
    }
    updateBulkActions();
    applyFilter();
}

function toggleSelectAll() {
    const selectAll = document.getElementById('selectAll');
    if (selectAll.checked) {
        allResults.forEach(r => selectedDocuments.add(r.file_hash));
    } else {
        selectedDocuments.clear();
    }
    updateBulkActions();
    applyFilter();
}

function clearSelection() {
    selectedDocuments.clear();
    document.getElementById('selectAll').checked = false;
    updateBulkActions();
    applyFilter();
}

function updateBulkActions() {
    const bulkActions = document.getElementById('bulkActions');
    const selectedCount = document.getElementById('selectedCount');
    
    if (selectedDocuments.size > 0) {
        bulkActions.style.display = 'flex';
        selectedCount.textContent = `${selectedDocuments.size} selected`;
    } else {
        bulkActions.style.display = 'none';
    }
}

// Export (CSV only)
async function exportResults(format) {
    if (format === 'json') {
        showToast('JSON export not available', 'error');
        return;
    }
    
    try {
        showToast('Exporting...', 'info');
        
        const response = await fetch(`/api/export?format=csv`);
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `documents_${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        
        showToast('Export complete', 'success');
    } catch (error) {
        console.error('Export error:', error);
        showToast('Export failed', 'error');
    }
}

// Toast Notifications
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('toast-fade');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Admin Panel Functions
function openAdminPanel() {
    document.getElementById('adminModal').classList.add('active');
    loadStats();
    loadSystemConfig();
    loadWatchStatus();
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
        document.getElementById('vaultDisplay').textContent = config.vault_path || '/data/pdfs';
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

async function loadWatchStatus() {
    try {
        const response = await fetch('/api/admin/watch/status');
        const status = await response.json();
        
        const statusText = document.getElementById('watchStatusText');
        const toggleBtn = document.getElementById('watchToggleBtn');
        
        if (status.enabled) {
            statusText.textContent = status.running ? 'Watch mode active' : 'Watch mode enabled (not running)';
            toggleBtn.textContent = 'Stop';
            toggleBtn.onclick = stopWatchMode;
        } else {
            statusText.textContent = 'Watch mode disabled in config';
            toggleBtn.style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading watch status:', error);
    }
}

async function toggleWatchMode() {
    try {
        const response = await fetch('/api/admin/watch/start', { method: 'POST' });
        const result = await response.json();
        
        if (result.success) {
            showToast('Watch mode started', 'success');
        } else {
            showToast(result.error || 'Failed to start watch mode', 'error');
        }
        loadWatchStatus();
    } catch (error) {
        showToast('Error starting watch mode', 'error');
    }
}

async function stopWatchMode() {
    try {
        const response = await fetch('/api/admin/watch/stop', { method: 'POST' });
        const result = await response.json();
        showToast('Watch mode stopped', 'info');
        loadWatchStatus();
    } catch (error) {
        showToast('Error stopping watch mode', 'error');
    }
}

async function loadTotalDocs(statusData = null) {
    try {
        const [stats, status] = statusData
            ? [await fetch('/api/stats').then(r => r.json()), statusData]
            : await Promise.all([
                fetch('/api/stats').then(r => r.json()),
                fetch('/api/admin/index/status').then(r => r.json())
            ]);
        
        const totalDocsEl = document.getElementById('totalDocs');
        if (status.is_running) {
            totalDocsEl.textContent = `Currently indexing... (${stats.total} documents indexed so far)`;
            totalDocsEl.style.color = 'var(--primary)';
            totalDocsEl.style.fontWeight = '500';
        } else {
            totalDocsEl.textContent = `Current index has ${stats.total} total documents`;
            totalDocsEl.style.color = '';
            totalDocsEl.style.fontWeight = '';
        }
    } catch (error) {
        console.error('Error loading total docs:', error);
    }
}

function startStatusPolling() {
    if (statusPollingInterval) {
        clearInterval(statusPollingInterval);
    }
    
    checkIndexingStatus();
    checkOllamaStatus();
    
    statusPollingInterval = setInterval(() => {
        checkIndexingStatus();
        checkOllamaStatus();
    }, 5000);
}

async function checkIndexingStatus() {
    try {
        const response = await fetch('/api/admin/index/status');
        const status = await response.json();
        
        await loadTotalDocs(status);
        
        if (status.is_running) {
            if (document.getElementById('indexProgress').style.display !== 'block') {
                document.getElementById('indexProgress').style.display = 'block';
                document.getElementById('stopBtn').style.display = 'inline-block';
                
                const indexBtn = document.getElementById('indexBtn');
                indexBtn.disabled = true;
                indexBtn.innerHTML = '⏳ Processing...';
                
                const headerBtn = document.getElementById('headerIndexBtn');
                if (headerBtn) {
                    headerBtn.disabled = true;
                    headerBtn.innerHTML = '⏳ Processing...';
                }
            }
            
            const progressBarContainer = document.querySelector('.progress-bar-container');
            if (status.total > 0) {
                progressBarContainer.classList.remove('indeterminate');
                document.getElementById('progressStatus').textContent = 'Updating Index...';
                document.getElementById('progressCount').textContent =
                    `${status.processed}/${status.total} (${status.skipped} skipped, ${status.errors} errors)`;
            } else {
                progressBarContainer.classList.add('indeterminate');
                document.getElementById('progressStatus').textContent = 'Scanning Vault...';
                document.getElementById('progressCount').textContent = 'Discovering PDF files...';
            }
            
            const pct = status.total > 0 ? (status.processed / status.total * 100) : 0;
            if (status.total > 0) {
                document.getElementById('progressBar').style.width = pct + '%';
            } else {
                document.getElementById('progressBar').style.width = '100%';
            }

            document.getElementById('progressFile').textContent = status.current_file || '-';
            
        } else {
            if (document.getElementById('indexProgress').style.display === 'block') {
                document.getElementById('indexProgress').style.display = 'none';
                document.getElementById('stopBtn').style.display = 'none';
                
                const indexBtn = document.getElementById('indexBtn');
                indexBtn.disabled = false;
                indexBtn.innerHTML = '🔄 Update Index';
                
                const headerBtn = document.getElementById('headerIndexBtn');
                if (headerBtn) {
                    headerBtn.disabled = false;
                    headerBtn.innerHTML = '🔄 Update';
                }
                
                document.getElementById('stopBtn').disabled = false;
                document.getElementById('stopBtn').innerHTML = 'Stop';
                
                loadStats();
                loadDocuments(currentSearchQuery);
            }
        }

    } catch (error) {
        console.error('Error checking indexing status:', error);
    }
}

async function checkOllamaStatus() {
    try {
        const response = await fetch('/api/ollama/status');
        const status = await response.json();
        const statusEl = document.getElementById('ollamaStatus');
        
        if (status.status === 'running') {
            if (status.model_available) {
                statusEl.innerHTML = `Ollama: <span style="color: #22c55e; font-weight: 500;">● Ready</span>`;
                statusEl.title = `Connected to ${status.url}\nModel: ${status.model} (available)`;
            } else {
                statusEl.innerHTML = `Ollama: <span style="color: #f59e0b; font-weight: 500;">● Model Missing</span>`;
                statusEl.title = `Connected to ${status.url}\nRequired model not found: ${status.model}`;
            }
        } else if (status.status === 'offline') {
            statusEl.innerHTML = `Ollama: <span style="color: #ef4444; font-weight: 500;">● Offline</span>`;
            statusEl.title = `Cannot connect to ${status.url}\nRequired model: ${status.model}`;
        } else {
            statusEl.innerHTML = `Ollama: <span style="color: #f59e0b; font-weight: 500;">● Error</span>`;
            statusEl.title = `Error: ${status.error}\nRequired model: ${status.model}`;
        }
    } catch (error) {
        console.error('Error checking Ollama status:', error);
    }
}

let indexingInterval = null;

async function startIndexing() {
    const btn = document.getElementById('indexBtn');
    const headerBtn = document.getElementById('headerIndexBtn');
    
    btn.disabled = true;
    btn.innerHTML = '⏳ Initializing...';
    if (headerBtn) {
        headerBtn.disabled = true;
        headerBtn.innerHTML = '⏳...';
    }

    try {
        const response = await fetch('/api/admin/index', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });

        const result = await response.json();
        
        if (result.success) {
            showToast('Indexing started', 'success');
            await checkIndexingStatus();
        } else {
            showToast(result.error || 'Error starting indexing', 'error');
            btn.disabled = false;
            btn.innerHTML = '🔄 Update Index';
            if (headerBtn) {
                headerBtn.disabled = false;
                headerBtn.innerHTML = '🔄 Update';
            }
        }
    } catch (error) {
        showToast('Error starting indexing', 'error');
        btn.disabled = false;
        btn.innerHTML = '🔄 Update Index';
        if (headerBtn) {
            headerBtn.disabled = false;
            headerBtn.innerHTML = '🔄 Update';
        }
    }
}

async function startReindexing() {
    const btn = document.getElementById('indexBtn');
    const headerBtn = document.getElementById('headerIndexBtn');
    
    btn.disabled = true;
    btn.innerHTML = '⏳ Initializing...';
    if (headerBtn) {
        headerBtn.disabled = true;
        headerBtn.innerHTML = '⏳...';
    }

    try {
        const response = await fetch('/api/admin/index', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ force: true })
        });

        const result = await response.json();
        
        if (result.success) {
            showToast('Reindexing started', 'success');
            await checkIndexingStatus();
        } else {
            showToast(result.error || 'Error starting reindexing', 'error');
            btn.disabled = false;
            btn.innerHTML = '🔄 Update Index';
            if (headerBtn) {
                headerBtn.disabled = false;
                headerBtn.innerHTML = '🔄 Update';
            }
        }
    } catch (error) {
        showToast('Error starting reindexing', 'error');
        btn.disabled = false;
        btn.innerHTML = '🔄 Update Index';
        if (headerBtn) {
            headerBtn.disabled = false;
            headerBtn.innerHTML = '🔄 Update';
        }
    }
}

async function stopIndexing() {
    try {
        const response = await fetch('/api/admin/index/stop', { method: 'POST' });
        const result = await response.json();

        if (result.success) {
            document.getElementById('stopBtn').disabled = true;
            document.getElementById('stopBtn').innerHTML = 'Stopping...';
            showToast('Stop signal sent', 'info');
        } else {
            showToast(result.error || 'Error stopping indexing', 'error');
        }
    } catch (error) {
        showToast('Error stopping indexing', 'error');
    }
}

async function clearAndRescan() {
    if (!confirm(`Re-analyze all PDFs in your vault?\n\nThis will scan all documents again with fresh AI analysis.\n\nYour PDF files will NOT be modified - only the search index will be updated.\n\nThis may take a while. Continue?`)) return;
    
    // Just trigger a full reindex (force=true)
    const btn = document.getElementById('indexBtn');
    const headerBtn = document.getElementById('headerIndexBtn');
    
    btn.disabled = true;
    btn.innerHTML = '⏳ Starting...';
    if (headerBtn) {
        headerBtn.disabled = true;
        headerBtn.innerHTML = '⏳...';
    }

    try {
        const response = await fetch('/api/admin/index', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ force: true })
        });

        const result = await response.json();
        
        if (result.success) {
            showToast('Re-indexing started', 'success');
            checkIndexingStatus();
        } else {
            showToast(result.error || 'Error starting re-index', 'error');
            btn.disabled = false;
            btn.innerHTML = '🔄 Update Index';
            if (headerBtn) {
                headerBtn.disabled = false;
                headerBtn.innerHTML = '🔄 Update';
            }
        }
    } catch (error) {
        showToast('Error starting re-index', 'error');
        btn.disabled = false;
        btn.innerHTML = '🔄 Update Index';
        if (headerBtn) {
            headerBtn.disabled = false;
            headerBtn.innerHTML = '🔄 Update';
        }
    }
}

function showDocument(hash) {
    const result = allResults.find(r => r.file_hash === hash);
    if (!result) return;
    
    currentHash = hash;
    selectedIndex = allResults.findIndex(r => r.file_hash === hash);
    saveSelectedDocument(hash);
    
    // Update active state in list
    document.querySelectorAll('.result-card').forEach(card => {
        card.classList.toggle('active', card.dataset.index == selectedIndex);
    });
    
    const filename = result.filename.split(/[/\\]/).pop();
    const tags = result.tags || [];
    
    // Update details panel
    document.getElementById('detailsPanel').innerHTML = `
            <div class="details-header">
                <div class="details-title">${escapeHtml(filename)}</div>
                <div class="details-actions">
                    <a href="/api/pdf/${hash}" target="_blank" class="btn btn-primary btn-sm">
                        📄 Open in New Tab
                    </a>
                    <button class="btn btn-secondary btn-sm" onclick="copyPath('${escapeHtml(result.file_path || result.filename).replace(/'/g, "\\'")}')">
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
                📁 ${escapeHtml(result.file_path || result.filename)}
            </div>
        </div>
    `;
    
    // Update preview panel
    document.getElementById('previewPanel').innerHTML = `
        <div class="preview-header">PDF Preview - Drag to pan • Ctrl+Scroll to zoom • Scroll to navigate</div>
        <div class="pdfjs-container">
            <div class="pdfjs-toolbar">
                <button onclick="pdfViewer.prevPage()" id="prevBtn" disabled>← Previous page</button>
                <button onclick="pdfViewer.nextPage()" id="nextBtn" disabled>Next page →</button>
                <button onclick="pdfViewer.zoomOut()">🔍−</button>
                <span class="zoom-level" id="zoomLevel">100%</span>
                <button onclick="pdfViewer.zoomIn()">🔍+</button>
                <button onclick="pdfViewer.fitToWidth()">↔ Fit Width</button>
                <button onclick="pdfViewer.fitToHeight()">↕ Fit Height</button>
                <span class="page-info" id="pageInfo">Loading...</span>
            </div>
            <div class="pdfjs-canvas" id="pdfCanvas">
                <div class="pdfjs-canvas-inner" id="pdfCanvasInner"></div>
                <div class="pdfjs-scroll-hint">🖱️ Drag to pan • Ctrl+Scroll to zoom • Scroll to navigate</div>
            </div>
        </div>
    `;

    if (window.pdfViewer) {
        window.pdfViewer.destroy();
    }
    window.pdfViewer = new PDFViewer(hash);
}

function copyPath(path) {
    navigator.clipboard.writeText(path).then(() => {
        showToast('Path copied to clipboard', 'success');
    });
}

function getMatchPercent(score) {
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

// PDF.js Viewer Class
class PDFViewer {
    constructor(hash) {
        this.hash = hash;
        this.pdfDoc = null;
        this.pageNum = 1;
        this.pageRendering = false;
        this.pageNumPending = null;
        
        this.scale = null;
        this.defaultScale = null;
        this.minScale = 0.25;
        this.maxScale = 5.0;
        this.zoomStep = 0.15;
        
        this.canvas = document.getElementById('pdfCanvas');
        this.canvasInner = document.getElementById('pdfCanvasInner');
        this.prevBtn = document.getElementById('prevBtn');
        this.nextBtn = document.getElementById('nextBtn');
        this.pageInfo = document.getElementById('pageInfo');
        this.zoomLevel = document.getElementById('zoomLevel');
        
        this.currentPageWidth = 0;
        this.currentPageHeight = 0;
        
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
        
        container.addEventListener('mousedown', (e) => {
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
        
        container.addEventListener('mouseenter', () => {
            if (!this.isDragging &&
                (container.scrollWidth > container.clientWidth ||
                 container.scrollHeight > container.clientHeight)) {
                container.style.cursor = 'grab';
            }
        });
        
        container.addEventListener('wheel', (e) => {
            if (e.ctrlKey) {
                e.preventDefault();
                
                const rect = container.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const mouseY = e.clientY - rect.top;
                
                const scrollXPercent = (container.scrollLeft + mouseX) / container.scrollWidth;
                const scrollYPercent = (container.scrollTop + mouseY) / container.scrollHeight;
                
                if (e.deltaY < 0) {
                    this.zoomIn();
                } else {
                    this.zoomOut();
                }
                
                this.pendingScrollPosition = {
                    percentX: scrollXPercent,
                    percentY: scrollYPercent,
                    mouseX: mouseX,
                    mouseY: mouseY
                };
            }
        }, { passive: false });
        
        document.addEventListener('keydown', (e) => {
            if (!this.pdfDoc) return;
            
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
            if (!window.pdfjsLib) {
                await this.loadPDFJS();
            }

            const loadingTask = pdfjsLib.getDocument(`/api/pdf/${this.hash}`);
            this.pdfDoc = await loadingTask.promise;

            this.updatePageInfo();
            this.updateButtons();

            await this.calculateAndRenderFitToWidth();

            const observer = new MutationObserver(() => {
                observer.disconnect();
                requestAnimationFrame(() => {
                    this.fitToHeight();
                });
            });
            observer.observe(this.canvasInner, { childList: true });
        } catch (error) {
            console.error('Error loading PDF:', error);
            this.pageInfo.textContent = 'Error loading PDF';
        }
    }
    
    async calculateAndRenderFitToWidth() {
        try {
            const page = await this.pdfDoc.getPage(this.pageNum);
            const viewport = page.getViewport({ scale: 1 });

            await new Promise(resolve => requestAnimationFrame(resolve));

            const containerWidth = this.canvas.clientWidth - 40;

            if (containerWidth > 0) {
                const fitScale = Math.min(this.maxScale, Math.max(this.minScale, containerWidth / viewport.width));
                this.scale = fitScale;
                this.defaultScale = fitScale;
            } else {
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

    async calculateAndRenderFitToHeight() {
        try {
            const page = await this.pdfDoc.getPage(this.pageNum);
            const viewport = page.getViewport({ scale: 1 });

            await new Promise(resolve => requestAnimationFrame(resolve));

            const containerHeight = this.canvas.clientHeight - 40;

            if (containerHeight > 0) {
                const fitScale = Math.min(this.maxScale, Math.max(this.minScale, containerHeight / viewport.height));
                this.scale = fitScale;
                this.defaultScale = fitScale;
            } else {
                this.scale = 1.5;
                this.defaultScale = 1.5;
            }

            this.updateZoomLevel();
            this.renderPage(this.pageNum);
        } catch (error) {
            console.error('Error calculating fit-to-height:', error);
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
            
            this.currentPageWidth = viewport.width;
            this.currentPageHeight = viewport.height;
            
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');

            canvas.height = viewport.height;
            canvas.width = viewport.width;
            canvas.style.display = 'block';
            canvas.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.5)';

            this.canvasInner.innerHTML = '';

            const renderContext = {
                canvasContext: context,
                viewport: viewport
            };

            await page.render(renderContext).promise;
            
            this.canvasInner.appendChild(canvas);
            this.pageRendering = false;
            
            if (this.pendingScrollPosition) {
                const pos = this.pendingScrollPosition;
                this.canvas.scrollLeft = (pos.percentX * this.canvas.scrollWidth) - pos.mouseX;
                this.canvas.scrollTop = (pos.percentY * this.canvas.scrollHeight) - pos.mouseY;
                this.pendingScrollPosition = null;
            }

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
            const containerWidth = this.canvas.clientWidth - 40;
            this.scale = Math.min(this.maxScale, Math.max(this.minScale, containerWidth / viewport.width));
            this.canvas.scrollTop = 0;
            this.canvas.scrollLeft = 0;
            this.queueRenderPage(this.pageNum);
            this.updateZoomLevel();
        } catch (error) {
            console.error('Error fitting to width:', error);
        }
    }

    async fitToHeight() {
        if (!this.pdfDoc) return;

        try {
            const page = await this.pdfDoc.getPage(this.pageNum);
            const viewport = page.getViewport({ scale: 1 });
            const containerHeight = this.canvas.clientHeight - 40;
            this.scale = Math.min(this.maxScale, Math.max(this.minScale, containerHeight / viewport.height));
            this.canvas.scrollTop = 0;
            this.canvas.scrollLeft = 0;
            this.queueRenderPage(this.pageNum);
            this.updateZoomLevel();
        } catch (error) {
            console.error('Error fitting to height:', error);
        }
    }

    resetView() {
        if (this.defaultScale === null) {
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
    const panels = document.querySelectorAll('.panel');
    panels.forEach(panel => {
        const panelType = panel.dataset.panel;
        if (panelType === 'preview') return;
        const width = panel.offsetWidth;
        panelSizes[panelType] = width;
    });
    localStorage.setItem('pdfScanner_panelSizes', JSON.stringify(panelSizes));
}

function loadLayoutPreferences() {
    const savedSizes = localStorage.getItem('pdfScanner_panelSizes');
    if (savedSizes) {
        try {
            panelSizes = JSON.parse(savedSizes);
        } catch (e) {
            console.error('Error loading panel sizes:', e);
        }
    }

    Object.entries(panelSizes).forEach(([panelType, size]) => {
        if (panelType === 'preview') return;
        const panel = document.querySelector(`[data-panel="${panelType}"]`);
        if (panel) {
            panel.style.flex = `0 0 ${size}px`;
        }
    });
}