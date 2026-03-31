from one_think.tools import Tool
from typing import Any, Dict, Tuple

try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False


class DuxSearchTool(Tool):
    name = "dux_search"
    description = "Dux Distributed Global Search - metasearch across diverse web search services. (prefer, because it is free)"

    DEFAULT_MAX_RESULTS = 5

    def execute(self, arguments: Dict[str, Any] | None = None) -> Tuple[str, str]:
        arguments = arguments or {}

        if arguments.get("help"):
            return self.get_full_information(), ""

        if not DDGS_AVAILABLE:
            return "", (
                "DDGS library not installed. "
                "Install with: pip install ddgs"
            )

        operation = arguments.get("operation", "text")
        if not operation or not isinstance(operation, str):
            return "", "Missing required argument: 'operation'"

        query = arguments.get("query")
        url = arguments.get("url")

        # Extract operation doesn't need query
        if operation != "extract" and (not query or not isinstance(query, str)):
            return "", "Missing required argument: 'query'"

        # Extract operation needs URL
        if operation == "extract" and (not url or not isinstance(url, str)):
            return "", "Missing required argument: 'url' for extract operation"

        try:
            ddgs = DDGS()

            if operation == "text":
                return self._text_search(ddgs, query, arguments)
            elif operation == "images":
                return self._image_search(ddgs, query, arguments)
            elif operation == "videos":
                return self._video_search(ddgs, query, arguments)
            elif operation == "news":
                return self._news_search(ddgs, query, arguments)
            elif operation == "books":
                return self._book_search(ddgs, query, arguments)
            elif operation == "extract":
                return self._extract_content(ddgs, url, arguments)
            else:
                return "", (
                    f"Unknown operation: '{operation}'. "
                    "Valid operations: text, images, videos, news, books, extract"
                )

        except Exception as e:
            return "", f"Search failed: {e}"

    def _text_search(self, ddgs: Any, query: str, arguments: Dict[str, Any]) -> Tuple[str, str]:
        try:
            max_results = int(arguments.get("max_results", self.DEFAULT_MAX_RESULTS))
        except (TypeError, ValueError):
            return "", "'max_results' must be an integer"

        if max_results <= 0:
            return "", "'max_results' must be greater than 0"

        results = list(ddgs.text(query, max_results=max_results))
        
        if not results:
            return "", "No results found."
        
        out = []
        for idx, item in enumerate(results, 1):
            title = item.get("title") or "(no title)"
            url = item.get("href") or "(no url)"
            snippet = item.get("body") or ""
            out.append(f"{idx}. {title}\nURL: {url}\n{snippet}\n")
        
        return "\n".join(out), ""

    def _image_search(self, ddgs: Any, query: str, arguments: Dict[str, Any]) -> Tuple[str, str]:
        try:
            max_results = int(arguments.get("max_results", self.DEFAULT_MAX_RESULTS))
        except (TypeError, ValueError):
            return "", "'max_results' must be an integer"

        if max_results <= 0:
            return "", "'max_results' must be greater than 0"

        results = list(ddgs.images(query, max_results=max_results))
        
        if not results:
            return "", "No results found."
        
        out = []
        for idx, item in enumerate(results, 1):
            title = item.get("title") or "(no title)"
            image_url = item.get("image") or "(no url)"
            source = item.get("source") or ""
            thumbnail = item.get("thumbnail") or ""
            out.append(f"{idx}. {title}\nImage URL: {image_url}\nSource: {source}\nThumbnail: {thumbnail}\n")
        
        return "\n".join(out), ""

    def _video_search(self, ddgs: Any, query: str, arguments: Dict[str, Any]) -> Tuple[str, str]:
        try:
            max_results = int(arguments.get("max_results", self.DEFAULT_MAX_RESULTS))
        except (TypeError, ValueError):
            return "", "'max_results' must be an integer"

        if max_results <= 0:
            return "", "'max_results' must be greater than 0"

        results = list(ddgs.videos(query, max_results=max_results))
        
        if not results:
            return "", "No results found."
        
        out = []
        for idx, item in enumerate(results, 1):
            title = item.get("title") or "(no title)"
            url = item.get("content") or item.get("url") or "(no url)"
            description = item.get("description") or ""
            duration = item.get("duration") or ""
            publisher = item.get("publisher") or ""
            out.append(f"{idx}. {title}\nURL: {url}\nPublisher: {publisher}\nDuration: {duration}\n{description}\n")
        
        return "\n".join(out), ""

    def _news_search(self, ddgs: Any, query: str, arguments: Dict[str, Any]) -> Tuple[str, str]:
        try:
            max_results = int(arguments.get("max_results", self.DEFAULT_MAX_RESULTS))
        except (TypeError, ValueError):
            return "", "'max_results' must be an integer"

        if max_results <= 0:
            return "", "'max_results' must be greater than 0"

        results = list(ddgs.news(query, max_results=max_results))
        
        if not results:
            return "", "No results found."
        
        out = []
        for idx, item in enumerate(results, 1):
            title = item.get("title") or "(no title)"
            url = item.get("url") or "(no url)"
            body = item.get("body") or ""
            date = item.get("date") or ""
            source = item.get("source") or ""
            out.append(f"{idx}. {title}\nURL: {url}\nSource: {source}\nDate: {date}\n{body}\n")
        
        return "\n".join(out), ""

    def _book_search(self, ddgs: Any, query: str, arguments: Dict[str, Any]) -> Tuple[str, str]:
        try:
            max_results = int(arguments.get("max_results", self.DEFAULT_MAX_RESULTS))
        except (TypeError, ValueError):
            return "", "'max_results' must be an integer"

        if max_results <= 0:
            return "", "'max_results' must be greater than 0"

        results = list(ddgs.books(query, max_results=max_results))
        
        if not results:
            return "", "No results found."
        
        out = []
        for idx, item in enumerate(results, 1):
            title = item.get("title") or "(no title)"
            authors = item.get("authors") or ""
            year = item.get("year") or ""
            url = item.get("url") or "(no url)"
            out.append(f"{idx}. {title}\nAuthors: {authors}\nYear: {year}\nURL: {url}\n")
        
        return "\n".join(out), ""

    def _extract_content(self, ddgs: Any, url: str, arguments: Dict[str, Any]) -> Tuple[str, str]:
        fmt = arguments.get("format", "text_markdown")
        valid_formats = ["text_markdown", "text_plain", "text_rich", "text", "content"]
        
        if fmt not in valid_formats:
            return "", f"Invalid format: '{fmt}'. Valid formats: {', '.join(valid_formats)}"

        result = ddgs.extract(url, fmt=fmt)
        
        if not result:
            return "", "Failed to extract content from URL."
        
        content = result.get("content")
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
        
        return f"URL: {result.get('url')}\n\n{content}", ""

    def get_full_information(self) -> str:
        return (
            f"Tool: {self.name}\n"
            "Description: Dux Distributed Global Search - metasearch across diverse web search services.\n\n"
            "Operations:\n"
            "- text: Perform text search\n"
            "- images: Search for images\n"
            "- videos: Search for videos\n"
            "- news: Search for news articles\n"
            "- books: Search for books\n"
            "- extract: Extract content from a URL\n\n"
            "Arguments:\n"
            "- operation (str, required): Operation to perform (text, images, videos, news, books, extract)\n"
            "- query (str, required for all except extract): Search query\n"
            "- url (str, required for extract): URL to extract content from\n"
            "- max_results (int, optional): Number of results to return (default=5)\n"
            "- format (str, optional for extract): Output format - text_markdown, text_plain, text_rich, text, content (default=text_markdown)\n"
            "- help (bool, optional): Show this message\n\n"
            "Examples:\n"
            "1. Text search: {'operation': 'text', 'query': 'Python programming', 'max_results': 5}\n"
            "2. Image search: {'operation': 'images', 'query': 'nature photos'}\n"
            "3. News search: {'operation': 'news', 'query': 'technology'}\n"
            "4. Extract content: {'operation': 'extract', 'url': 'https://example.com', 'format': 'text_markdown'}\n\n"
            "Behavior:\n"
            "- Uses DDGS library (Dux Distributed Global Search)\n"
            "- No API key required\n"
            "- Aggregates results from diverse web search services\n"
            "- Requires: pip install ddgs\n"
        )


if __name__ == "__main__":
    tool = DuxSearchTool()
    
    # Test text search
    print("=== TEXT SEARCH ===")
    result, error = tool.execute({"operation": "text", "query": "Python programming", "max_results": 2})
    if error:
        print(f"Error: {error}")
    else:
        print(result)
    
    print("\n=== IMAGE SEARCH ===")
    result, error = tool.execute({"operation": "images", "query": "python logo", "max_results": 2})
    if error:
        print(f"Error: {error}")
    else:
        print(result)
    
    print("\n=== NEWS SEARCH ===")
    result, error = tool.execute({"operation": "news", "query": "AI technology", "max_results": 2})
    if error:
        print(f"Error: {error}")
    else:
        print(result)
