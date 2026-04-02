"""
WebFetch tool - migrated to new JSON format.

Example of migrating from legacy execute() to new execute_json() interface.
"""

import time
import requests
from typing import Any, Optional
from urllib.parse import urlparse
from pydantic import BaseModel, Field, HttpUrl
from one_think.tools.base import Tool, ToolResponse

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


class WebFetch(Tool):
    """
    Fetches readable content from web pages.
    
    Returns:
    - Readable extracted text for HTML pages
    - Raw text for non-HTML
    - Rejects binary content (PDF, images, etc.)
    """
    
    name = "web_fetch"
    description = "Fetches content from a web page"
    version = "2.0.0"
    
    DEFAULT_LENGTH = None  # No limit
    DEFAULT_TIMEOUT = 10
    
    # Pydantic schemas for input/output validation
    class Input(BaseModel):
        """Input parameters for WebFetch tool."""
        url: HttpUrl = Field(description="URL to fetch content from")
        max_length: Optional[int] = Field(default=None, ge=1, description="Maximum content length (characters)")
        timeout: Optional[int] = Field(default=10, ge=1, le=60, description="Timeout in seconds")
        
    class Output(BaseModel):  
        """Output format for WebFetch tool."""
        url: str = Field(description="Actual URL fetched (after redirects)")
        title: str = Field(description="Page title if available")
        content: str = Field(description="Extracted text content")
        content_type: str = Field(description="Response content type")
        length: int = Field(description="Content length in characters")
        truncated: bool = Field(description="Whether content was truncated due to max_length")
    
    def execute_json(
        self,
        params: dict[str, Any],
        request_id: Optional[str] = None
    ) -> ToolResponse:
        """
        Execute web fetch with strict JSON response.
        
        Args:
            params: {
                "url": str (required),
                "length": int (optional) - char limit,
                "timeout": int (optional) - request timeout
            }
            request_id: Optional request ID
            
        Returns:
            ToolResponse with content in result.data
        """
        
        # Check for help request first
        if params.get("help"):
            return self._create_success_response(
                result={"help": self.get_help()},
                request_id=request_id
            )
        
        start_time = time.perf_counter()
        
        # Validate required params
        error_resp = self.validate_required_params(params, ["url"])
        if error_resp:
            return error_resp
        
        url = params["url"]
        if not isinstance(url, str) or not url.strip():
            return self._create_error_response(
                error_type="ValidationError",
                message="'url' must be a non-empty string",
                request_id=request_id
            )
        
        # Parse optional params
        try:
            length = params.get("length", self.DEFAULT_LENGTH)
            timeout = int(params.get("timeout", self.DEFAULT_TIMEOUT))
            
            if length is not None:
                length = int(length)
                if length <= 0:
                    return self._create_error_response(
                        error_type="ValidationError",
                        message="'length' must be greater than 0",
                        request_id=request_id
                    )
            
            if timeout <= 0:
                return self._create_error_response(
                    error_type="ValidationError",
                    message="'timeout' must be greater than 0",
                    request_id=request_id
                )
        
        except (TypeError, ValueError) as e:
            return self._create_error_response(
                error_type="ValidationError",
                message="'length' and 'timeout' must be integers",
                details={"error": str(e)},
                request_id=request_id
            )
        
        # Normalize URL
        url = self._normalize_url(url)
        
        # Fetch content
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=timeout,
                allow_redirects=True
            )
            response.raise_for_status()
            
            content_type = response.headers.get("Content-Type", "").lower()
            
            # Reject binary types
            binary_types = ["application/pdf", "application/octet-stream", "image/", "video/", "audio/"]
            if any(bt in content_type for bt in binary_types):
                return self._create_error_response(
                    error_type="UnsupportedContentType",
                    message=f"Cannot fetch binary content",
                    details={"content_type": content_type},
                    request_id=request_id
                )
            
            raw_text = response.text or ""
            
            # Extract content based on type
            if "text/html" in content_type:
                content = self._extract_readable_text(raw_text)
                if not content:
                    content = self._clean_text(raw_text)
            else:
                content = self._clean_text(raw_text)
            
            if not content:
                return self._create_error_response(
                    error_type="NoContent",
                    message="No readable content found on the page",
                    request_id=request_id
                )
            
            # Apply length limit
            if length is not None:
                content = content[:length]
                truncated = len(response.text) > length
            else:
                truncated = False
            
            # Success response
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            
            return self._create_success_response(
                result={
                    "url": url,
                    "content": content,
                    "content_type": content_type,
                    "truncated": truncated,
                    "char_count": len(content),
                },
                request_id=request_id,
                execution_time_ms=elapsed_ms,
                metadata={
                    "status_code": response.status_code,
                    "final_url": response.url,
                }
            )
        
        except requests.exceptions.Timeout:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return self._create_error_response(
                error_type="TimeoutError",
                message="Request timed out",
                details={"timeout": timeout},
                request_id=request_id,
                execution_time_ms=elapsed_ms
            )
        
        except requests.exceptions.HTTPError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            status_code = e.response.status_code if e.response else "unknown"
            return self._create_error_response(
                error_type="HTTPError",
                message=f"HTTP error: status code {status_code}",
                details={"status_code": status_code, "url": url},
                request_id=request_id,
                execution_time_ms=elapsed_ms
            )
        
        except requests.exceptions.RequestException as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return self._create_error_response(
                error_type="RequestError",
                message=f"Request failed: {type(e).__name__}",
                details={"error": str(e)},
                request_id=request_id,
                execution_time_ms=elapsed_ms
            )
        
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return self._create_error_response(
                error_type="UnexpectedError",
                message=f"Unexpected error: {type(e).__name__}",
                details={"error": str(e)},
                request_id=request_id,
                execution_time_ms=elapsed_ms
            )
    
    def get_help(self) -> str:
        """Return detailed help for web_fetch."""
        bs4_status = "available" if HAS_BS4 else "NOT AVAILABLE (install beautifulsoup4)"
        
        return f"""
Tool: {self.name} (v{self.version})
Description: {self.description}

Parameters:
  url (string, required):
    - Target URL to fetch
    - Automatically adds https:// if no scheme provided
  
  length (integer, optional):
    - Maximum number of characters to return
    - Default: None (no limit, return full content)
    - If set, content will be truncated
  
  timeout (integer, optional):
    - Request timeout in seconds
    - Default: {self.DEFAULT_TIMEOUT}
    - Must be greater than 0

Response (success):
  {{
    "status": "success",
    "result": {{
      "url": "normalized URL",
      "content": "extracted text content",
      "content_type": "response content type",
      "truncated": true/false,
      "char_count": integer
    }},
    "metadata": {{
      "status_code": HTTP status,
      "final_url": "URL after redirects"
    }}
  }}

Response (error):
  {{
    "status": "error",
    "error": {{
      "type": "ErrorType",
      "message": "error description",
      "details": {{...}}
    }}
  }}

Error Types:
  - ValidationError: Invalid parameters
  - UnsupportedContentType: Binary content (PDF, images, etc.)
  - TimeoutError: Request took too long
  - HTTPError: HTTP status code error
  - RequestError: Network/connection error
  - NoContent: Page has no readable content

Behavior:
  - Follows redirects automatically
  - Adds browser-like headers
  - For HTML: extracts readable text (BeautifulSoup {bs4_status})
  - For non-HTML: returns raw text
  - Rejects binary content types

Examples:
  1. Simple fetch:
     {{"url": "https://example.com"}}
  
  2. With length limit:
     {{"url": "https://example.com", "length": 1000}}
  
  3. Custom timeout:
     {{"url": "https://slow-site.com", "timeout": 30}}
"""
    
    def _normalize_url(self, url: str) -> str:
        """Add https:// if no scheme present."""
        url = url.strip()
        parsed = urlparse(url)
        if not parsed.scheme:
            return f"https://{url}"
        return url
    
    def _extract_readable_text(self, html: str) -> str:
        """Extract readable text from HTML."""
        if not html or not HAS_BS4:
            return ""
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Remove unwanted tags
        for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
            tag.decompose()
        
        # Try to find main content
        for selector in ["main", "article", '[role="main"]']:
            node = soup.select_one(selector)
            if node:
                return node.get_text(separator=" ", strip=True)
        
        # Fallback to body
        if soup.body:
            return soup.body.get_text(separator=" ", strip=True)
        
        return soup.get_text(separator=" ", strip=True)
    
    def _clean_text(self, text: str) -> str:
        """Clean whitespace from text."""
        return " ".join(text.split())


# Example usage
if __name__ == "__main__":
    tool = WebFetchV2()
    
    # Test help
    print("=== HELP ===")
    resp = tool(params={"help": True})
    print(resp.result["help"][:200])
    
    # Test fetch
    print("\n=== FETCH ===")
    resp = tool(params={"url": "example.com", "length": 500})
    print(f"Status: {resp.status}")
    if resp.status == "success":
        print(f"Content length: {resp.result['char_count']}")
        print(f"Content preview: {resp.result['content'][:100]}...")
    else:
        print(f"Error: {resp.error}")
