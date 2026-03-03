"""
Pydantic models for request/response validation and data structures.
"""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator
import re


class PDFMetadata(BaseModel):
    """PDF document metadata."""
    file_hash: str = Field(..., min_length=64, max_length=64, description="SHA-256 hash")
    filename: str = Field(..., min_length=1, description="Original filename")
    subject: str = Field(default="", description="Document subject/title")
    summary: str = Field(default="", description="AI-generated summary")
    date: str = Field(default="", description="Document date (YYYY-MM-DD)")
    sender: str = Field(default="", description="Sender/from info")
    recipient: str = Field(default="", description="Recipient/to info")
    document_type: str = Field(default="", description="Type of document")
    tags: List[str] = Field(default_factory=list, description="Search tags")
    error: Optional[str] = Field(default=None, description="Error message if processing failed")
    last_updated: Optional[str] = Field(default=None, description="Last update timestamp")
    file_path: Optional[str] = Field(default=None, description="Full path to file")
    file_size: Optional[int] = Field(default=None, description="File size in bytes")
    mtime: Optional[float] = Field(default=None, description="File modification time")
    
    @field_validator('file_hash')
    @classmethod
    def validate_hash(cls, v: str) -> str:
        if not re.match(r'^[a-f0-9]{64}$', v):
            raise ValueError('file_hash must be a valid SHA-256 hex string')
        return v.lower()


class SearchResult(PDFMetadata):
    """Search result with relevance scoring."""
    relevance_score: float = Field(default=0.0, description="Search relevance score")
    search_matches: List[Any] = Field(default_factory=list, description="Matched terms and fields")


class IndexingStatus(BaseModel):
    """Current indexing status."""
    is_running: bool = Field(default=False)
    current_file: str = Field(default="")
    processed: int = Field(default=0)
    total: int = Field(default=0)
    skipped: int = Field(default=0)
    errors: int = Field(default=0)
    last_directory: str = Field(default="")
    stop_requested: bool = Field(default=False)


class SearchQuery(BaseModel):
    """Search query parameters."""
    q: str = Field(default="", max_length=1000, description="Search query")
    limit: int = Field(default=50, ge=1, le=1000, description="Max results")
    offset: int = Field(default=0, ge=0, description="Result offset for pagination")
    document_type: Optional[str] = Field(default=None, description="Filter by document type")
    sender: Optional[str] = Field(default=None, description="Filter by sender")
    date_from: Optional[str] = Field(default=None, description="Filter from date (YYYY-MM-DD)")
    date_to: Optional[str] = Field(default=None, description="Filter to date (YYYY-MM-DD)")
    sort_by: str = Field(default="relevance", description="Sort field: relevance, date, filename")
    sort_order: str = Field(default="desc", description="Sort order: asc, desc")
    
    @field_validator('sort_by')
    @classmethod
    def validate_sort_by(cls, v: str) -> str:
        allowed = ['relevance', 'date', 'filename', 'last_updated']
        if v not in allowed:
            raise ValueError(f'sort_by must be one of: {allowed}')
        return v
    
    @field_validator('sort_order')
    @classmethod
    def validate_sort_order(cls, v: str) -> str:
        if v not in ['asc', 'desc']:
            raise ValueError('sort_order must be asc or desc')
        return v


class IndexRequest(BaseModel):
    """Request to start indexing."""
    force: bool = Field(default=False, description="Force reindex all files")


class ReindexRequest(BaseModel):
    """Request to reindex a specific document."""
    file_hash: str = Field(..., min_length=64, max_length=64)


class DeleteRequest(BaseModel):
    """Request to delete documents."""
    file_hashes: List[str] = Field(..., min_length=1, description="List of file hashes to delete")
    
    @field_validator('file_hashes')
    @classmethod
    def validate_hashes(cls, v: List[str]) -> List[str]:
        for h in v:
            if not re.match(r'^[a-fA-F0-9]{64}$', h):
                raise ValueError(f'Invalid hash: {h}')
        return [h.lower() for h in v]


class ErrorResponse(BaseModel):
    """Error response."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(default=None, description="Detailed error info")


class SuccessResponse(BaseModel):
    """Success response."""
    success: bool = Field(default=True)
    message: Optional[str] = Field(default=None)


class StatsResponse(BaseModel):
    """Database statistics."""
    total: int = Field(default=0)
    by_type: dict = Field(default_factory=dict)
    errors: int = Field(default=0)


class ConfigResponse(BaseModel):
    """System configuration."""
    database_path: str
    ollama_url: str
    model: str
    vault_path: str


class OllamaStatusResponse(BaseModel):
    """Ollama service status."""
    status: str = Field(description="running, offline, or error")
    url: str
    model: str
    model_available: Optional[bool] = Field(default=None)
    error: Optional[str] = Field(default=None)


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""
    results: List[PDFMetadata]
    total: int
    limit: int
    offset: int
    has_more: bool