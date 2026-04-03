"""
DuckDuckGo Search Tool - Real search implementation using DDGS library.
Free web search without API keys or rate limits.
"""
from typing import Dict, Any, Optional, Literal, List
from pydantic import BaseModel, Field
import time

from one_think.tools.base import Tool, ToolResponse

# Try to import DDGS, fallback gracefully
try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False


class DDGSSearchTool(Tool):
    """DuckDuckGo search tool with real search implementation."""
    
    name = "ddgs"
    description = "DuckDuckGo search engine - free web search without API keys"
    version = "2.1.0"
    
    # Pydantic schemas  
    class Input(BaseModel):
        """Input parameters for search operations."""
        operation: Literal["search", "news", "images"] = Field(description="Search operation to perform")
        query: str = Field(description="Search query")
        max_results: Optional[int] = Field(default=5, ge=1, le=20, description="Maximum results (1-20)")
        region: Optional[str] = Field(default="us-en", description="Search region (us-en, uk-en, etc.)")
        safesearch: Optional[str] = Field(default="moderate", description="Safe search: on, moderate, off")
        timelimit: Optional[str] = Field(default=None, description="Time limit: d(day), w(week), m(month), y(year)")
        
    class Output(BaseModel):
        """Output format for search operations."""
        operation: str = Field(description="Operation performed")
        query: str = Field(description="Search query used")
        results: List[Dict[str, Any]] = Field(description="Search results")
        total_results: int = Field(description="Number of results returned")
        region: str = Field(description="Search region used")
        success: bool = Field(description="Whether operation succeeded")
    
    def execute_json(self, params: Dict[str, Any], request_id: Optional[str] = None) -> ToolResponse:
        """Execute search operation with JSON response."""
        
        # Check for help request first
        if params.get("help"):
            return self._create_success_response(
                result={"help": self.get_help()},
                request_id=request_id
            )
        
        # Check if DDGS is available
        if not DDGS_AVAILABLE:
            return self._create_error_response(
                "DDGS library not installed. Install with: pip install ddgs>=1.7.7",
                request_id=request_id
            )
        
        # Validate required params
        error = self.validate_required_params(params, required=["operation", "query"])
        if error:
            return error
            
        operation = params["operation"]
        query = params["query"]
        
        # Route to operation handlers
        if operation == "search":
            return self._perform_text_search(params, request_id)
        elif operation == "news":
            return self._perform_news_search(params, request_id)
        elif operation == "images":
            return self._perform_image_search(params, request_id)
        else:
            return self._create_error_response(
                f"Unknown operation: '{operation}'. Valid operations: search, news, images",
                request_id=request_id
            )
    
    def _perform_text_search(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Perform web text search using DDGS."""
        query = params["query"]
        max_results = params.get("max_results", 5)
        region = params.get("region", "us-en")
        safesearch = params.get("safesearch", "moderate")
        timelimit = params.get("timelimit", None)
        
        try:
            start_time = time.time()
            
            # Perform search
            ddgs = DDGS()
            results = ddgs.text(
                query=query,
                region=region,
                safesearch=safesearch,
                timelimit=timelimit,
                max_results=max_results
            )
            
            # Convert generator to list and extract relevant fields
            search_results = []
            for result in results:
                search_results.append({
                    "title": result.get("title", ""),
                    "url": result.get("href", ""),
                    "snippet": result.get("body", ""),
                    "favicon": result.get("favicon", ""),
                    "published": result.get("published", "")
                })
            
            execution_time = (time.time() - start_time) * 1000
            
            return self._create_success_response(
                result={
                    "operation": "search",
                    "query": query,
                    "results": search_results,
                    "total_results": len(search_results),
                    "region": region,
                    "safesearch": safesearch,
                    "timelimit": timelimit,
                    "execution_time_ms": round(execution_time, 2),
                    "success": True
                },
                request_id=request_id
            )
            
        except Exception as e:
            return self._create_error_response(
                f"Search failed: {str(e)}",
                request_id=request_id
            )
    
    def _perform_news_search(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Perform news search using DDGS."""
        query = params["query"]
        max_results = params.get("max_results", 5)
        region = params.get("region", "us-en")
        safesearch = params.get("safesearch", "moderate")
        timelimit = params.get("timelimit", None)
        
        try:
            start_time = time.time()
            
            # Perform news search
            ddgs = DDGS()
            results = ddgs.news(
                query=query,
                region=region,
                safesearch=safesearch,
                timelimit=timelimit,
                max_results=max_results
            )
            
            # Convert generator to list and extract relevant fields
            news_results = []
            for result in results:
                news_results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "snippet": result.get("body", ""),
                    "source": result.get("source", ""),
                    "published": result.get("date", ""),
                    "favicon": result.get("favicon", "")
                })
            
            execution_time = (time.time() - start_time) * 1000
            
            return self._create_success_response(
                result={
                    "operation": "news",
                    "query": query,
                    "results": news_results,
                    "total_results": len(news_results),
                    "region": region,
                    "execution_time_ms": round(execution_time, 2),
                    "success": True
                },
                request_id=request_id
            )
            
        except Exception as e:
            return self._create_error_response(
                f"News search failed: {str(e)}",
                request_id=request_id
            )
    
    def _perform_image_search(self, params: Dict[str, Any], request_id: Optional[str]) -> ToolResponse:
        """Perform image search using DDGS."""
        query = params["query"]
        max_results = params.get("max_results", 5)
        region = params.get("region", "us-en")
        safesearch = params.get("safesearch", "moderate")
        
        try:
            start_time = time.time()
            
            # Perform image search
            ddgs = DDGS()
            results = ddgs.images(
                query=query,
                region=region,
                safesearch=safesearch,
                max_results=max_results
            )
            
            # Convert generator to list and extract relevant fields
            image_results = []
            for result in results:
                image_results.append({
                    "title": result.get("title", ""),
                    "image_url": result.get("image", ""),
                    "thumbnail_url": result.get("thumbnail", ""),
                    "source_url": result.get("url", ""),
                    "width": result.get("width", 0),
                    "height": result.get("height", 0),
                    "source": result.get("source", "")
                })
            
            execution_time = (time.time() - start_time) * 1000
            
            return self._create_success_response(
                result={
                    "operation": "images",
                    "query": query,
                    "results": image_results,
                    "total_results": len(image_results),
                    "region": region,
                    "execution_time_ms": round(execution_time, 2),
                    "success": True
                },
                request_id=request_id
            )
            
        except Exception as e:
            return self._create_error_response(
                f"Image search failed: {str(e)}",
                request_id=request_id
            )
    
    def get_help(self) -> str:
        """Return comprehensive help text."""
        return """DuckDuckGo Search Tool (DDGS)

DESCRIPTION:
    Real web search using DuckDuckGo search engine.
    Free to use without API keys or rate limits.
    
FEATURES:
    ✅ Web text search
    ✅ News search  
    ✅ Image search
    ✅ Multiple regions and languages
    ✅ Safe search filtering
    ✅ Time-based filtering

OPERATIONS:
    search    - Web text search (default)
    news      - News articles search
    images    - Image search

PARAMETERS:
    operation (string, required)
        Operation to perform: search, news, images
        
    query (string, required)
        Search query or keywords
        
    max_results (integer, optional)
        Maximum results to return (1-20), default: 5
        
    region (string, optional)  
        Search region: us-en, uk-en, de-de, fr-fr, etc.
        Default: us-en
        
    safesearch (string, optional)
        Safe search filter: on, moderate, off
        Default: moderate
        
    timelimit (string, optional)
        Time filter: d(day), w(week), m(month), y(year)
        Default: None (all time)

EXAMPLES:
    1. Basic web search:
       {"operation": "search", "query": "Python programming"}
       
    2. Recent news:
       {"operation": "news", "query": "latest technology", "timelimit": "w"}
       
    3. Image search:
       {"operation": "images", "query": "mountain landscape", "max_results": 10}
       
    4. Advanced search:
       {"operation": "search", "query": "machine learning", 
        "region": "uk-en", "safesearch": "off", "max_results": 10}

RESPONSE FORMAT:
    Success:
        {
            "status": "success",
            "result": {
                "operation": "search",
                "query": "Python programming",
                "results": [
                    {
                        "title": "Learn Python Programming",
                        "url": "https://example.com",
                        "snippet": "Complete guide to Python...",
                        "published": "2024-01-15"
                    }
                ],
                "total_results": 5,
                "region": "us-en",
                "execution_time_ms": 1250.5,
                "success": true
            }
        }
        
    Error:
        {
            "status": "error", 
            "error": {
                "message": "Search failed: connection error",
                "type": "ToolExecutionError"
            }
        }

NOTES:
    - No API key required
    - Rate limits handled automatically by DDGS
    - Supports multiple search backends
    - Real-time results from DuckDuckGo
    - Privacy-focused search (no tracking)
    
REQUIREMENTS:
    - ddgs>=1.7.7 (install with: pip install ddgs)
"""