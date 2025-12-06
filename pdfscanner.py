#!/usr/bin/env python3
"""
LocalPDFVault - AI-Powered Local Document Search

A privacy-focused PDF indexing application that recursively scans directories for PDF files,
extracts metadata using local Ollama vision models, and provides intelligent search capabilities.
All processing happens locally on your machine - your documents never leave your computer.

Author: yonie (https://github.com/yonie)
Developed with AI assistance
"""

import os
import sys
import hashlib
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import re
import sqlite3
from contextlib import contextmanager

try:
    import requests
except ImportError:
    print("Error: requests library not found. Install with: pip install requests")
    sys.exit(1)

import config

class DatabaseManager:
    """Manages SQLite database operations for PDF metadata storage"""

    def __init__(self, db_path: str = "pdfscanner.db"):
        self.db_path = db_path
        self._create_table()

    def _create_table(self):
        """Create the pdf_metadata and indexing_status tables if they don't exist"""
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS pdf_metadata (
                    file_hash TEXT PRIMARY KEY,
                    filename TEXT,
                    subject TEXT,
                    summary TEXT,
                    date TEXT,
                    sender TEXT,
                    recipient TEXT,
                    document_type TEXT,
                    tags TEXT,
                    error TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create indexing status table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS indexing_status (
                    id INTEGER PRIMARY KEY CHECK (id = 1),  -- Ensure only one row
                    is_running BOOLEAN DEFAULT FALSE,
                    current_file TEXT,
                    processed INTEGER DEFAULT 0,
                    total INTEGER DEFAULT 0,
                    skipped INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    last_directory TEXT,
                    stop_requested BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Insert default row if not exists
            conn.execute('''
                INSERT OR IGNORE INTO indexing_status (id, is_running, current_file, processed, total, skipped, errors, last_directory, stop_requested)
                VALUES (1, FALSE, '', 0, 0, 0, 0, '', FALSE)
            ''')
            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def store_metadata(self, metadata: Dict[str, Any]) -> bool:
        """
        Store PDF metadata in database

        Args:
            metadata: Dictionary with PDF metadata

        Returns:
            True if stored successfully, False otherwise
        """
        try:
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO pdf_metadata
                    (file_hash, filename, subject, summary, date, sender, recipient, document_type, tags, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    metadata.get('file_hash'),
                    metadata.get('filename'),
                    metadata.get('subject'),
                    metadata.get('summary'),
                    metadata.get('date'),
                    metadata.get('sender'),
                    metadata.get('recipient'),
                    metadata.get('document_type'),
                    json.dumps(metadata.get('tags', [])),
                    metadata.get('error')
                ))
            return True
        except Exception as e:
            print(f"Error storing metadata: {e}")
            return False

    def get_metadata(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve metadata by file hash

        Args:
            file_hash: SHA-256 hash of the file

        Returns:
            Metadata dictionary or None if not found
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute('SELECT * FROM pdf_metadata WHERE file_hash = ?', (file_hash,))
                row = cursor.fetchone()
                if row:
                    return {
                        'file_hash': row[0],
                        'filename': row[1],
                        'subject': row[2],
                        'summary': row[3],
                        'date': row[4],
                        'sender': row[5],
                        'recipient': row[6],
                        'document_type': row[7],
                        'tags': json.loads(row[8]) if row[8] else [],
                        'error': row[9],
                        'last_updated': row[10]
                    }
        except Exception as e:
            print(f"Error retrieving metadata: {e}")
        return None

    def search_metadata(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search metadata with relevance ranking and fuzzy matching

        Priority order:
        1. Exact phrase matches (highest)
        2. All terms present (high)
        3. Some terms present (medium)
        4. Fuzzy matches (lowest)

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching metadata dictionaries with relevance scores
        """
        try:
            import difflib

            with self._get_connection() as conn:
                # Enable case-insensitive search
                conn.execute("PRAGMA case_sensitive_like = FALSE")

                # Split query into individual terms
                terms = [term.strip() for term in query.split() if term.strip()]
                if not terms:
                    return []

                # Get all documents first (we'll rank them in Python)
                cursor = conn.execute('SELECT * FROM pdf_metadata')
                all_docs = []
                for row in cursor.fetchall():
                    metadata = {
                        'file_hash': row[0],
                        'filename': row[1],
                        'subject': row[2] or '',
                        'summary': row[3] or '',
                        'date': row[4],
                        'sender': row[5] or '',
                        'recipient': row[6] or '',
                        'document_type': row[7] or '',
                        'tags': json.loads(row[8]) if row[8] else [],
                        'error': row[9],
                        'last_updated': row[10]
                    }
                    all_docs.append(metadata)

                # Score and rank documents
                scored_results = []
                query_lower = query.lower()

                for doc in all_docs:
                    # Combine all searchable text
                    searchable_text = ' '.join([
                        doc['filename'],
                        doc['subject'],
                        doc['summary'],
                        doc['sender'],
                        doc['recipient'],
                        doc['document_type'],
                        ' '.join(doc['tags'])
                    ]).lower()

                    # Calculate relevance score
                    score = self._calculate_relevance_score(query_lower, terms, searchable_text)

                    if score > 0:
                        # Find which terms matched and in which fields
                        matches = self._find_term_matches(terms, doc)

                        doc_copy = doc.copy()
                        doc_copy['relevance_score'] = score
                        doc_copy['search_matches'] = matches
                        scored_results.append(doc_copy)

                # Sort by relevance score (descending), then by last_updated (descending)
                # last_updated is a string timestamp so we sort it as a string (ISO format sorts correctly)
                scored_results.sort(key=lambda x: (-x['relevance_score'], x.get('last_updated', '') or ''), reverse=False)
                # Re-sort to handle the string timestamp properly
                scored_results.sort(key=lambda x: x['relevance_score'], reverse=True)

                return scored_results[:limit]

        except Exception as e:
            print(f"Error searching metadata: {e}")
            return []

    def _calculate_relevance_score(self, query_lower: str, terms: List[str], text: str) -> float:
        """
        Calculate relevance score for a document with clear priority tiers:
        
        Priority Tiers (from highest to lowest):
        1. Exact phrase match ("john doe" found as-is): +1000
        2. All terms present (both "john" AND "doe" found): +500
        3. Partial matches (some terms found): +50 per term
        4. Fuzzy matches (similar words): +5 per match
        """
        if not text:
            return 0

        import difflib
        
        score = 0
        exact_matched_terms = set()
        fuzzy_matched_terms = set()

        # Tier 1: Exact phrase match (highest priority - 1000 points)
        # This matches "john doe" as a complete phrase
        if query_lower in text:
            score += 1000
            # Mark all terms as matched since the whole phrase is there
            for term in terms:
                exact_matched_terms.add(term.lower())

        # Tier 2: All terms present (high priority - 500 points)
        # Both "john" and "doe" are found, but not necessarily together
        all_terms_present = all(term.lower() in text for term in terms)
        if all_terms_present and len(terms) > 1:
            score += 500
            for term in terms:
                exact_matched_terms.add(term.lower())

        # Tier 3: Individual/Partial term matches (medium priority - 50 per term)
        # Only "john" OR only "doe" is found
        for term in terms:
            term_lower = term.lower()
            if term_lower in text:
                exact_matched_terms.add(term_lower)
                # Base score for finding the term
                score += 50
                # Bonus for term frequency (additional occurrences)
                term_count = text.count(term_lower)
                if term_count > 1:
                    score += 5 * (term_count - 1)
                # Bonus for term appearing early in text (likely more relevant)
                words = text.split()[:20]
                if any(term_lower in word for word in words):
                    score += 10

        # Tier 4: Fuzzy matching (lowest priority - 5 per match)
        # Handles typos like "jhn" matching "john"
        words_in_text = text.split()
        for term in terms:
            term_lower = term.lower()
            if term_lower not in exact_matched_terms:
                # Find close matches using difflib
                close_matches = difflib.get_close_matches(
                    term_lower,
                    words_in_text,
                    n=5,  # Check up to 5 potential matches
                    cutoff=0.7  # 70% similarity threshold for fuzzy matching
                )
                if close_matches:
                    fuzzy_matched_terms.add(term_lower)
                    # Award points for each fuzzy match found
                    score += 5 * len(close_matches)

        # Return score if ANY matches were found (exact or fuzzy)
        has_any_match = len(exact_matched_terms) > 0 or len(fuzzy_matched_terms) > 0
        return score if has_any_match else 0

    def _find_term_matches(self, terms: List[str], doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find which terms matched in which fields"""
        matches = []

        for term in terms:
            term_lower = term.lower()
            matched_fields = []

            # Check each field for matches
            field_checks = [
                ('filename', doc.get('filename', '')),
                ('subject', doc.get('subject', '')),
                ('summary', doc.get('summary', '')),
                ('sender', doc.get('sender', '')),
                ('recipient', doc.get('recipient', '')),
                ('type', doc.get('document_type', '')),
            ]

            for field_name, field_value in field_checks:
                if field_value and term_lower in field_value.lower():
                    matched_fields.append(field_name)

            # Check tags
            if doc.get('tags'):
                tag_matches = [tag for tag in doc['tags'] if term_lower in tag.lower()]
                if tag_matches:
                    matched_fields.append('tags')

            if matched_fields:
                matches.append({
                    'term': term,
                    'fields': matched_fields
                })

        return matches

    def get_all_metadata(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get all metadata entries

        Args:
            limit: Maximum number of results

        Returns:
            List of all metadata dictionaries
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute('SELECT * FROM pdf_metadata ORDER BY last_updated DESC LIMIT ?', (limit,))
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'file_hash': row[0],
                        'filename': row[1],
                        'subject': row[2],
                        'summary': row[3],
                        'date': row[4],
                        'sender': row[5],
                        'recipient': row[6],
                        'document_type': row[7],
                        'tags': json.loads(row[8]) if row[8] else [],
                        'error': row[9],
                        'last_updated': row[10]
                    })
                return results
        except Exception as e:
            print(f"Error getting all metadata: {e}")
            return []

    def delete_metadata(self, file_hash: str) -> bool:
        """
        Delete a single metadata entry by file hash

        Args:
            file_hash: SHA-256 hash of the file to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            with self._get_connection() as conn:
                conn.execute('DELETE FROM pdf_metadata WHERE file_hash = ?', (file_hash,))
            return True
        except Exception as e:
            print(f"Error deleting metadata: {e}")
            return False

    def delete_all_metadata(self) -> bool:
        """
        Delete all metadata entries from the database

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            with self._get_connection() as conn:
                conn.execute('DELETE FROM pdf_metadata')
            return True
        except Exception as e:
            print(f"Error deleting all metadata: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics

        Returns:
            Dictionary with stats like total count, document types, etc.
        """
        try:
            with self._get_connection() as conn:
                # Total count
                cursor = conn.execute('SELECT COUNT(*) FROM pdf_metadata')
                total = cursor.fetchone()[0]

                # Count by document type
                cursor = conn.execute('''
                    SELECT document_type, COUNT(*) as count
                    FROM pdf_metadata
                    WHERE document_type IS NOT NULL AND document_type != ''
                    GROUP BY document_type
                    ORDER BY count DESC
                ''')
                types = {row[0]: row[1] for row in cursor.fetchall()}

                # Count with errors
                cursor = conn.execute('SELECT COUNT(*) FROM pdf_metadata WHERE error IS NOT NULL')
                errors = cursor.fetchone()[0]

                return {
                    'total': total,
                    'by_type': types,
                    'errors': errors
                }
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {'total': 0, 'by_type': {}, 'errors': 0}

    def get_indexing_status(self) -> Dict[str, Any]:
        """
        Get current indexing status from database

        Returns:
            Dictionary with indexing status
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute('SELECT * FROM indexing_status WHERE id = 1')
                row = cursor.fetchone()
                if row:
                    return {
                        'is_running': bool(row[1]),
                        'current_file': row[2] or '',
                        'processed': row[3] or 0,
                        'total': row[4] or 0,
                        'skipped': row[5] or 0,
                        'errors': row[6] or 0,
                        'last_directory': row[7] or '',
                        'stop_requested': bool(row[8])
                    }
        except Exception as e:
            print(f"Error getting indexing status: {e}")
        return {
            'is_running': False,
            'current_file': '',
            'processed': 0,
            'total': 0,
            'skipped': 0,
            'errors': 0,
            'last_directory': '',
            'stop_requested': False
        }

    def update_indexing_status(self, status: Dict[str, Any]) -> bool:
        """
        Update indexing status in database

        Args:
            status: Dictionary with status fields to update

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            with self._get_connection() as conn:
                # Build update query dynamically
                fields = []
                values = []
                for key, value in status.items():
                    if key in ['is_running', 'current_file', 'processed', 'total', 'skipped', 'errors', 'last_directory', 'stop_requested']:
                        fields.append(f"{key} = ?")
                        values.append(value)

                if fields:
                    query = f"UPDATE indexing_status SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = 1"
                    conn.execute(query, values)
                return True
        except Exception as e:
            print(f"Error updating indexing status: {e}")
            return False

    def reset_indexing_status(self) -> bool:
        """
        Reset indexing status to defaults

        Returns:
            True if reset successfully, False otherwise
        """
        return self.update_indexing_status({
            'is_running': False,
            'current_file': '',
            'processed': 0,
            'total': 0,
            'skipped': 0,
            'errors': 0,
            'last_directory': '',
            'stop_requested': False
        })




class PDFScanner:
    """Main PDF Scanner class with Ollama integration"""
    
    def __init__(self, host: str = "localhost", port: int = 11434, model: str = "qwen3-vl:30b-a3b-instruct-q4_K_M", verbose: bool = False, db_path: str = "pdfscanner.db"):
        """
        Initialize the PDF Scanner

        Args:
            host: Ollama server host
            port: Ollama server port
            model: Ollama model name
            verbose: Enable verbose logging
            db_path: Path to SQLite database file
        """
        self.host = host
        self.port = port
        self.model = model
        self.base_url = f"http://{host}:{port}"
        self.logger = self._setup_logging(verbose)
        self.db_manager = DatabaseManager(db_path)
        
    def _setup_logging(self, verbose: bool = False) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger('pdfscanner')
        level = logging.DEBUG if verbose else logging.INFO
        logger.setLevel(level)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger
    
    def test_ollama_connection(self) -> bool:
        """Test connection to Ollama server"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                self.logger.info(f"Successfully connected to Ollama at {self.base_url}")
                return True
            else:
                self.logger.error(f"Failed to connect to Ollama: HTTP {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to connect to Ollama at {self.base_url}: {e}")
            return False
    
    def generate_file_hash(self, file_path: str) -> str:
        """
        Generate SHA-256 hash of a file
        
        Args:
            file_path: Path to the file
            
        Returns:
            SHA-256 hash as hex string
        """
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            self.logger.error(f"Failed to generate hash for {file_path}: {e}")
            return ""
    
    
    def extract_pdf_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract metadata from PDF using PyPDF2
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dictionary with PDF metadata
        """
        try:
            import PyPDF2
            metadata = {}
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                if pdf_reader.metadata:
                    pdf_info = pdf_reader.metadata
                    metadata = {
                        'title': pdf_info.get('/Title', ''),
                        'author': pdf_info.get('/Author', ''),
                        'subject': pdf_info.get('/Subject', ''),
                        'creator': pdf_info.get('/Creator', ''),
                        'producer': pdf_info.get('/Producer', ''),
                        'creation_date': str(pdf_info.get('/CreationDate', '')),
                        'modification_date': str(pdf_info.get('/ModDate', ''))
                    }
            return metadata
        except Exception as e:
            self.logger.error(f"Failed to extract PDF metadata from {file_path}: {e}")
            return {}
    
    def ollama_vision_analysis(self, file_path: str) -> Dict[str, Any]:
        """
        Use Ollama vision model to analyze PDF and extract metadata
        The vision model analyzes the PDF directly through images - no text extraction needed
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dictionary with analyzed metadata
        """
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(file_path)
            if doc.page_count == 0:
                doc.close()
                return {}
            
            # Smart selective scanning - first N and last N pages
            total_pages = doc.page_count
            max_pages_per_end = getattr(config, 'MAX_PAGES_PER_END', 3)

            if max_pages_per_end == 0 or total_pages <= (max_pages_per_end * 2):
                # Scan all pages (original behavior or small documents)
                pages_to_scan = list(range(total_pages))
            else:
                # Large document - scan first and last pages only
                pages_to_scan = list(range(max_pages_per_end)) + list(range(total_pages - max_pages_per_end, total_pages))

            self.logger.info(f"Scanning {len(pages_to_scan)} of {total_pages} pages for {file_path}")
            
            image_data_list = []
            for page_num in pages_to_scan:
                page = doc.load_page(page_num)
                # Higher quality for better text recognition
                pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))  # 2.5x zoom for good quality
                image_data_list.append(pix.tobytes("png"))
            
            doc.close()
            
            # Enhanced prompt for comprehensive metadata extraction with tags
            prompt = f"""Analyze this PDF document and extract metadata in JSON format. 
            
            Document: {os.path.basename(file_path)}
            
            Extract and return only a JSON object with these fields:
            - filename: "{os.path.basename(file_path)}"
            - subject: "document title or main topic (in Dutch or English)"
            - summary: "brief 2-3 sentence summary of the content"
            - date: "document date in YYYY-MM-DD format if visible, otherwise empty string"
            - sender: "sender/from information (person, company, or organization)"
            - recipient: "recipient/to information (person, company, or organization)"
            - document_type: "type of document (invoice, contract, letter, report, deed, legal document, etc.)"
            - tags: ["relevant", "categorization", "keywords", "for", "this", "document"]
            
            Look for dates, names, addresses, official seals, document types, and any other identifying information.
            Use your vision capabilities to read and understand the document content.
            Suggest helpful tags that would categorize this document for easy searching and organization.
            
            Respond with only valid JSON, no additional text."""
            
            # Call Ollama API with multiple images if available
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "num_predict": 1000  # Limit response length
                }
            }
            
            # Add images to payload (Ollama supports multiple images)
            # Convert bytes to base64 for Ollama API
            import base64
            if len(image_data_list) == 1:
                payload["images"] = [base64.b64encode(image_data_list[0]).decode('utf-8')]
            else:
                # For multiple pages, use all images
                payload["images"] = [base64.b64encode(img).decode('utf-8') for img in image_data_list]
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=120  # Increased timeout for vision processing
            )
            
            if response.status_code == 200:
                result = response.json()
                try:
                    if 'response' in result:
                        metadata_text = result['response'].strip()
                        # Clean up the response to extract JSON
                        json_match = re.search(r'\{.*\}', metadata_text, re.DOTALL)
                        if json_match:
                            metadata = json.loads(json_match.group())
                            # Ensure all required fields exist
                            required_fields = ["filename", "subject", "summary", "date", "sender", "recipient", "document_type", "tags"]
                            for field in required_fields:
                                if field not in metadata:
                                    if field == "tags":
                                        metadata[field] = []
                                    else:
                                        metadata[field] = ""
                            return metadata
                        else:
                            self.logger.warning("No JSON found in Ollama response")
                            return {}
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Failed to parse Ollama response as JSON: {e}")
                    self.logger.debug(f"Raw response: {metadata_text}")
                    return {}
            else:
                self.logger.error(f"Ollama API error: HTTP {response.status_code}")
                return {}
            
        except ImportError:
            self.logger.error("PyMuPDF (fitz) not found. Install with: pip install pymupdf")
            return {}
        except Exception as e:
            self.logger.error(f"Ollama vision analysis failed for {file_path}: {e}")
            return {}
        
        return {}
    
    def scan_directory(self, directory: str) -> List[str]:
        """
        Recursively scan directory for PDF files
        
        Args:
            directory: Directory path to scan
            
        Returns:
            List of PDF file paths
        """
        pdf_files = []
        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.lower().endswith('.pdf'):
                        pdf_files.append(os.path.join(root, file))
            
            self.logger.info(f"Found {len(pdf_files)} PDF files in {directory}")
            return pdf_files
            
        except Exception as e:
            self.logger.error(f"Failed to scan directory {directory}: {e}")
            return []
    
    def process_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        Process a single PDF file and extract all metadata using vision model
        The vision model handles all heavy lifting - no text extraction needed
        """
        self.logger.info(f"Processing: {file_path}")
        
        result = {
            "filename": file_path,
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
            
            # Use vision model as primary method - it analyzes the PDF images directly
            ollama_metadata = self.ollama_vision_analysis(file_path)
            
            # Vision analysis MUST succeed - no fallback allowed
            if not ollama_metadata:
                result["error"] = "Vision analysis failed - document not indexed"
                self.logger.error(f"Vision analysis failed for {file_path} - skipping indexing")
                return result
            
            # Vision analysis succeeded, use those results
            result.update({
                "subject": ollama_metadata.get("subject", ""),
                "summary": ollama_metadata.get("summary", ""),
                "date": ollama_metadata.get("date", ""),
                "sender": ollama_metadata.get("sender", ""),
                "recipient": ollama_metadata.get("recipient", ""),
                "document_type": ollama_metadata.get("document_type", ""),
                "tags": ollama_metadata.get("tags", [])
            })
            self.logger.info(f"Successfully processed: {file_path}")
            # Output complete result immediately after processing
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"Error processing {file_path}: {e}")
        
        return result
    
    def scan_and_process(self, directory: str) -> None:
        """
        Scan directory and process all PDF files

        Args:
            directory: Directory path to scan
        """
        self.logger.info(f"Starting PDF scan of directory: {directory}")

        # Test Ollama connection first
        if not self.test_ollama_connection():
            self.logger.error("Cannot proceed without Ollama connection")
            return

        # Scan for PDF files
        pdf_files = self.scan_directory(directory)
        if not pdf_files:
            self.logger.warning(f"No PDF files found in {directory}")
            return

        success_count = 0
        skipped_count = 0
        error_count = 0

        for pdf_file in pdf_files:
            # Generate hash to check if already processed
            file_hash = self.generate_file_hash(pdf_file)
            if not file_hash:
                self.logger.error(f"Failed to generate hash for {pdf_file}")
                error_count += 1
                continue

            # Check if already in database
            existing = self.db_manager.get_metadata(file_hash)
            if existing:
                self.logger.info(f"Skipping {pdf_file} - already processed")
                skipped_count += 1
                continue

            # Process the PDF
            result = self.process_pdf(pdf_file)
            
            # Only store in database if vision analysis succeeded (no error)
            if result.get("error") is None:
                if self.db_manager.store_metadata(result):
                    success_count += 1
                else:
                    self.logger.error(f"Failed to store metadata for {pdf_file}")
                    error_count += 1
            else:
                # Vision analysis failed - do not store, count as error for retry later
                self.logger.warning(f"Skipping storage for {pdf_file} - vision analysis failed")
                error_count += 1

        # Log final summary
        self.logger.info(f"Processing complete: {success_count} successful, {skipped_count} skipped, {error_count} errors")
    


def main():
    """Main entry point for the application"""
    parser = argparse.ArgumentParser(
        description="PDF Scanner with Ollama Integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pdfscanner.py --directory /path/to/pdfs
  python pdfscanner.py --directory /path/to/pdfs --host 192.168.1.100 --port 11434
  python pdfscanner.py --directory /path/to/pdfs --model llama3.2-vision:11b
        """
    )
    
    parser.add_argument(
        "--directory",
        required=True,
        help="Directory path to scan for PDF files"
    )
    
    parser.add_argument(
        "--host",
        default="localhost",
        help="Ollama server host (default: localhost)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=11434,
        help="Ollama server port (default: 11434)"
    )
    
    parser.add_argument(
        "--model",
        default="qwen3-vl:30b-a3b-instruct-q4_K_M",
        help="Ollama model name (default: qwen3-vl:30b-a3b-instruct-q4_K_M)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()

    # Validate directory
    if not os.path.exists(args.directory):
        print(f"Error: Directory '{args.directory}' does not exist")
        sys.exit(1)

    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a directory")
        sys.exit(1)

    # Create scanner instance
    scanner = PDFScanner(host=args.host, port=args.port, model=args.model, verbose=args.verbose)
    
    try:
        # Scan and process PDFs (results are output immediately after each file)
        scanner.scan_and_process(args.directory)
        
    except KeyboardInterrupt:
        scanner.logger.info("Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        scanner.logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()