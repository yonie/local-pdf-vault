"""
Vision analysis service for PDF document processing using Ollama.

Handles communication with Ollama API for document metadata extraction.
"""

import base64
import json
import logging
import re
from typing import Dict, Any, Optional, List
import requests

from ..config import settings

logger = logging.getLogger(__name__)


class VisionAnalyzer:
    """Handles PDF vision analysis using Ollama."""
    
    def __init__(self, host: str = None, port: int = None, model: str = None, timeout: int = None):
        self.host = host or settings.ollama_host
        self.port = port or settings.ollama_port
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout
        self.base_url = f"http://{self.host}:{self.port}"
    
    def test_connection(self) -> bool:
        """Test connection to Ollama server."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                logger.info(f"Connected to Ollama at {self.base_url}")
                return True
            logger.error(f"Ollama returned status {response.status_code}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to Ollama at {self.base_url}: {e}")
            return False
    
    def check_model_available(self) -> tuple[bool, str]:
        """Check if the configured model is available."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = [m.get('name', '') for m in data.get('models', [])]
                if self.model in models:
                    return True, self.model
                return False, f"Model '{self.model}' not found. Available: {', '.join(models[:5])}"
            return False, f"Ollama returned status {response.status_code}"
        except requests.exceptions.RequestException as e:
            return False, str(e)
    
    def analyze_pdf(self, file_path: str, page_images: List[bytes], 
                   retry_attempt: int = 0) -> Optional[Dict[str, Any]]:
        """
        Use Ollama vision model to analyze PDF and extract metadata.
        
        Args:
            file_path: Path to the PDF file (for logging/filename)
            page_images: List of page images as bytes
            retry_attempt: Current retry attempt number
            
        Returns:
            Dictionary with analyzed metadata, or None if failed
        """
        if not page_images:
            logger.warning(f"No page images for {file_path}")
            return None
        
        # Determine zoom level based on retry attempt
        zoom = 2.5 if retry_attempt < 3 else 3.5  # Higher quality on final retry
        
        # Build prompt
        prompt = self._build_prompt(file_path)
        
        # Configure temperature based on retry attempt
        temperature = min(0.1 + (retry_attempt * 0.05), 0.3)
        
        # Build request payload
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "images": [base64.b64encode(img).decode('utf-8') for img in page_images],
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "num_predict": 4096,
                "num_ctx": 8192,
                "num_gpu": 999
            }
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.error(f"Ollama API error for {file_path}: HTTP {response.status_code}")
                return None
            
            result = response.json()
            if 'response' not in result:
                logger.error(f"No 'response' field in Ollama result for {file_path}")
                return None
            
            metadata_text = result['response'].strip()
            
            # Validate response
            if not metadata_text or len(metadata_text) < 50:
                logger.warning(f"Short response ({len(metadata_text)} chars) for {file_path}")
                return None
            
            # Extract JSON from response
            metadata = self._extract_json(metadata_text, file_path)
            
            if metadata:
                logger.info(f"Successfully analyzed {file_path} (attempt {retry_attempt + 1})")
            
            return metadata
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout analyzing {file_path}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error for {file_path}: {e}")
            return None
    
    def _build_prompt(self, file_path: str) -> str:
        """Build the analysis prompt."""
        import os
        filename = os.path.basename(file_path)
        
        return f"""Analyze this PDF document and extract metadata in JSON format. 

Document: {filename}

CRITICAL: Respond with ONLY a valid JSON object. Do not include any explanations, markdown formatting, or additional text.

Required JSON structure:
{{
  "filename": "{filename}",
  "subject": "document title or main topic (in Dutch or English)",
  "summary": "brief 2-3 sentence summary of the content",
  "date": "document date in YYYY-MM-DD format if visible, otherwise empty string",
  "sender": "sender/from information (person, company, or organization)",
  "recipient": "recipient/to information (person, company, or organization)",
  "document_type": "type of document (invoice, contract, letter, report, deed, legal document, etc.)",
  "tags": ["max", "5-10", "relevant", "tags"],
  "full_text": "extract ALL readable text from the document, preserving structure and order"
}}

IMPORTANT: 
- Limit tags to 5-10 most relevant keywords only
- Keep the summary concise (2-3 sentences max)
- The full_text field should contain as much text as you can read from the document - this is critical for search

Look for dates, names, addresses, official seals, document types, and any other identifying information.
Use your vision capabilities to read and understand the document content.

Return ONLY the JSON object, nothing else."""
    
    def _extract_json(self, response_text: str, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Robust JSON extraction with multiple strategies.
        
        Args:
            response_text: Raw response text from Ollama
            file_path: Path to the PDF file (for logging)
            
        Returns:
            Extracted and validated metadata dictionary, or None if failed
        """
        if not response_text:
            logger.warning(f"Empty response for {file_path}")
            return None
        
        # Strategy 1: Extract from markdown code blocks
        markdown_patterns = [
            r'```(?:json)?\s*(\{[^`]+\})\s*```',
            r'```\s*(\{[^`]+\})\s*```',
        ]
        
        for pattern in markdown_patterns:
            match = re.search(pattern, response_text, re.DOTALL)
            if match:
                try:
                    metadata = json.loads(match.group(1))
                    return self._validate_metadata(metadata, file_path)
                except json.JSONDecodeError:
                    continue
        
        # Strategy 2: Find last complete JSON object
        json_objects = []
        brace_depth = 0
        json_start = -1
        
        for i, char in enumerate(response_text):
            if char == '{':
                if brace_depth == 0:
                    json_start = i
                brace_depth += 1
            elif char == '}':
                brace_depth -= 1
                if brace_depth == 0 and json_start >= 0:
                    json_objects.append(response_text[json_start:i+1])
                    json_start = -1
        
        # Try each JSON object, starting from last
        for json_str in reversed(json_objects):
            try:
                metadata = json.loads(json_str)
                if isinstance(metadata, dict) and len(metadata) > 0:
                    return self._validate_metadata(metadata, file_path)
            except json.JSONDecodeError:
                continue
        
        # Strategy 3: Fallback greedy match
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                metadata = json.loads(json_match.group())
                return self._validate_metadata(metadata, file_path)
            except json.JSONDecodeError as e:
                logger.error(f"JSON extraction failed for {file_path}: {e}")
        
        logger.error(f"No valid JSON found in response for {file_path}")
        return None
    
    def _validate_metadata(self, metadata: Dict[str, Any], file_path: str) -> Dict[str, Any]:
        """
        Validate and fix metadata structure.
        
        Args:
            metadata: Raw metadata dictionary
            file_path: Path to the PDF file (for logging)
            
        Returns:
            Validated and fixed metadata dictionary
        """
        required_fields = {
            "filename": "",
            "subject": "",
            "summary": "",
            "date": "",
            "sender": "",
            "recipient": "",
            "document_type": "",
            "tags": [],
            "full_text": ""
        }
        
        # Ensure all required fields exist with correct types
        for field, default_value in required_fields.items():
            if field not in metadata:
                metadata[field] = default_value
                logger.debug(f"Added missing field '{field}' for {file_path}")
            elif field == "tags":
                if not isinstance(metadata[field], list):
                    if isinstance(metadata[field], str):
                        metadata[field] = [t.strip() for t in metadata[field].split(',') if t.strip()]
                    else:
                        metadata[field] = []
            else:
                if not isinstance(metadata[field], str):
                    metadata[field] = str(metadata[field]) if metadata[field] is not None else ""
        
        return metadata