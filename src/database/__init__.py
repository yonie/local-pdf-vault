"""
Database manager for PDF metadata storage and retrieval.

Features:
- SQLite with WAL mode for better concurrency
- FTS5 full-text search
- Connection pooling
- Proper indexing
"""

import sqlite3
import json
import logging
from contextlib import contextmanager
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from contextlib import contextmanager
import threading

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database operations for PDF metadata storage."""
    
    _pool_lock = threading.Lock()
    _connection_pool: Dict[int, sqlite3.Connection] = {}
    
    def __init__(self, db_path: str = "pdfscanner.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._create_table()
        self._enable_wal_mode()
        self._create_indexes()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA cache_size=-64000')  # 64MB cache
            conn.execute('PRAGMA foreign_keys=ON')
            self._local.connection = conn
        return self._local.connection
    
    @contextmanager
    def _transaction(self):
        """Context manager for database transactions."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def _enable_wal_mode(self):
        """Enable WAL mode for better concurrency."""
        try:
            with self._transaction() as conn:
                conn.execute('PRAGMA journal_mode=WAL')
        except Exception as e:
            logger.warning(f"Could not enable WAL mode: {e}")
    
    def _create_table(self):
        """Create the pdf_metadata and indexing_status tables if they don't exist."""
        with self._transaction() as conn:
            # Main metadata table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS pdf_metadata (
                    file_hash TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    subject TEXT,
                    summary TEXT,
                    date TEXT,
                    sender TEXT,
                    recipient TEXT,
                    document_type TEXT,
                    tags TEXT,
                    full_text TEXT,
                    error TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    file_path TEXT,
                    file_size INTEGER,
                    mtime REAL
                )
            ''')
            
            # Create FTS5 virtual table for full-text search (includes full_text)
            conn.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS pdf_search USING fts5(
                    file_hash,
                    filename,
                    subject,
                    summary,
                    sender,
                    recipient,
                    document_type,
                    tags,
                    full_text,
                    content='pdf_metadata',
                    content_rowid='rowid',
                    tokenize='unicode61'
                )
            ''')
            
            # Triggers to keep FTS in sync
            conn.execute('''
                CREATE TRIGGER IF NOT EXISTS pdf_search_insert AFTER INSERT ON pdf_metadata
                BEGIN
                    INSERT INTO pdf_search(rowid, file_hash, filename, subject, summary, sender, recipient, document_type, tags, full_text)
                    VALUES (NEW.rowid, NEW.file_hash, NEW.filename, NEW.subject, NEW.summary, NEW.sender, NEW.recipient, NEW.document_type, NEW.tags, NEW.full_text);
                END
            ''')
            
            conn.execute('''
                CREATE TRIGGER IF NOT EXISTS pdf_search_delete AFTER DELETE ON pdf_metadata
                BEGIN
                    DELETE FROM pdf_search WHERE rowid = OLD.rowid;
                END
            ''')
            
            conn.execute('''
                CREATE TRIGGER IF NOT EXISTS pdf_search_update AFTER UPDATE ON pdf_metadata
                BEGIN
                    DELETE FROM pdf_search WHERE rowid = OLD.rowid;
                    INSERT INTO pdf_search(rowid, file_hash, filename, subject, summary, sender, recipient, document_type, tags, full_text)
                    VALUES (NEW.rowid, NEW.file_hash, NEW.filename, NEW.subject, NEW.summary, NEW.sender, NEW.recipient, NEW.document_type, NEW.tags, NEW.full_text);
                END
            ''')
            
            # Indexing status table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS indexing_status (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
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
    
    def _create_indexes(self):
        """Create performance indexes."""
        with self._transaction() as conn:
            # Index for path lookups
            conn.execute('CREATE INDEX IF NOT EXISTS idx_file_path ON pdf_metadata(file_path)')
            # Index for document type filtering
            conn.execute('CREATE INDEX IF NOT EXISTS idx_document_type ON pdf_metadata(document_type)')
            # Index for date sorting/filtering
            conn.execute('CREATE INDEX IF NOT EXISTS idx_date ON pdf_metadata(date)')
            # Index for sender filtering
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sender ON pdf_metadata(sender)')
            # Index for last_updated sorting
            conn.execute('CREATE INDEX IF NOT EXISTS idx_last_updated ON pdf_metadata(last_updated DESC)')
        
        # Rebuild FTS5 index if it's empty but pdf_metadata has data
        self._rebuild_fts_if_needed()
    
    def _rebuild_fts_if_needed(self):
        """Rebuild FTS5 index if it's out of sync with main table."""
        try:
            conn = self._get_connection()
            
            # Check if FTS5 can actually search (not just count rows)
            # FTS5 can have rows that aren't properly indexed
            cursor = conn.execute("SELECT COUNT(*) FROM pdf_metadata")
            main_count = cursor.fetchone()[0]
            
            if main_count == 0:
                return  # No data to index
            
            # Try a simple search - if it returns 0 for common terms, rebuild
            # Check for common document types in the database
            cursor = conn.execute("SELECT DISTINCT document_type FROM pdf_metadata WHERE document_type IS NOT NULL AND document_type != '' LIMIT 1")
            sample_type = cursor.fetchone()
            
            if sample_type:
                # Try to find this document type in FTS5
                cursor = conn.execute("SELECT file_hash FROM pdf_search WHERE pdf_search MATCH ? LIMIT 1", (sample_type[0],))
                if not cursor.fetchone():
                    logger.info(f"FTS5 index appears corrupt, rebuilding for {main_count} documents...")
                    with self._transaction() as txn:
                        txn.execute("INSERT INTO pdf_search(pdf_search) VALUES('rebuild')")
                    logger.info("FTS5 index rebuilt successfully")
        except Exception as e:
            logger.warning(f"Could not rebuild FTS5 index: {e}")
    
    def store_metadata(self, metadata: Dict[str, Any]) -> bool:
        """
        Store PDF metadata in database.
        
        Args:
            metadata: Dictionary with PDF metadata
            
        Returns:
            True if stored successfully, False otherwise
        """
        try:
            with self._transaction() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO pdf_metadata
                    (file_hash, filename, subject, summary, date, sender, recipient, document_type, tags, full_text, error, file_path, file_size, mtime)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    metadata.get('full_text'),
                    metadata.get('error'),
                    metadata.get('file_path'),
                    metadata.get('file_size'),
                    metadata.get('mtime')
                ))
            return True
        except Exception as e:
            logger.error(f"Error storing metadata: {e}")
            return False
    
    def get_file_cache(self) -> Dict[str, Dict[str, Any]]:
        """
        Retrieve a mapping of file_path -> {hash, size, mtime} for fast verification.
        
        Returns:
            Dictionary where KEY=file_path, VALUE={hash, size, mtime}
        """
        try:
            conn = self._get_connection()
            cursor = conn.execute('''
                SELECT file_path, file_hash, file_size, mtime FROM pdf_metadata WHERE file_path IS NOT NULL
            ''')
            return {row[0]: {'hash': row[1], 'size': row[2], 'mtime': row[3]} for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error retrieving file cache: {e}")
            return {}
    
    def get_all_hashes(self) -> Set[str]:
        """Retrieve all known file hashes as a set for fast lookup."""
        try:
            conn = self._get_connection()
            cursor = conn.execute('SELECT file_hash FROM pdf_metadata')
            return {row[0] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error retrieving hashes: {e}")
            return set()
    
    def get_metadata(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve metadata by file hash.
        
        Args:
            file_hash: SHA-256 hash of the file
            
        Returns:
            Metadata dictionary or None if not found
        """
        try:
            conn = self._get_connection()
            cursor = conn.execute('SELECT * FROM pdf_metadata WHERE file_hash = ?', (file_hash,))
            row = cursor.fetchone()
            if row:
                return {
                    'file_hash': row['file_hash'],
                    'filename': row['filename'],
                    'subject': row['subject'] or '',
                    'summary': row['summary'] or '',
                    'date': row['date'],
                    'sender': row['sender'] or '',
                    'recipient': row['recipient'] or '',
                    'document_type': row['document_type'] or '',
                    'tags': json.loads(row['tags']) if row['tags'] else [],
                    'full_text': row['full_text'] or '',
                    'error': row['error'],
                    'last_updated': row['last_updated'],
                    'file_path': row['file_path'],
                    'file_size': row['file_size'],
                    'mtime': row['mtime']
                }
        except Exception as e:
            logger.error(f"Error retrieving metadata: {e}")
        return None
    
    def search_metadata(self, query: str, limit: int = 50, offset: int = 0,
                       document_type: Optional[str] = None,
                       sender: Optional[str] = None,
                       date_from: Optional[str] = None,
                       date_to: Optional[str] = None,
                       sort_by: str = 'relevance',
                       sort_order: str = 'desc') -> Dict[str, Any]:
        """
        Search metadata using FTS5 with filters and pagination.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            offset: Result offset for pagination
            document_type: Optional filter by document type
            sender: Optional filter by sender
            date_from: Optional filter from date
            date_to: Optional filter to date
            sort_by: Sort field (relevance, date, filename, last_updated)
            sort_order: Sort order (asc, desc)
            
        Returns:
            Dictionary with results, total, limit, offset, has_more
        """
        try:
            conn = self._get_connection()
            
            # If no search query, use direct query on pdf_metadata (no FTS5 needed)
            if not query.strip():
                # Build WHERE clause for filters
                conditions = []
                params = []
                
                if document_type:
                    conditions.append('document_type = ?')
                    params.append(document_type)
                if sender:
                    conditions.append('sender LIKE ?')
                    params.append(f'%{sender}%')
                if date_from:
                    conditions.append('date >= ?')
                    params.append(date_from)
                if date_to:
                    conditions.append('date <= ?')
                    params.append(date_to)
                
                where_clause = 'WHERE ' + ' AND '.join(conditions) if conditions else ''
                
                # Determine sort
                if sort_by == 'date':
                    order_clause = f'ORDER BY date {sort_order.upper()}'
                elif sort_by == 'filename':
                    order_clause = f'ORDER BY filename {sort_order.upper()}'
                else:  # last_updated or relevance (no ranking without search)
                    order_clause = f'ORDER BY last_updated {sort_order.upper()}'
                
                # Count total
                count_query = f'SELECT COUNT(*) FROM pdf_metadata {where_clause}'
                cursor = conn.execute(count_query, params)
                total = cursor.fetchone()[0]
                
                # Get results with pagination
                data_query = f'SELECT * FROM pdf_metadata {where_clause} {order_clause} LIMIT ? OFFSET ?'
                params.extend([limit + 1, offset])
                cursor = conn.execute(data_query, params)
                rows = cursor.fetchall()
                
                has_more = len(rows) > limit
                results = rows[:limit]
                
                documents = []
                for row in results:
                    doc = {
                        'file_hash': row['file_hash'],
                        'filename': row['filename'],
                        'subject': row['subject'] or '',
                        'summary': row['summary'] or '',
                        'date': row['date'],
                        'sender': row['sender'] or '',
                        'recipient': row['recipient'] or '',
                        'document_type': row['document_type'] or '',
                        'tags': json.loads(row['tags']) if row['tags'] else [],
                        'error': row['error'],
                        'last_updated': row['last_updated'],
                        'file_path': row['file_path'],
                        'file_size': row['file_size'],
                        'mtime': row['mtime']
                    }
                    documents.append(doc)
                
                return {
                    'results': documents,
                    'total': total,
                    'limit': limit,
                    'offset': offset,
                    'has_more': has_more
                }
            
            # Use FTS5 for search queries
            base_query = '''
                SELECT pm.*, bm25(pdf_search) as relevance
                FROM pdf_metadata pm
                JOIN pdf_search ON pm.rowid = pdf_search.rowid
                WHERE pdf_search MATCH ?
            '''
            
            # Prepare search terms for FTS5
            search_terms = ' '.join(f'"{term}"*' for term in query.split() if term.strip())
            
            params = [search_terms]
            
            # Add filters
            conditions = []
            if document_type:
                conditions.append('pm.document_type = ?')
                params.append(document_type)
            if sender:
                conditions.append('pm.sender LIKE ?')
                params.append(f'%{sender}%')
            if date_from:
                conditions.append('pm.date >= ?')
                params.append(date_from)
            if date_to:
                conditions.append('pm.date <= ?')
                params.append(date_to)
            
            if conditions:
                base_query += ' AND ' + ' AND '.join(conditions)
            
            # Count total results (use same filters)
            count_query = base_query.replace('SELECT pm.*, bm25(pdf_search) as relevance', 'SELECT COUNT(*)')
            cursor = conn.execute(count_query, params)
            total = cursor.fetchone()[0]
            
            # Add sorting
            if sort_by == 'relevance':
                order_clause = f'ORDER BY relevance {sort_order.upper()}'
            elif sort_by == 'date':
                order_clause = f'ORDER BY pm.date {sort_order.upper()}'
            elif sort_by == 'filename':
                order_clause = f'ORDER BY pm.filename {sort_order.upper()}'
            else:  # last_updated
                order_clause = f'ORDER BY pm.last_updated {sort_order.upper()}'
            
            # Add pagination
            params.extend([limit + 1, offset])  # Fetch one extra to check has_more
            final_query = f'{base_query} {order_clause} LIMIT ? OFFSET ?'
            
            cursor = conn.execute(final_query, params)
            rows = cursor.fetchall()
            
            has_more = len(rows) > limit
            results = rows[:limit]
            
            documents = []
            for row in results:
                doc = {
                    'file_hash': row['file_hash'],
                    'filename': row['filename'],
                    'subject': row['subject'] or '',
                    'summary': row['summary'] or '',
                    'date': row['date'],
                    'sender': row['sender'] or '',
                    'recipient': row['recipient'] or '',
                    'document_type': row['document_type'] or '',
                    'tags': json.loads(row['tags']) if row['tags'] else [],
                    'error': row['error'],
                    'last_updated': row['last_updated'],
                    'file_path': row['file_path'],
                    'file_size': row['file_size'],
                    'mtime': row['mtime'],
                    'relevance_score': -row['relevance'] if row['relevance'] else 0  # bm25 returns negative
                }
                documents.append(doc)
            
            return {
                'results': documents,
                'total': total,
                'limit': limit,
                'offset': offset,
                'has_more': has_more
            }
            
        except Exception as e:
            logger.error(f"Error searching metadata: {e}")
            return {'results': [], 'total': 0, 'limit': limit, 'offset': offset, 'has_more': False}
    
    def get_all_metadata(self, limit: int = 1000, offset: int = 0,
                        sort_by: str = 'last_updated', sort_order: str = 'desc') -> Dict[str, Any]:
        """
        Get all metadata entries with pagination.
        
        Args:
            limit: Maximum number of results
            offset: Result offset for pagination
            sort_by: Sort field
            sort_order: Sort order (asc, desc)
            
        Returns:
            Dictionary with results, total, limit, offset, has_more
        """
        try:
            conn = self._get_connection()
            
            # Get total count
            cursor = conn.execute('SELECT COUNT(*) FROM pdf_metadata')
            total = cursor.fetchone()[0]
            
            # Validate sort field
            valid_sorts = {'last_updated', 'date', 'filename', 'document_type'}
            if sort_by not in valid_sorts:
                sort_by = 'last_updated'
            
            order_clause = f'ORDER BY {sort_by} {sort_order.upper()}'
            
            # Fetch with pagination
            cursor = conn.execute(
                f'SELECT * FROM pdf_metadata {order_clause} LIMIT ? OFFSET ?',
                (limit + 1, offset)
            )
            rows = cursor.fetchall()
            
            has_more = len(rows) > limit
            results = rows[:limit]
            
            documents = []
            for row in results:
                doc = {
                    'file_hash': row['file_hash'],
                    'filename': row['filename'],
                    'subject': row['subject'] or '',
                    'summary': row['summary'] or '',
                    'date': row['date'],
                    'sender': row['sender'] or '',
                    'recipient': row['recipient'] or '',
                    'document_type': row['document_type'] or '',
                    'tags': json.loads(row['tags']) if row['tags'] else [],
                    'error': row['error'],
                    'last_updated': row['last_updated'],
                    'file_path': row['file_path'],
                    'file_size': row['file_size'],
                    'mtime': row['mtime']
                }
                documents.append(doc)
            
            return {
                'results': documents,
                'total': total,
                'limit': limit,
                'offset': offset,
                'has_more': has_more
            }
            
        except Exception as e:
            logger.error(f"Error getting all metadata: {e}")
            return {'results': [], 'total': 0, 'limit': limit, 'offset': offset, 'has_more': False}
    
    def delete_metadata(self, file_hash: str) -> bool:
        """
        Delete a single metadata entry by file hash.
        
        Args:
            file_hash: SHA-256 hash of the file to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            with self._transaction() as conn:
                conn.execute('DELETE FROM pdf_metadata WHERE file_hash = ?', (file_hash,))
            return True
        except Exception as e:
            logger.error(f"Error deleting metadata: {e}")
            return False
    
    def delete_all_metadata(self) -> bool:
        """
        Delete all metadata entries from the database.
        
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            with self._transaction() as conn:
                conn.execute('DELETE FROM pdf_metadata')
            return True
        except Exception as e:
            logger.error(f"Error deleting all metadata: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary with stats like total count, document types, etc.
        """
        try:
            conn = self._get_connection()
            
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
            logger.error(f"Error getting stats: {e}")
            return {'total': 0, 'by_type': {}, 'errors': 0}
    
    def get_document_types(self) -> List[str]:
        """Get list of all document types for filtering."""
        try:
            conn = self._get_connection()
            cursor = conn.execute('''
                SELECT DISTINCT document_type FROM pdf_metadata 
                WHERE document_type IS NOT NULL AND document_type != ''
                ORDER BY document_type
            ''')
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting document types: {e}")
            return []
    
    def get_senders(self, limit: int = 100) -> List[str]:
        """Get list of all senders for autocomplete."""
        try:
            conn = self._get_connection()
            cursor = conn.execute('''
                SELECT DISTINCT sender FROM pdf_metadata 
                WHERE sender IS NOT NULL AND sender != ''
                ORDER BY sender
                LIMIT ?
            ''', (limit,))
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting senders: {e}")
            return []
    
    def get_indexing_status(self) -> Dict[str, Any]:
        """
        Get current indexing status from database.
        
        Returns:
            Dictionary with indexing status
        """
        try:
            conn = self._get_connection()
            cursor = conn.execute('SELECT * FROM indexing_status WHERE id = 1')
            row = cursor.fetchone()
            if row:
                return {
                    'is_running': bool(row['is_running']),
                    'current_file': row['current_file'] or '',
                    'processed': row['processed'] or 0,
                    'total': row['total'] or 0,
                    'skipped': row['skipped'] or 0,
                    'errors': row['errors'] or 0,
                    'last_directory': row['last_directory'] or '',
                    'stop_requested': bool(row['stop_requested'])
                }
        except Exception as e:
            logger.error(f"Error getting indexing status: {e}")
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
        Update indexing status in database.
        
        Args:
            status: Dictionary with status fields to update
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            allowed_fields = {'is_running', 'current_file', 'processed', 'total', 
                            'skipped', 'errors', 'last_directory', 'stop_requested'}
            
            fields = []
            values = []
            for key, value in status.items():
                if key in allowed_fields:
                    fields.append(f"{key} = ?")
                    values.append(value)
            
            if fields:
                with self._transaction() as conn:
                    query = f"UPDATE indexing_status SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = 1"
                    conn.execute(query, values)
            return True
        except Exception as e:
            logger.error(f"Error updating indexing status: {e}")
            return False
    
    def reset_indexing_status(self) -> bool:
        """
        Reset indexing status to defaults.
        
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
    
    def close(self):
        """Close the database connection."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None