"""
PDF Scanner service for document processing.

Handles directory scanning, PDF processing, and metadata extraction.
"""

import hashlib
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple

from ..config import settings
from ..database import DatabaseManager
from .vision import VisionAnalyzer

logger = logging.getLogger(__name__)


class PageSelectionStrategy:
    """Different strategies for selecting pages to analyze."""
    
    @staticmethod
    def first_and_last(total_pages: int, max_per_end: int) -> List[int]:
        """Scan first N and last N pages."""
        if max_per_end == 0 or total_pages <= (max_per_end * 2):
            return list(range(total_pages))
        return list(range(max_per_end)) + list(range(total_pages - max_per_end, total_pages))
    
    @staticmethod
    def middle(total_pages: int, max_pages: int) -> List[int]:
        """Scan middle pages."""
        if total_pages <= max_pages:
            return list(range(total_pages))
        middle_start = total_pages // 2 - max_pages // 2
        return list(range(middle_start, middle_start + max_pages))
    
    @staticmethod
    def distributed(total_pages: int, max_pages: int) -> List[int]:
        """Scan evenly distributed pages across document."""
        if total_pages <= max_pages:
            return list(range(total_pages))
        step = max(1, total_pages // max_pages)
        return list(range(0, total_pages, step))[:max_pages]
    
    @staticmethod
    def first_only(total_pages: int) -> List[int]:
        """Scan just the first page."""
        return [0] if total_pages > 0 else []


class PDFScanner:
    """Main PDF Scanner class with Ollama vision integration."""
    
    def __init__(self, db_manager: DatabaseManager = None):
        self.db = db_manager or DatabaseManager(settings.database_path)
        self.vision = VisionAnalyzer()
        self.logger = logger
    
    def test_ollama_connection(self) -> bool:
        """Test connection to Ollama server."""
        return self.vision.test_connection()
    
    def generate_file_hash(self, file_path: str) -> str:
        """
        Generate SHA-256 hash of a file using buffered reading.
        
        Args:
            file_path: Path to the file
            
        Returns:
            SHA-256 hash as hex string
        """
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):  # 1MB chunks
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            self.logger.error(f"Failed to generate hash for {file_path}: {e}")
            return ""
    
    def scan_directory(self, directory: str, on_progress: Optional[Callable] = None) -> List[Tuple[str, int, float]]:
        """
        High-performance parallel directory scan.
        
        Args:
            directory: Directory to scan
            on_progress: Optional callback for progress updates
            
        Returns:
            List of (path, size, mtime) tuples
        """
        pdf_files = []
        queue = [directory]
        max_workers = settings.max_parallel_scanning
        
        def _scan_dir(path: str) -> Tuple[List[Tuple], List[str]]:
            local_files = []
            local_subdirs = []
            try:
                with os.scandir(path) as it:
                    for entry in it:
                        try:
                            if entry.is_file() and entry.name.lower().endswith('.pdf'):
                                st = entry.stat()
                                local_files.append((entry.path, st.st_size, st.st_mtime))
                            elif entry.is_dir():
                                local_subdirs.append(entry.path)
                        except OSError:
                            continue
            except OSError as e:
                self.logger.debug(f"Cannot scan {path}: {e}")
            return local_files, local_subdirs
        
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                while queue:
                    if on_progress:
                        on_progress(queue[0])
                    
                    results = list(executor.map(_scan_dir, queue))
                    queue = []
                    
                    for files, subdirs in results:
                        pdf_files.extend(files)
                        queue.extend(subdirs)
            
            self.logger.info(f"Found {len(pdf_files)} PDF files in {directory}")
            return pdf_files
            
        except Exception as e:
            self.logger.error(f"Failed to scan directory {directory}: {e}")
            return []
    
    def extract_pages(self, file_path: str, pages: List[int], zoom: float = 2.5) -> List[bytes]:
        """
        Extract specific pages as images from a PDF.
        
        Args:
            file_path: Path to the PDF
            pages: List of page indices to extract (0-based)
            zoom: Zoom factor for rendering
            
        Returns:
            List of page images as bytes
        """
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(file_path)
            images = []
            
            for page_num in pages:
                if page_num >= doc.page_count:
                    continue
                page = doc.load_page(page_num)
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
                images.append(pix.tobytes("png"))
            
            doc.close()
            return images
            
        except ImportError:
            self.logger.error("PyMuPDF (fitz) not found. Install with: pip install pymupdf")
            return []
        except Exception as e:
            self.logger.error(f"Error extracting pages from {file_path}: {e}")
            return []
    
    def get_pages_to_scan(self, total_pages: int, retry_attempt: int) -> Tuple[List[int], float]:
        """
        Determine which pages to scan based on retry attempt.
        
        Args:
            total_pages: Total number of pages in document
            retry_attempt: Current retry attempt (0-indexed)
            
        Returns:
            Tuple of (page_indices, zoom_level)
        """
        max_per_end = settings.max_pages_per_end
        
        strategies = [
            lambda: PageSelectionStrategy.first_and_last(total_pages, max_per_end),
            lambda: PageSelectionStrategy.middle(total_pages, max_per_end),
            lambda: PageSelectionStrategy.distributed(total_pages, 6),
            lambda: PageSelectionStrategy.first_only(total_pages),
        ]
        
        strategy_index = min(retry_attempt, len(strategies) - 1)
        pages = strategies[strategy_index]()
        zoom = 3.5 if retry_attempt >= 3 else 2.5
        
        return pages, zoom
    
    def process_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        Process a single PDF file and extract all metadata.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dictionary with extracted metadata
        """
        import fitz  # PyMuPDF
        
        self.logger.info(f"Processing: {file_path}")
        
        # Get file stats
        st = os.stat(file_path)
        
        result = {
            "filename": os.path.basename(file_path),
            "file_path": file_path,
            "file_size": st.st_size,
            "mtime": st.st_mtime,
            "file_hash": "",
            "subject": "",
            "summary": "",
            "date": "",
            "sender": "",
            "recipient": "",
            "document_type": "",
            "tags": [],
            "error": None
        }
        
        try:
            # Generate file hash
            result["file_hash"] = self.generate_file_hash(file_path)
            if not result["file_hash"]:
                result["error"] = "Failed to generate file hash"
                return result
            
            # Open PDF to get page count
            doc = fitz.open(file_path)
            total_pages = doc.page_count
            doc.close()
            
            if total_pages == 0:
                result["error"] = "PDF has no pages"
                return result
            
            # Try different page selection strategies
            max_retries = settings.max_vision_retries
            
            for attempt in range(max_retries + 1):
                pages, zoom = self.get_pages_to_scan(total_pages, attempt)
                
                self.logger.debug(f"Attempt {attempt + 1}: scanning pages {pages} of {total_pages}")
                
                # Extract pages as images
                page_images = self.extract_pages(file_path, pages, zoom)
                
                if not page_images:
                    self.logger.warning(f"No images extracted for {file_path}")
                    continue
                
                # Analyze with vision model
                metadata = self.vision.analyze_pdf(file_path, page_images, attempt)
                
                if metadata:
                    result.update({
                        "subject": metadata.get("subject", ""),
                        "summary": metadata.get("summary", ""),
                        "date": metadata.get("date", ""),
                        "sender": metadata.get("sender", ""),
                        "recipient": metadata.get("recipient", ""),
                        "document_type": metadata.get("document_type", ""),
                        "tags": metadata.get("tags", [])
                    })
                    self.logger.info(f"Successfully processed: {file_path}")
                    return result
                
                if attempt < max_retries:
                    self.logger.warning(f"Retry {attempt + 1}/{max_retries} for {file_path}")
            
            # All retries failed
            result["error"] = f"Vision analysis failed after {max_retries + 1} attempts"
            self.logger.error(f"Failed to process {file_path} after all retries")
            
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"Error processing {file_path}: {e}")
        
        return result
    
    def scan_and_process(self, directory: str, force_reindex: bool = False,
                        status_callback: Optional[Callable] = None) -> Dict[str, int]:
        """
        Scan directory and process all PDF files.
        
        Args:
            directory: Directory to scan
            force_reindex: Force reindex even if file hasn't changed
            status_callback: Optional callback for status updates
            
        Returns:
            Dictionary with processing statistics
        """
        import time
        
        stats = {
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'total': 0
        }
        
        # Test Ollama connection
        if not self.test_ollama_connection():
            self.logger.error("Cannot proceed without Ollama connection")
            return stats
        
        # Scan for PDF files
        pdf_entries = self.scan_directory(directory)
        stats['total'] = len(pdf_entries)
        
        if not pdf_entries:
            self.logger.warning(f"No PDF files found in {directory}")
            return stats
        
        # Load file cache for smart skipping
        file_cache = self.db.get_file_cache()
        
        self.logger.info(f"Found {stats['total']} PDF files to check")
        
        for idx, (pdf_path, f_size, f_mtime) in enumerate(pdf_entries, 1):
            # Check for stop request
            status = self.db.get_indexing_status()
            if status.get('stop_requested'):
                self.logger.info("Stop requested, halting indexing")
                break
            
            # Update status
            if status_callback:
                status_callback({
                    'current_file': f"Checking: {os.path.basename(pdf_path)}",
                    'processed': idx - 1
                })
            
            # Smart skip check - avoid re-processing unchanged files
            cached = file_cache.get(pdf_path)
            if not force_reindex and cached:
                if cached['size'] == f_size and abs(cached['mtime'] - f_mtime) < 0.01:
                    stats['skipped'] += 1
                    continue
            
            # Process the PDF
            self.logger.info(f"Processing [{idx}/{stats['total']}]: {os.path.basename(pdf_path)}")
            
            if status_callback:
                status_callback({
                    'current_file': f"Analyzing: {os.path.basename(pdf_path)}"
                })
            
            result = self.process_pdf(pdf_path)
            
            if result.get('error') is None:
                self.db.store_metadata(result)
                stats['processed'] += 1
            else:
                stats['errors'] += 1
        
        self.logger.info(f"Processing complete: {stats}")
        return stats