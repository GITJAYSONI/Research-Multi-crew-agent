import asyncio
import os

import aiohttp
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def perform_python_search(query: str, max_results: int = 5) -> list[dict]:
    """Search Tavily directly and return normalized source metadata."""
    web_results = tavily.search(
        query=query,
        search_depth="advanced",
        max_results=max_results,
    )

    return [
        {
            "title": result.get("title", "N/A"),
            "url": result.get("url", "N/A"),
            "summary": result.get("content", "N/A"),
        }
        for result in web_results.get("results", [])
    ]


async def fetch_url_text(session: aiohttp.ClientSession, url: str) -> str:
    if "youtube.com" in url or "youtu.be" in url:
        return f"Source: {url}\nContent: [YouTube pages cannot be scraped for text.]\n"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/114.0.0.0 Safari/537.36"
        )
    }

    try:
        async with session.get(url, timeout=10, headers=headers) as response:
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")

            for tag in soup(["script", "style", "header", "footer", "nav"]):
                tag.decompose()

            text = soup.get_text(separator=" ", strip=True)[:8000]
            return f"Source: {url}\nContent:\n{text}\n"
    except Exception as exc:
        return f"Could not scrape {url}: {exc}\n"


async def async_scrape_all_urls(urls: list[str]) -> str:
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url_text(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
        return "\n".join(results)
