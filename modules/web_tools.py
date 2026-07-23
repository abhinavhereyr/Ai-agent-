"""Web tools - search, scrape, browse using free APIs.

Merged from OpenHermes + NEO-AGENT web tools.
"""
import re
import json
from typing import Optional

import requests
from bs4 import BeautifulSoup

try:
    from duckduckgo_search import DDGS
    HAS_DDG = True
except ImportError:
    HAS_DDG = False


def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo (free, no API key needed).

    Args:
        query: The search query
        max_results: Maximum number of results (default: 5)

    Returns:
        Formatted search results with titles, snippets, and URLs
    """
    if not HAS_DDG:
        return "DuckDuckGo search not installed. Run: pip install duckduckgo-search"

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No results found."

        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            snippet = r.get("body", "No description")
            url = r.get("href", "No URL")
            lines.append(f"{i}. **{title}**\n   {snippet[:200]}\n   {url}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"Search error: {e}"


def web_scrape(url: str) -> str:
    """Scrape and extract text content from a webpage.

    Args:
        url: The URL to fetch and scrape

    Returns:
        Page text content (up to 10000 chars)
    """
    try:
        headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36")
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove non-content elements
        for tag in soup(["script", "style", "nav", "footer", "header",
                         "noscript"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r'\n+', '\n', text).strip()

        if len(text) > 10000:
            text = text[:10000] + "\n\n... (truncated)"

        return text
    except Exception as e:
        return f"Scrape error: {e}"


def web_fetch_json(url: str) -> str:
    """Fetch JSON data from an API endpoint.

    Args:
        url: The API URL to fetch

    Returns:
        JSON response as formatted string
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return json.dumps(data, indent=2)[:10000]
    except Exception as e:
        return f"JSON fetch error: {e}"


def web_search_news(query: str, max_results: int = 5) -> str:
    """Search news using DuckDuckGo.

    Args:
        query: News search query
        max_results: Maximum results (default: 5)

    Returns:
        Formatted news results
    """
    if not HAS_DDG:
        return "DuckDuckGo search not installed."

    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))
        if not results:
            return "No news found."

        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            source = r.get("source", "unknown")
            date = r.get("date", "")
            url = r.get("url", "")
            lines.append(f"{i}. **{title}** ({source}, {date})\n   {url}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"News search error: {e}"
