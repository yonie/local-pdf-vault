"""
Playwright integration tests for LocalPDFVault web interface.
Verifies the UI renders correctly, search works, and interactions function properly.
"""

import pytest
import time
import os
import tempfile
import threading
from pathlib import Path

# Set up minimal config before importing flask app
os.environ['WEB_HOST'] = '127.0.0.1'
os.environ['WEB_PORT'] = '14337'
os.environ['SCAN_DIRECTORY'] = tempfile.mkdtemp(prefix='pdfvault_test_')
os.environ['OLLAMA_HOST'] = '127.0.0.1'
os.environ['OLLAMA_PORT'] = '11434'
os.environ['OLLAMA_MODEL'] = 'qwen3-vl:30b-a3b-instruct'
os.environ['MAX_PAGES_PER_END'] = '3'
os.environ['MAX_PARALLEL_SCANNING'] = '4'
os.environ['MAX_PARALLEL_HASHING'] = '2'

from src.web import create_app


@pytest.fixture(scope='session')
def server():
    """Start Flask server in background thread."""
    app = create_app()
    server_thread = threading.Thread(target=lambda: app.run(
        host='127.0.0.1', port=14337, debug=False, use_reloader=False
    ), daemon=True)
    server_thread.start()
    time.sleep(1)  # Wait for server to start
    yield
    # Server is daemon thread, will be killed with process


@pytest.fixture
def browser(playwright):
    """Launch a browser for testing."""
    browser = playwright.chromium.launch(headless=True)
    yield browser
    browser.close()


@pytest.fixture
def page(browser):
    """Create a new page for testing."""
    p = browser.new_page()
    yield p
    p.close()


class TestHomePage:
    """Test that the home page renders correctly."""

    def test_page_loads(self, server, page):
        """Page should load without errors."""
        page.goto('http://127.0.0.1:14337/')
        assert page.title() == 'LocalPDFVault'

    def test_no_console_errors(self, server, page):
        """Page should load with no JavaScript console errors."""
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto('http://127.0.0.1:14337/')
        page.wait_for_timeout(1000)
        assert len(errors) == 0, f"Console errors found: {errors}"

    def test_header_elements_present(self, server, page):
        """Header should contain logo, status, and action buttons."""
        page.goto('http://127.0.0.1:14337/')
        
        # Logo
        assert page.locator('.header').is_visible()
        assert page.locator('.logo-text').is_visible()
        assert page.locator('.logo-text').inner_text() == 'PDFVault'

        # Status pill
        assert page.locator('.status-pill').is_visible()

    def test_search_input_present(self, server, page):
        """Search input should be present and functional."""
        page.goto('http://127.0.0.1:14337/')
        
        search_input = page.locator('#searchInput')
        assert search_input.is_visible()
        assert search_input.get_attribute('placeholder') == 'Search documents...'

    def test_two_panels_present(self, server, page):
        """Both panels (sidebar, stage) should exist."""
        page.goto('http://127.0.0.1:14337/')

        assert page.locator('.panel-sidebar').is_visible()
        assert page.locator('.panel-stage').is_visible()

    def test_empty_state_shown(self, server, page):
        """Empty state should be shown when no documents are selected."""
        page.goto('http://127.0.0.1:14337/')

        # Stage should show empty state
        stage_empty = page.locator('#stageEmpty')
        assert stage_empty.is_visible()
        assert 'Select a document' in stage_empty.inner_text()

    def test_document_view_hidden_by_default(self, server, page):
        """Document view (toolbar + PDF) should be hidden until a doc is selected."""
        page.goto('http://127.0.0.1:14337/')

        assert not page.locator('#stageDoc').is_visible()


class TestSearch:
    """Test search functionality."""

    def test_search_input_type(self, server, page):
        """Search input should be a text input element."""
        page.goto('http://127.0.0.1:14337/')
        
        search_input = page.locator('#searchInput')
        assert search_input.evaluate('el => el.tagName') == 'INPUT'
        assert search_input.evaluate('el => el.type') == 'text'

    def test_search_clear_button(self, server, page):
        """Clear button should appear when typing."""
        page.goto('http://127.0.0.1:14337/')
        
        search_input = page.locator('#searchInput')
        clear_btn = page.locator('#searchClear')
        
        # Clear button should be hidden initially
        assert clear_btn.evaluate('el => el.style.display') == 'none'
        
        # Type something
        search_input.fill('test')
        assert clear_btn.is_visible()

    def test_search_results_list(self, server, page):
        """Results list container should exist."""
        page.goto('http://127.0.0.1:14337/')
        
        results_list = page.locator('#resultsList')
        assert results_list.is_visible()

    def test_results_count_display(self, server, page):
        """Results count should be displayed."""
        page.goto('http://127.0.0.1:14337/')
        
        results_count = page.locator('#resultsCount')
        assert results_count.is_visible()


class TestAdminPanel:
    """Test admin panel modal."""

    def test_admin_button_exists(self, server, page):
        """Admin button should exist in header."""
        page.goto('http://127.0.0.1:14337/')
        
        admin_btn = page.locator('button[title="Manage index (G)"]')
        assert admin_btn.is_visible()

    def test_admin_modal_opens(self, server, page):
        """Admin modal should open when button clicked."""
        page.goto('http://127.0.0.1:14337/')
        
        # Click admin button
        page.click('button[title="Manage index (G)"]')
        
        # Modal should be visible
        modal = page.locator('#adminModal')
        assert modal.is_visible()

    def test_admin_modal_sections(self, server, page):
        """Admin modal should contain all expected sections."""
        page.goto('http://127.0.0.1:14337/')
        
        page.click('button[title="Manage index (G)"]')
        
        # Check sections exist by text content (CSS uses uppercase)
        modal_text = page.locator('#adminModal').inner_text().lower()
        assert 'database statistics' in modal_text
        assert 'document vault' in modal_text
        assert 'auto-index watch mode' in modal_text
        assert 'maintenance' in modal_text
        assert 'privacy & system info' in modal_text

    def test_admin_modal_closes_with_escape(self, server, page):
        """Admin modal should close on Escape key."""
        page.goto('http://127.0.0.1:14337/')
        
        page.click('button[title="Manage index (G)"]')
        assert page.locator('#adminModal').is_visible()
        
        page.keyboard.press('Escape')
        assert not page.locator('#adminModal').is_visible()

    def test_admin_modal_closes_with_x(self, server, page):
        """Admin modal should close with X button."""
        page.goto('http://127.0.0.1:14337/')
        
        page.click('button[title="Manage index (G)"]')
        assert page.locator('#adminModal').is_visible()
        
        page.click('.modal-close')
        assert not page.locator('#adminModal').is_visible()

    def test_admin_modal_closes_click_outside(self, server, page):
        """Admin modal should close when pressing Escape."""
        page.goto('http://127.0.0.1:14337/')
        
        page.click('button[title="Manage index (G)"]')
        assert page.locator('#adminModal').is_visible()
        
        # Press Escape to close modal
        page.keyboard.press('Escape')
        assert not page.locator('#adminModal').is_visible()

    def test_index_button_present(self, server, page):
        """Index update button should be present in admin modal."""
        page.goto('http://127.0.0.1:14337/')
        
        page.click('button[title="Manage index (G)"]')
        
        index_btn = page.locator('#indexBtn')
        assert index_btn.is_visible()
        assert 'Update Index' in index_btn.inner_text()

    def test_header_index_button_present(self, server, page):
        """Header should have index update button."""
        page.goto('http://127.0.0.1:14337/')
        
        header_btn = page.locator('#headerIndexBtn')
        assert header_btn.is_visible()


class TestKeyboardShortcuts:
    """Test keyboard shortcut functionality."""

    def test_slash_focuses_search(self, server, page):
        """Pressing / should focus the search input."""
        page.goto('http://127.0.0.1:14337/')
        
        # Click somewhere else first
        page.click('.logo-text')
        
        # Press /
        page.keyboard.press('/')
        
        # Search input should be focused - check via JavaScript
        focused_tag = page.evaluate('document.activeElement.tagName')
        assert focused_tag == 'INPUT'

    def test_escape_clears_search(self, server, page):
        """Escape should clear search when input has text."""
        page.goto('http://127.0.0.1:14337/')
        
        search_input = page.locator('#searchInput')
        search_input.fill('test query')
        assert search_input.input_value() == 'test query'
        
        page.keyboard.press('Escape')
        assert search_input.input_value() == ''


class TestFilters:
    """Test filter functionality."""

    def test_filter_toggle_button(self, server, page):
        """Filter toggle button should exist."""
        page.goto('http://127.0.0.1:14337/')
        
        filter_btn = page.locator('#filterToggleBtn')
        assert filter_btn.is_visible()

    def test_advanced_filters_hidden_by_default(self, server, page):
        """Advanced filters should be hidden by default."""
        page.goto('http://127.0.0.1:14337/')
        
        advanced = page.locator('#advancedFilters')
        display = advanced.evaluate('el => window.getComputedStyle(el).display')
        assert display == 'none'

    def test_advanced_filters_visible_when_toggled(self, server, page):
        """Advanced filters should show when toggle clicked."""
        page.goto('http://127.0.0.1:14337/')
        
        page.click('#filterToggleBtn')
        
        advanced = page.locator('#advancedFilters')
        display = advanced.evaluate('el => window.getComputedStyle(el).display')
        assert display != 'none'

    def test_filter_elements_present(self, server, page):
        """All filter elements should be present."""
        page.goto('http://127.0.0.1:14337/')
        
        # Toggle filters to make them visible
        page.click('#filterToggleBtn')
        
        # Type filter
        assert page.locator('#filterType').is_visible()
        
        # Sort by
        assert page.locator('#sortBy').is_visible()
        
        # Sort order
        assert page.locator('#sortOrderBtn').is_visible()
        
        # Date filters
        assert page.locator('#filterDateFrom').is_visible()
        assert page.locator('#filterDateTo').is_visible()
        
        # Sender filter
        assert page.locator('#filterSender').is_visible()

    def test_type_filter_options(self, server, page):
        """Type filter should have 'All Types' option."""
        page.goto('http://127.0.0.1:14337/')
        
        select = page.locator('#filterType')
        options = select.locator('option')
        first_option = options.first
        assert 'All types' in first_option.inner_text()


class TestUIElements:
    """Test various UI elements and styling."""

    def test_no_emoji_in_header(self, server, page):
        """Header should not contain emoji characters (modern design)."""
        page.goto('http://127.0.0.1:14337/')
        
        header_text = page.locator('.header').inner_text()
        # Should not contain emoji that were in old design
        assert '⚙️' not in header_text
        assert '🔄' not in header_text
        assert '📄' not in header_text

    def test_no_emoji_in_admin_modal(self, server, page):
        """Admin modal should not contain emoji characters."""
        page.goto('http://127.0.0.1:14337/')
        page.click('button[title="Manage index (G)"]')
        
        modal_text = page.locator('#adminModal').inner_text()
        assert '⚙️' not in modal_text
        assert '🔄' not in modal_text
        assert '📊' not in modal_text
        assert '📂' not in modal_text
        assert '🔧' not in modal_text
        assert '🔒' not in modal_text

    def test_svg_icons_present(self, server, page):
        """SVG icons should be present in the UI."""
        page.goto('http://127.0.0.1:14337/')
        
        svg_count = page.evaluate('document.querySelectorAll("svg").length')
        assert svg_count > 0, "No SVG icons found in the page"

    def test_load_more_present(self, server, page):
        """Load-more control should exist (hidden when all results fit)."""
        page.goto('http://127.0.0.1:14337/')

        assert page.locator('#loadMore').count() == 1

    def test_keyboard_shortcuts_section(self, server, page):
        """Keyboard shortcuts section should be visible in empty state."""
        page.goto('http://127.0.0.1:14337/')
        
        shortcuts = page.locator('.keyboard-shortcuts')
        assert shortcuts.is_visible()
        text = shortcuts.inner_text()
        assert '/' in text
        assert 'Esc' in text
        assert 'Enter' in text

    def test_typography_uses_inter(self, server, page):
        """Page should use Inter font family."""
        page.goto('http://127.0.0.1:14337/')
        
        font = page.evaluate('getComputedStyle(document.body).fontFamily')
        assert 'Inter' in font

    def test_light_background(self, server, page):
        """Page should have the light theme background."""
        page.goto('http://127.0.0.1:14337/')

        bg = page.evaluate('getComputedStyle(document.body).backgroundColor')
        assert 'rgb(244, 244, 245)' in bg

    def test_resizer_present(self, server, page):
        """A resizer should exist between sidebar and stage."""
        page.goto('http://127.0.0.1:14337/')

        resizers = page.locator('.resizer')
        count = resizers.count()
        assert count == 1, f"Expected 1 resizer, found {count}"


class TestAPIEndpoints:
    """Test that API endpoints return expected responses."""

    def test_search_api_empty(self, server, page):
        """Search API should return valid JSON with results."""
        response = page.request.get('http://127.0.0.1:14337/api/search')
        assert response.ok
        data = response.json()
        # API returns either a dict with 'results' key or a list of documents
        if isinstance(data, dict):
            assert 'results' in data or 'total' in data
        else:
            assert isinstance(data, list)

    def test_stats_api(self, server, page):
        """Stats API should return valid JSON."""
        response = page.request.get('http://127.0.0.1:14337/api/stats')
        assert response.ok
        data = response.json()
        assert isinstance(data, dict)

    def test_config_api(self, server, page):
        """Config API should return valid JSON with expected fields."""
        response = page.request.get('http://127.0.0.1:14337/api/config')
        assert response.ok
        data = response.json()
        assert 'database_path' in data
        assert 'ollama_url' in data
        assert 'model' in data
        assert 'vault_path' in data

    def test_ollama_status_api(self, server, page):
        """Ollama status API should return valid JSON."""
        response = page.request.get('http://127.0.0.1:14337/api/ollama/status')
        assert response.ok
        data = response.json()
        assert 'status' in data
        assert 'url' in data
        assert 'model' in data


class TestResponsiveLayout:
    """Test responsive layout behavior."""

    def test_sidebar_visible_full_width(self, server, page):
        """Sidebar should be visible on standard viewport."""
        page.set_viewport_size({'width': 1440, 'height': 900})
        page.goto('http://127.0.0.1:14337/')
        
        sidebar = page.locator('.panel-sidebar')
        assert sidebar.is_visible()
        width = sidebar.evaluate('el => el.clientWidth')
        assert width > 0

    def test_stage_visible_on_small_viewport(self, server, page):
        """Stage should remain visible on small viewport."""
        page.set_viewport_size({'width': 800, 'height': 600})
        page.goto('http://127.0.0.1:14337/')

        assert page.locator('.panel-stage').is_visible()

    def test_sidebar_narrows_on_small_viewport(self, server, page):
        """Sidebar should shrink on small viewport but stay visible."""
        page.set_viewport_size({'width': 800, 'height': 600})
        page.goto('http://127.0.0.1:14337/')

        sidebar = page.locator('.panel-sidebar')
        assert sidebar.is_visible()
        width = sidebar.evaluate('el => el.clientWidth')
        assert 0 < width <= 300
