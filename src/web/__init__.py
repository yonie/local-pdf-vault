"""
Flask application factory and utilities.
"""

import os
import logging
from functools import wraps
from typing import Callable

from flask import Flask, jsonify, request, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache

from ..config import settings
from ..database import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
db: DatabaseManager = None
limiter: Limiter = None
cache: Cache = None


def create_app(config_override: dict = None) -> Flask:
    """
    Create and configure the Flask application.
    
    Args:
        config_override: Optional configuration overrides
        
    Returns:
        Configured Flask application
    """
    global db, limiter, cache
    
    app = Flask(__name__,
                template_folder='../../templates',
                static_folder='../../static')
    
    # Load configuration
    app.config['SECRET_KEY'] = settings.secret_key
    app.config['DEBUG'] = settings.debug
    
    # Rate limiting
    if settings.rate_limit_enabled:
        limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=[f"{settings.rate_limit_per_minute} per minute"]
        )
    else:
        limiter = None
    
    # Caching
    if settings.cache_enabled:
        cache = Cache(app, config={
            'CACHE_TYPE': 'SimpleCache',
            'CACHE_DEFAULT_TIMEOUT': settings.cache_timeout
        })
    else:
        cache = None
    
    # Initialize database
    db = DatabaseManager(settings.database_path)
    
    # Reset indexing status on startup
    db.reset_indexing_status()
    
    # Register blueprints
    from .routes import api_bp, admin_bp, mcp_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(mcp_bp)
    
    # Main route
    @app.route('/')
    def index():
        from flask import render_template
        return render_template('index.html')
    
    # Error handlers
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({'error': 'Bad request', 'detail': str(e)}), 400
    
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        return jsonify({'error': 'Rate limit exceeded', 'detail': str(e)}), 429
    
    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f"Internal error: {e}")
        return jsonify({'error': 'Internal server error'}), 500
    
    # Validation decorator
    app.validate_request = validate_request
    
    logger.info(f"Application initialized, vault path: {settings.scan_directory}")
    
    return app


def validate_request(schema_class):
    """
    Decorator to validate request data using Pydantic schema.
    
    Usage:
        @app.validate_request(SearchQuery)
        def search(validated_data):
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.is_json:
                data = request.get_json()
            else:
                data = dict(request.args)
            
            try:
                validated = schema_class(**data)
                kwargs['validated'] = validated
                return f(*args, **kwargs)
            except Exception as e:
                return jsonify({
                    'error': 'Validation error',
                    'detail': str(e)
                }), 400
        return decorated_function
    return decorator


def get_db() -> DatabaseManager:
    """Get the database manager instance."""
    global db
    return db


def get_cache():
    """Get the cache instance."""
    global cache
    return cache


def cached(timeout: int = None):
    """
    Decorator for caching responses.
    
    Args:
        timeout: Cache timeout in seconds (uses default if not specified)
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if cache is None:
                return f(*args, **kwargs)
            
            cache_key = f"{f.__name__}:{request.full_path}"
            result = cache.get(cache_key)
            
            if result is None:
                result = f(*args, **kwargs)
                cache.set(cache_key, result, timeout=timeout)
            
            return result
        return decorated_function
    return decorator