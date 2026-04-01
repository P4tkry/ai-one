"""
AI Web Search Tool - Full JSON migration
Performs AI-powered web search using Tavily API with structured responses
"""
import os
import requests
from typing import Dict, Any, Optional, List

from one_think.tools.base import Tool, ToolResponse
from dotenv import load_dotenv

load_dotenv()


class AIWebSearchTool(Tool):
    """Performs AI-powered web search using the Tavily API."""
    
    name = "ai_web_search"
    description = "Performs AI-powered web search using the Tavily API."
    
    API_URL = "https://api.tavily.com/search"
    DEFAULT_MAX_RESULTS = 5
    
    def execute_json(self, params: Dict[str, Any], request_id: Optional[str] = None) -> ToolResponse:
        """Execute web search with JSON response."""
        
        # Validate query
        query = params.get("query")
        if not query or not isinstance(query, str):
            return self._create_error_response(
                "Missing required parameter: 'query'",
                request_id=request_id
            )
        
        # Validate max_results
        try:
            max_results = int(params.get("max_results", self.DEFAULT_MAX_RESULTS))
        except (TypeError, ValueError):
            return self._create_error_response(
                "'max_results' must be an integer",
                request_id=request_id
            )
        
        if max_results <= 0:
            return self._create_error_response(
                "'max_results' must be greater than 0",
                request_id=request_id
            )
        
        # Check API key
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return self._create_error_response(
                "TAVILY_API_KEY not set in .env file",
                request_id=request_id
            )
        
        # Perform search
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "query": query,
            "max_results": max_results,
        }
        
        try:
            response = requests.post(self.API_URL, headers=headers, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            results = data.get("results")
            if not results:
                return self._create_success_response(
                    result={
                        "query": query,
                        "results": [],
                        "total_results": 0,
                        "message": "No results found"
                    },
                    request_id=request_id
                )
            
            # Structure results
            structured_results = self._structure_results(results)
            
            return self._create_success_response(
                result={
                    "query": query,
                    "results": structured_results,
                    "total_results": len(results),
                    "max_results": max_results,
                    "api_provider": "Tavily"
                },
                request_id=request_id
            )
            
        except requests.exceptions.RequestException as e:
            return self._create_error_response(
                f"Request failed: {e}",
                request_id=request_id
            )
        except Exception as e:
            return self._create_error_response(
                f"Unexpected error: {e}",
                request_id=request_id
            )
    
    def _structure_results(self, results: List[Dict]) -> List[Dict]:
        """Convert raw Tavily results to structured format."""
        structured = []
        for idx, item in enumerate(results, 1):
            structured.append({
                "rank": idx,
                "title": item.get("title") or "(no title)",
                "url": item.get("url") or "(no url)",
                "snippet": item.get("snippet") or "",
                "score": item.get("score"),
                "published_date": item.get("published_date"),
                "content": item.get("content", ""),
                "raw_content": item.get("raw_content", "")
            })
        return structured
    
    def get_help(self) -> str:
        """Return comprehensive help text."""
        return f"""AI Web Search Tool

DESCRIPTION:
    Performs AI-powered web search using the Tavily API.
    Returns structured search results with title, URL, snippet, and content.

PARAMETERS:
    query (string, required)
        Search query to execute

    max_results (integer, optional)
        Number of results to return (default: {self.DEFAULT_MAX_RESULTS})

EXAMPLES:
    1. Basic search:
       {{"query": "OpenAI latest news"}}

    2. Limit results:
       {{"query": "Python tutorial", "max_results": 3}}

    3. Specific search:
       {{"query": "AI-ONE architecture patterns", "max_results": 10}}

CONFIGURATION:
    Set TAVILY_API_KEY in .env file:
        TAVILY_API_KEY=your_api_key_here

    Get API key from: https://tavily.com/

RESPONSE FORMAT:
    Success:
        {{
            "status": "success",
            "result": {{
                "query": "search terms",
                "results": [
                    {{
                        "rank": 1,
                        "title": "Result title",
                        "url": "https://example.com",
                        "snippet": "Brief description...",
                        "score": 0.95,
                        "published_date": "2023-01-01",
                        "content": "Full content...",
                        "raw_content": "Raw content..."
                    }}
                ],
                "total_results": 5,
                "max_results": 5,
                "api_provider": "Tavily"
            }}
        }}
    
    Error:
        {{
            "status": "error",
            "error": {{
                "message": "Error description",
                "type": "ToolExecutionError"
            }}
        }}

FEATURES:
    - AI-powered search results
    - Structured content extraction
    - Relevance scoring
    - Published date information
    - Full content when available
    - Rate limiting handled by API

NOTES:
    - Requires internet connection
    - API key needed for authentication
    - Results ranked by relevance
    - Content may be truncated for very long pages
    - Some results may not have all fields (score, date, etc.)

TROUBLESHOOTING:
    - "API key not set" → Add TAVILY_API_KEY to .env
    - "Request failed" → Check internet connection
    - "No results found" → Try different search terms
    - Rate limiting → Wait and retry
"""