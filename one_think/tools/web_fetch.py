from one_think.tools import Tool
import requests
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


class WebFetch(Tool):
    """
    Tool for fetching readable content from a web page.
    Priority:
    1. Readable extracted text
    2. Raw HTML fallback
    """

    name: str = "web_fetch"
    description: str = (
        "Fetches content from a web page, prioritizing readable text and "
        "falling back to raw HTML when needed."
    )

    DEFAULT_LENGTH = None
    DEFAULT_TIMEOUT = 10

    def execute(self, arguments: Dict[str, Any] | None = None) -> Tuple[str, str]:
        arguments = arguments or {}

        if arguments.get("help"):
            return self.get_full_information(), ""

        url = arguments.get("url")
        if not url or not isinstance(url, str):
            return "", "Missing required argument: 'url'"

        url = self._normalize_url(url)

        try:
            length = int(arguments.get("length", self.DEFAULT_LENGTH))
            timeout = int(arguments.get("timeout", self.DEFAULT_TIMEOUT))
        except (TypeError, ValueError):
            return "", "'length' and 'timeout' must be integers"

        if length <= 0:
            return "", "'length' must be greater than 0"
        if timeout <= 0:
            return "", "'timeout' must be greater than 0"

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
                allow_redirects=True,
            )
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "").lower()
            raw_text = response.text or ""

            if "text/html" in content_type:
                # Priorytet: czytelny tekst
                readable_content = self._extract_readable_text(raw_text)
                readable_content = self._clean_text(readable_content)

                if readable_content:
                    return readable_content[:length], ""

                # Fallback: surowy HTML
                html_fallback = self._clean_text(raw_text)
                if html_fallback:
                    return html_fallback[:length], ""

                return "", "No readable content found on the page"

            # Dla nie-HTML zwracamy zwykły tekst odpowiedzi
            content = self._clean_text(raw_text)
            if not content:
                return "", "No readable content found on the page"
            content_to_return = content[:length] if length else content
            return content_to_return, ""

        except requests.exceptions.Timeout:
            return "", "Request timed out"
        except requests.exceptions.TooManyRedirects:
            return "", "Too many redirects"
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else "unknown"
            return "", f"HTTP error: status code {status_code}"
        except requests.exceptions.RequestException as e:
            return "", f"Request failed: {e}"
        except Exception as e:
            return "", f"Unexpected error: {e}"

    def get_full_information(self) -> str:
        return (
            f"Tool: {self.name}\n"
            "Description: Fetches content from a web page.\n\n"
            "Usage:\n"
            "- url (str, required): target URL\n"
            f"- length (int, optional): number of characters to return (default={self.DEFAULT_LENGTH})\n"
            f"- timeout (int, optional): request timeout in seconds (default={self.DEFAULT_TIMEOUT})\n"
            "- help (bool, optional): show this message\n\n"
            "Behavior:\n"
            "- Adds browser-like headers\n"
            "- Follows redirects\n"
            "- For HTML pages: returns readable extracted text first\n"
            "- Falls back to raw HTML if readable extraction fails\n"
            "- Returns plain text for non-HTML responses\n"
        )

    def _normalize_url(self, url: str) -> str:
        url = url.strip()
        parsed = urlparse(url)

        if not parsed.scheme:
            return f"https://{url}"

        return url

    def _extract_readable_text(self, html: str) -> str:
        if not html or BeautifulSoup is None:
            return ""

        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
            tag.decompose()

        for selector in ["main", "article", '[role="main"]']:
            node = soup.select_one(selector)
            if node:
                return node.get_text(separator=" ", strip=True)

        if soup.body:
            return soup.body.get_text(separator=" ", strip=True)

        return soup.get_text(separator=" ", strip=True)

    def _clean_text(self, text: str) -> str:
        return " ".join(text.split())


if __name__ == "__main__":
    tool = WebFetch()
    result, error = tool.execute({
        "url": "https://pl.wikipedia.org/wiki/HMS_Roberts_(1915)"
    })

    if error:
        print(f"Error: {error}")
    else:
        print(result)