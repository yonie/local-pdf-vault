#!/usr/bin/env python3
"""
PDF Scanner with Ollama Integration

A comprehensive PDF scanning application that recursively scans directories for PDF files,
extracts metadata using local Ollama vision models, and outputs structured JSON data.

Author: Kilo Code
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

try:
    import requests
except ImportError:
    print("Error: requests library not found. Install with: pip install requests")
    sys.exit(1)

try:
    import pdfplumber
except ImportError:
    print("Error: pdfplumber library not found. Install with: pip install pdfplumber")
    sys.exit(1)


class PDFScanner:
    """Main PDF Scanner class with Ollama integration"""
    
    def __init__(self, host: str = "localhost", port: int = 11434, model: str = "qwen3-vl:30b-a3b-instruct-q4_K_M"):
        """
        Initialize the PDF Scanner
        
        Args:
            host: Ollama server host
            port: Ollama server port
            model: Ollama model name
        """
        self.host = host
        self.port = port
        self.model = model
        self.base_url = f"http://{host}:{port}"
        self.logger = self._setup_logging()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger('pdfscanner')
        logger.setLevel(logging.INFO)
        
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
    
    def extract_pdf_text(self, file_path: str) -> str:
        """
        Extract text content from PDF file
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Extracted text content
        """
        try:
            text_content = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_content += page_text + "\n"
            return text_content.strip()
        except Exception as e:
            self.logger.error(f"Failed to extract text from {file_path}: {e}")
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
                
            # For multi-page documents, we'll use the first few pages for better analysis
            pages_to_analyze = min(3, doc.page_count)  # Use up to 3 pages
            image_data_list = []
            
            for page_num in range(pages_to_analyze):
                page = doc.load_page(page_num)
                # Higher quality for better text recognition
                pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))  # 3x zoom for better OCR
                image_data_list.append(pix.tobytes("png"))
            
            doc.close()
            
            # Enhanced prompt for comprehensive metadata extraction
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
            
            Look for dates, names, addresses, official seals, document types, and any other identifying information.
            Use your vision capabilities to read and understand the document content.
            
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
                            required_fields = ["filename", "subject", "summary", "date", "sender", "recipient", "document_type"]
                            for field in required_fields:
                                if field not in metadata:
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
            
            # If vision analysis succeeded, use those results
            if ollama_metadata:
                result.update({
                    "subject": ollama_metadata.get("subject", ""),
                    "summary": ollama_metadata.get("summary", ""),
                    "date": ollama_metadata.get("date", ""),
                    "sender": ollama_metadata.get("sender", ""),
                    "recipient": ollama_metadata.get("recipient", ""),
                    "document_type": ollama_metadata.get("document_type", "")
                })
                self.logger.info(f"Successfully processed: {file_path}")
                # Output complete result immediately after processing
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                # Only if vision analysis fails, try basic PDF metadata as fallback
                pdf_metadata = self.extract_pdf_metadata(file_path)
                result.update({
                    "subject": pdf_metadata.get("title", ""),
                    "summary": "Vision analysis not available",
                    "date": pdf_metadata.get("creation_date", ""),
                    "sender": pdf_metadata.get("author", ""),
                    "recipient": "",
                    "document_type": "pdf"
                })
                result["error"] = "Vision analysis failed, using fallback metadata"
                self.logger.info(f"Processed with fallback metadata: {file_path}")
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
        error_count = 0
        
        for pdf_file in pdf_files:
            result = self.process_pdf(pdf_file)
            if result.get("error") is None:
                success_count += 1
            else:
                error_count += 1
        
        # Log final summary
        self.logger.info(f"Processing complete: {success_count} successful, {error_count} errors")
    
    def output_results(self, results: List[Dict[str, Any]]) -> None:
        """
        Output results as JSON to console
        
        Args:
            results: List of processing results
        """
        try:
            json_output = json.dumps(results, indent=2, ensure_ascii=False)
            print(json_output)
        except Exception as e:
            self.logger.error(f"Failed to output JSON results: {e}")


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
    
    # Setup logging level
    if args.verbose:
        logging.getLogger('pdfscanner').setLevel(logging.DEBUG)
    
    # Validate directory
    if not os.path.exists(args.directory):
        print(f"Error: Directory '{args.directory}' does not exist")
        sys.exit(1)
    
    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a directory")
        sys.exit(1)
    
    # Create scanner instance
    scanner = PDFScanner(host=args.host, port=args.port, model=args.model)
    
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