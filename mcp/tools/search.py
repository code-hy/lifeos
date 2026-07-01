from mcp.server import mcp_tool
import logging
import urllib.request
import urllib.parse
import json

logger = logging.getLogger("LifeOS.Tools.Search")

@mcp_tool()
def search_web(query: str) -> str:
    """
    Search the web for current information on a given topic.
    Uses DuckDuckGo instant answer API (no API key required).
    """
    logger.info(f"Search Tool: Searching web for '{query}'")
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1"
        req = urllib.request.Request(url, headers={"User-Agent": "LifeOS/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        parts = []
        if data.get("AbstractText"):
            parts.append(f"Summary: {data['AbstractText']}")
        if data.get("AbstractSource"):
            parts.append(f"Source: {data['AbstractSource']}")
        if data.get("RelatedTopics"):
            topics = data["RelatedTopics"][:5]
            for t in topics:
                if isinstance(t, dict) and "Text" in t:
                    parts.append(f"- {t['Text']}")

        if parts:
            return "\n".join(parts)
        else:
            return f"No instant results found for '{query}'. Try a more specific query."
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return f"Web search unavailable: {e}"
