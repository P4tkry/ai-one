from one_think.tools import Tool
import os
import requests
from typing import Any, Dict, Tuple
from dotenv import load_dotenv

load_dotenv()

class AIWebSearchTool(Tool):
    name = "ai_web_search"
    description = "Performs AI-powered web search using the Tavily API."


    API_URL = "https://api.tavily.com/search"
    DEFAULT_MAX_RESULTS = 5

    def execute(self, arguments: Dict[str, Any] | None = None) -> Tuple[str, str]:
        arguments = arguments or {}

        if arguments.get("help"):
            return self.get_full_information(), ""

        query = arguments.get("query")
        if not query or not isinstance(query, str):
            return "", "Missing required argument: 'query'"

        try:
            max_results = int(arguments.get("max_results", self.DEFAULT_MAX_RESULTS))
        except (TypeError, ValueError):
            return "", "'max_results' must be an integer"
        if max_results <= 0:
            return "", "'max_results' must be greater than 0"

        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return "", "TAVILY_API_KEY not set in .env file"

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
                return "", "No results found."
            formatted = self._format_results(results)
            return formatted, ""
        except requests.exceptions.RequestException as e:
            return "", f"Request failed: {e}"
        except Exception as e:
            return "", f"Unexpected error: {e}"

    def _format_results(self, results: Any) -> str:
        if not isinstance(results, list):
            return str(results)
        out = []
        for idx, item in enumerate(results, 1):
            title = item.get("title") or "(no title)"
            url = item.get("url") or "(no url)"
            snippet = item.get("snippet") or ""
            out.append(f"{idx}. {title}\nURL: {url}\n{snippet}\n")
        return "\n".join(out)

    def get_full_information(self) -> str:
        return (
            f"Tool: {self.name}\n"
            "Description: Performs AI-powered web search using Tavily API.\n\n"
            "Usage:\n"
            "- query (str, required): search query\n"
            f"- max_results (int, optional): number of results to return (default={self.DEFAULT_MAX_RESULTS})\n"
            "- help (bool, optional): show this message\n\n"
            "Behavior:\n"
            "- Uses Tavily API (https://api.tavily.com/search)\n"
            "- Requires TAVILY_API_KEY in .env file\n"
            "- Returns a list of search results with title, url, and snippet\n"
        )

if __name__ == "__main__":
    tool = AIWebSearchTool()
    result, error = tool.execute({"query": "OpenAI latest news"})
    if error:
        print(f"Error: {error}")
    else:
        print(result)
