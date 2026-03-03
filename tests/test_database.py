"""
Tests for Database Manager
"""

import pytest
import tempfile
import os
from src.database import DatabaseManager


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db = DatabaseManager(db_path)
    yield db
    
    # Cleanup
    db.close()
    os.unlink(db_path)


class TestDatabaseManager:
    """Test cases for DatabaseManager class."""
    
    def test_store_and_retrieve_metadata(self, db):
        """Test storing and retrieving metadata."""
        metadata = {
            'file_hash': 'a' * 64,
            'filename': 'test.pdf',
            'subject': 'Test Document',
            'summary': 'A test document for testing',
            'date': '2024-01-15',
            'sender': 'Test Sender',
            'recipient': 'Test Recipient',
            'document_type': 'invoice',
            'tags': ['test', 'invoice'],
            'file_path': '/path/to/test.pdf',
            'file_size': 12345,
            'mtime': 1234567890.0
        }
        
        # Store
        assert db.store_metadata(metadata) is True
        
        # Retrieve
        result = db.get_metadata(metadata['file_hash'])
        assert result is not None
        assert result['filename'] == 'test.pdf'
        assert result['subject'] == 'Test Document'
        assert result['document_type'] == 'invoice'
        assert result['tags'] == ['test', 'invoice']
        assert result['file_path'] == '/path/to/test.pdf'
    
    def test_search_metadata(self, db):
        """Test searching metadata."""
        # Store some test documents
        docs = [
            {
                'file_hash': 'a' * 64,
                'filename': 'invoice_001.pdf',
                'subject': 'Invoice for services',
                'date': '2024-01-15',
                'sender': 'Company A',
                'document_type': 'invoice',
                'tags': ['invoice', 'payment'],
                'file_path': '/path/invoice_001.pdf'
            },
            {
                'file_hash': 'b' * 64,
                'filename': 'contract_001.pdf',
                'subject': 'Employment contract',
                'date': '2024-02-15',
                'sender': 'Company B',
                'document_type': 'contract',
                'tags': ['contract', 'employment'],
                'file_path': '/path/contract_001.pdf'
            }
        ]
        
        for doc in docs:
            db.store_metadata(doc)
        
        # Search for 'invoice'
        results = db.search_metadata('invoice', limit=10)
        assert results['total'] >= 1
        assert len(results['results']) >= 1
    
    def test_get_file_cache(self, db):
        """Test file cache retrieval."""
        metadata = {
            'file_hash': 'c' * 64,
            'filename': 'cached.pdf',
            'file_path': '/path/cached.pdf',
            'file_size': 5000,
            'mtime': 1234567890.0
        }
        
        db.store_metadata(metadata)
        
        cache = db.get_file_cache()
        assert '/path/cached.pdf' in cache
        assert cache['/path/cached.pdf']['hash'] == 'c' * 64
    
    def test_delete_metadata(self, db):
        """Test deleting metadata."""
        metadata = {
            'file_hash': 'd' * 64,
            'filename': 'to_delete.pdf',
            'file_path': '/path/to_delete.pdf'
        }
        
        db.store_metadata(metadata)
        assert db.get_metadata('d' * 64) is not None
        
        db.delete_metadata('d' * 64)
        assert db.get_metadata('d' * 64) is None
    
    def test_indexing_status(self, db):
        """Test indexing status operations."""
        # Get initial status
        status = db.get_indexing_status()
        assert status['is_running'] is False
        
        # Update status
        db.update_indexing_status({
            'is_running': True,
            'current_file': 'test.pdf',
            'processed': 5,
            'total': 10
        })
        
        status = db.get_indexing_status()
        assert status['is_running'] is True
        assert status['current_file'] == 'test.pdf'
        assert status['processed'] == 5
        
        # Reset
        db.reset_indexing_status()
        status = db.get_indexing_status()
        assert status['is_running'] is False
        assert status['processed'] == 0
    
    def test_get_stats(self, db):
        """Test statistics retrieval."""
        # Store some documents
        docs = [
            {
                'file_hash': 'e' * 64,
                'filename': 'doc1.pdf',
                'document_type': 'invoice'
            },
            {
                'file_hash': 'f' * 64,
                'filename': 'doc2.pdf',
                'document_type': 'contract'
            },
            {
                'file_hash': 'g' * 64,
                'filename': 'doc3.pdf',
                'document_type': 'invoice',
                'error': 'Some error'
            }
        ]
        
        for doc in docs:
            db.store_metadata(doc)
        
        stats = db.get_stats()
        assert stats['total'] == 3
        assert 'invoice' in stats['by_type']
        assert stats['errors'] == 1
    
    def test_pagination(self, db):
        """Test pagination in search results."""
        # Store many documents
        for i in range(110):
            db.store_metadata({
                'file_hash': f"{i:064d}",
                'filename': f'doc{i}.pdf',
                'subject': f'Document {i}'
            })
        
        # Test pagination
        page1 = db.get_all_metadata(limit=50, offset=0)
        assert len(page1['results']) == 50
        assert page1['total'] >= 110
        assert page1['has_more'] is True
        
        page3 = db.get_all_metadata(limit=50, offset=100)
        assert len(page3['results']) >= 10
        assert page3['has_more'] is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])