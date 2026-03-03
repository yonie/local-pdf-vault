"""
LocalPDFVault Configuration

Configuration is loaded from environment variables with sensible defaults.
All settings can be overridden via environment variables.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Web Interface Configuration
    web_host: str = Field(default="0.0.0.0", alias="WEB_HOST")
    web_port: int = Field(default=4337, alias="WEB_PORT")
    debug: bool = Field(default=False, alias="DEBUG")
    secret_key: str = Field(default="local-pdf-vault-secret-key-change-in-production", alias="SECRET_KEY")
    
    # Ollama Configuration
    ollama_host: str = Field(default="localhost", alias="OLLAMA_HOST")
    ollama_port: int = Field(default=11434, alias="OLLAMA_PORT")
    ollama_model: str = Field(default="qwen3-vl:30b-a3b-instruct", alias="OLLAMA_MODEL")
    ollama_timeout: int = Field(default=120, alias="OLLAMA_TIMEOUT")
    
    # PDF Processing Configuration
    scan_directory: str = Field(default="/data/pdfs", alias="SCAN_DIRECTORY")
    max_pages_per_end: int = Field(default=3, alias="MAX_PAGES_PER_END")
    max_parallel_scanning: int = Field(default=128, alias="MAX_PARALLEL_SCANNING")
    max_parallel_hashing: int = Field(default=16, alias="MAX_PARALLEL_HASHING")
    
    # Vision Analysis Retry Configuration
    max_vision_retries: int = Field(default=3, alias="MAX_VISION_RETRIES")
    
    # Database Configuration
    database_path: str = Field(default="pdfscanner.db", alias="DATABASE_PATH")
    
    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")
    
    # Caching
    cache_enabled: bool = Field(default=True, alias="CACHE_ENABLED")
    cache_timeout: int = Field(default=30, alias="CACHE_TIMEOUT")
    
    # File Watching
    watch_enabled: bool = Field(default=False, alias="WATCH_ENABLED")
    watch_debounce_seconds: float = Field(default=2.0, alias="WATCH_DEBOUNCE_SECONDS")
    
    @property
    def ollama_url(self) -> str:
        """Get the full Ollama URL."""
        return f"http://{self.ollama_host}:{self.ollama_port}"
    
    @property
    def vault_realpath(self) -> str:
        """Get the real path of the vault directory (resolves symlinks)."""
        return os.path.realpath(self.scan_directory)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Global settings instance
settings = Settings()