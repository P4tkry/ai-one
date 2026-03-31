from one_think.tools import Tool
import requests
from typing import Any, Dict, Tuple


class WebFetch(Tool):
    """
    Tool for fetching content from a given web page.
    """

    name: str = "web_fetch"
    description: str = "Fetches the content of a web page for a given URL."

    arguments: Dict[str, str] = {
        "help": "bool (if true, returns detailed information about the tool)",
        "url": "str (URL to fetch content from)",
        "length": "int (number of characters to return, default=100)",
        "timeout": "int (request timeout in seconds, default=5)"
    }

    def execute(self, arguments: Dict[str, Any] | None = None) -> Tuple[str, str]:
        arguments = arguments or {}

        if arguments.get("help"):
            return self.get_full_information(), ""

        url: str | None = arguments.get("url")
        if not url:
            return "", "Missing required argument: 'url'"

        length: int = int(arguments.get("length", 100))
        timeout: int = int(arguments.get("timeout", 5))

        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()

            content = response.text[:length]
            return content, ""

        except requests.exceptions.Timeout:
            return "", "Request timed out"
        except requests.exceptions.HTTPError as e:
            return "", f"HTTP error: {e}"
        except requests.exceptions.RequestException as e:
            return "", f"Request failed: {e}"

    def get_full_information(self) -> str:
        return (
            f"Tool: {self.name}\n"
            "Description: Fetches the content of a web page.\n\n"
            "Arguments:\n"
            "- url (str): target URL (required)\n"
            "- length (int): number of characters to return (default=100)\n"
            "- timeout (int): request timeout in seconds (default=5)\n"
            "- help (bool): show this message\n"
        )


if __name__ == "__main__":
    tool = WebFetch()
    result, error = tool.execute({
        "url": "https://example.com",
        "length": 100,
        "timeout": 5
    })

    if error:
        print(f"Error: {error}")
    else:
        print(result)