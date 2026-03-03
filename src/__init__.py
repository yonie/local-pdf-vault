"""
LocalPDFVault - AI-Powered Local Document Search

A privacy-focused PDF indexing application that uses local vision models
for intelligent document processing.
"""

from .config import settings
from .database import DatabaseManager
from .services import PDFScanner, VisionAnalyzer, FileWatcher
from .web import create_app

__version__ = "2.0.0"
__author__ = "yonie (https://github.com/yonie)"

__all__ = [
    'settings',
    'DatabaseManager',
    'PDFScanner',
    'VisionAnalyzer',
    'FileWatcher',
    'create_app'
]