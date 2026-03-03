"""
File watcher service for automatic reindexing.

Uses watchdog to monitor the vault directory for changes.
"""

import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from ..config import settings

logger = logging.getLogger(__name__)


class PDFEventHandler(FileSystemEventHandler):
    """Handles file system events for PDF files."""
    
    def __init__(self, callback: Callable[[str, str], None], debounce_seconds: float = 2.0):
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self._pending: dict = {}  # path -> (event_type, last_time)
        self._lock = threading.Lock()
        self._debounce_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def on_created(self, event: FileSystemEvent):
        if not event.is_directory and event.src_path.lower().endswith('.pdf'):
            self._add_event(event.src_path, 'created')
    
    def on_modified(self, event: FileSystemEvent):
        if not event.is_directory and event.src_path.lower().endswith('.pdf'):
            self._add_event(event.src_path, 'modified')
    
    def on_deleted(self, event: FileSystemEvent):
        if not event.is_directory and event.src_path.lower().endswith('.pdf'):
            self._add_event(event.src_path, 'deleted')
    
    def on_moved(self, event: FileSystemEvent):
        if not event.is_directory:
            if event.src_path.lower().endswith('.pdf'):
                self._add_event(event.src_path, 'deleted')
            if event.dest_path.lower().endswith('.pdf'):
                self._add_event(event.dest_path, 'created')
    
    def _add_event(self, path: str, event_type: str):
        """Add an event to the pending queue with debounce."""
        with self._lock:
            self._pending[path] = (event_type, time.time())
        
        # Start debounce thread if not running
        if self._debounce_thread is None or not self._debounce_thread.is_alive():
            self._stop_event.clear()
            self._debounce_thread = threading.Thread(target=self._process_debounced, daemon=True)
            self._debounce_thread.start()
    
    def _process_debounced(self):
        """Process debounced events."""
        while not self._stop_event.is_set():
            time.sleep(0.5)  # Check every 500ms
            
            now = time.time()
            to_process = []
            
            with self._lock:
                for path, (event_type, event_time) in list(self._pending.items()):
                    if now - event_time >= self.debounce_seconds:
                        to_process.append((path, event_type))
                        del self._pending[path]
            
            for path, event_type in to_process:
                try:
                    self.callback(path, event_type)
                except Exception as e:
                    logger.error(f"Error processing event for {path}: {e}")
            
            # Stop if no more pending events
            with self._lock:
                if not self._pending:
                    self._stop_event.set()


class FileWatcher:
    """Watches a directory for PDF file changes."""
    
    def __init__(self, on_file_changed: Callable[[str, str], None]):
        """
        Initialize the file watcher.
        
        Args:
            on_file_changed: Callback function(path, event_type) when a file changes
                           event_type is one of: 'created', 'modified', 'deleted'
        """
        self.on_file_changed = on_file_changed
        self.observer: Optional[Observer] = None
        self._watching = False
    
    def start(self, directory: str) -> bool:
        """
        Start watching a directory.
        
        Args:
            directory: Directory to watch
            
        Returns:
            True if started successfully
        """
        if self._watching:
            logger.warning("File watcher already running")
            return False
        
        if not os.path.isdir(directory):
            logger.error(f"Directory does not exist: {directory}")
            return False
        
        try:
            event_handler = PDFEventHandler(
                callback=self.on_file_changed,
                debounce_seconds=settings.watch_debounce_seconds
            )
            
            self.observer = Observer()
            self.observer.schedule(event_handler, directory, recursive=True)
            self.observer.start()
            self._watching = True
            
            logger.info(f"Started watching directory: {directory}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start file watcher: {e}")
            return False
    
    def stop(self):
        """Stop watching."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        self._watching = False
        logger.info("File watcher stopped")
    
    @property
    def is_watching(self) -> bool:
        """Check if watcher is running."""
        return self._watching


# Global watcher instance
_watcher: Optional[FileWatcher] = None


def get_watcher() -> Optional[FileWatcher]:
    """Get the global file watcher instance."""
    return _watcher


def start_watcher(directory: str, on_file_changed: Callable[[str, str], None]) -> bool:
    """
    Start the global file watcher.
    
    Args:
        directory: Directory to watch
        on_file_changed: Callback for file changes
        
    Returns:
        True if started successfully
    """
    global _watcher
    
    if _watcher and _watcher.is_watching:
        logger.warning("File watcher already running")
        return False
    
    _watcher = FileWatcher(on_file_changed)
    return _watcher.start(directory)


def stop_watcher():
    """Stop the global file watcher."""
    global _watcher
    
    if _watcher:
        _watcher.stop()
        _watcher = None