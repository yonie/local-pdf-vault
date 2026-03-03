"""
Routes package.
"""

from .api import api_bp
from .admin import admin_bp

__all__ = ['api_bp', 'admin_bp']