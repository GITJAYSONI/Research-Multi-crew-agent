import asyncio
import logging
import os
from urllib.parse import quote_plus, urlparse

import aiohttp
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

logger = logging.getLogger(__name__)

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# ── YouTube is already blocked in validate_url() so it is NOT listed here.
# Listing it twice caused no harm but was redundant — removed for clarity.
REJECTED_DOMAIN_PARTS = (
    "wikipedia.org",
    "britannica.com",
    "medium.com",
    "blogspot.",
    "wordpress.",
    "quora.com",
    "reddit.com",
    "pinterest.",
    "doubleclick.",
    "adservice.",
    "clickserve.",
)

# Merged with domains previously only in sources.py
TRUSTED_DOMAIN_PARTS = (
    ".gov",
    ".edu",
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "who.int",
    "nih.gov",
    "cdc.gov",
    "sec.gov",
    "nasdaq.com",
    "nseindia.com",
    "investor.",
    "press.",
    "moneycontrol.com",
    "bloomberg.com",
    # ── Added from sources.py trust_score() ──
    "nature.com",
    "science.org",
    "arxiv.org",
    "ieee.org",
    "acm.org",
    "nytimes.com",
    "theguardian.com",
    "worldbank.org",
    "docs.",
    "developer.",
    "support.",
    "research.",
)

# aiohttp timeout object — used in every fetch call
_SCRAPE_TIMEOUT = aiohttp.ClientTimeout(total=15, connect=5)
_MIN_EXTRACTED_TEXT = 200
_BROWSER_MIN_EXTRACTED_TEXT = 1200

# Browser-like User-Agent to reduce bot-blocking
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def validate_url(url: str) -> bool:
    """Return True only for well-formed, scrapeable HTTP/S URLs."""
    if not isinstance(url, str):
        return False
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return False
    if len(url) < 20:
        return False
    lowered = url.lower()
    if "..." in url or " " in url:
        return False
    # Block YouTube — no scrapeable text content
    if "youtube.com" in lowered or "youtu.be" in lowered:
        return False
    parsed = urlparse(url)
    if not parsed.netloc or "." not in parsed.netloc:
        return False
    return True


def extract_clean_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")

    for tag in soup(["script", "style", "header", "footer", "nav", "aside", "form"]):
        tag.decompose()

    return soup.get_text(separator=" ", strip=True)


def source_quality_score(result: dict) -> int:
    """Score a search result 0–100 based on domain trust and content availability."""
    url = (result.get("url") or "").lower()
    domain = urlparse(url).netloc.lower().replace("www.", "")
    score = 50
    if not validate_url(url):
        return 0
    if any(part in domain for part in REJECTED_DOMAIN_PARTS):
        score -= 45
    if any(part in domain for part in TRUSTED_DOMAIN_PARTS) or domain.endswith((".gov", ".edu")):
        score += 40
    if result.get("content") or result.get("summary"):
        score += 10
    return max(0, min(100, score))


def perform_python_search(query: str, max_results: int = 5) -> list[dict]:
    """Search via Tavily and return quality-filtered, deduplicated source metadata."""
    try:
        web_results = tavily.search(
            query=query,
            search_depth="advanced",
            max_results=max_results * 2,
        )
    except Exception as exc:
        logger.error("Tavily search failed for query '%s': %s", query, exc)
        return []

    seen_domains: set[str] = set()
    filtered: list[dict] = []
    deferred_duplicates: list[dict] = []

    for result in web_results.get("results", []):
        source = {
            "title": result.get("title", "N/A"),
            "url": result.get("url", "N/A"),
            "summary": result.get("content", "N/A"),
        }
        score = source_quality_score(source)
        if score < 40:
            continue
        domain = urlparse(source["url"]).netloc.lower().replace("www.", "")
        source["quality_score"] = score
        if domain in seen_domains:
            deferred_duplicates.append(source)
            continue
        seen_domains.add(domain)
        filtered.append(source)

    # Fill up to max_results with same-domain results if needed
    if len(filtered) < max_results:
        filtered.extend(deferred_duplicates[: max_results - len(filtered)])

    return sorted(filtered, key=lambda item: item.get("quality_score", 0), reverse=True)[:max_results]


async def fetch_url_text(session: aiohttp.ClientSession, url: str) -> str:
    """
    Fetch and extract clean text from a single URL.

    Returns empty string on any failure — errors are now logged
    instead of silently discarded.
    """
    if not validate_url(url):
        return ""

    headers = {"User-Agent": _USER_AGENT}

    try:
        async with session.get(
            url,
            timeout=_SCRAPE_TIMEOUT,
            headers=headers,
            allow_redirects=True,
            ssl=False,          # avoids SSL certificate errors on some domains
        ) as response:
            final_url = str(response.url)

            # ── FIX: also accept 301/302 redirect targets that land on 200
            if response.status != 200:
                logger.debug("Non-200 status %s for URL: %s", response.status, url)
                return ""

            if not validate_url(final_url):
                logger.debug("Redirect landed on invalid URL: %s → %s", url, final_url)
                return ""

            # Respect content-type — only parse HTML pages
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                logger.debug("Skipping non-HTML content at %s (%s)", url, content_type)
                return ""

            html = await response.text(errors="replace")
            text = extract_clean_text(html)
            if len(text) < _BROWSER_MIN_EXTRACTED_TEXT:
                browser_text = await fetch_url_text_with_browser(final_url)
                if browser_text:
                    return browser_text

            text = text[:8000]
            if len(text) < _MIN_EXTRACTED_TEXT:
                logger.debug("Too little text extracted from %s (%d chars)", url, len(text))
                return ""

            return f"Source: {final_url}\nOriginal URL: {url}\nContent:\n{text}\n"

    except asyncio.TimeoutError:
        logger.warning("Timeout scraping URL: %s", url)
        return ""
    except aiohttp.ClientError as exc:
        logger.warning("Network error scraping %s: %s", url, exc)
        return ""
    except Exception as exc:
        logger.warning("Unexpected error scraping %s: %s", url, exc)
        return ""


async def fetch_url_text_with_browser(url: str) -> str:
    """Render JavaScript-heavy pages with Playwright when it is installed."""
    if not validate_url(url):
        return ""

    try:
        from playwright.async_api import async_playwright
    except Exception:
        logger.debug("Playwright is not installed; skipping browser scrape for %s", url)
        return ""

    browser = None
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page(user_agent=_USER_AGENT)
            response = await page.goto(url, wait_until="networkidle", timeout=20000)
            final_url = page.url
            if response and response.status >= 400:
                logger.debug("Browser scrape got status %s for %s", response.status, url)
                return ""
            if not validate_url(final_url):
                logger.debug("Browser redirect landed on invalid URL: %s -> %s", url, final_url)
                return ""
            text = extract_clean_text(await page.content())[:12000]
            if len(text) < _MIN_EXTRACTED_TEXT:
                return ""
            return f"Source: {final_url}\nOriginal URL: {url}\nContent:\n{text}\n"
    except Exception as exc:
        logger.warning("Browser scrape failed for %s: %s", url, exc)
        return ""
    finally:
        if browser:
            await browser.close()


async def async_scrape_all_urls(urls: list[str]) -> str:
    """Scrape all valid URLs concurrently and return joined text blob."""
    valid_urls = [url for url in urls if validate_url(url)]
    if not valid_urls:
        logger.warning("async_scrape_all_urls called with no valid URLs.")
        return ""

    connector = aiohttp.TCPConnector(limit=10, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_url_text(session, url) for url in valid_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    blobs = []
    for url, result in zip(valid_urls, results):
        if isinstance(result, Exception):
            logger.warning("Scraping task raised exception for %s: %s", url, result)
        elif result and result.strip():
            blobs.append(result)

    logger.info("Scraped %d/%d URLs successfully.", len(blobs), len(valid_urls))
    return "\n".join(blobs)


def youtube_search_link(query: str) -> str:
    """
    Build a working YouTube search URL for a given query.

    FIX: Previously this appended ' explained' to every query which produced
    irrelevant results for technical/financial topics. Now it uses the raw
    query so results stay on-topic. The ' explained' suffix is only added
    for very short (≤3 word) queries where context helps.
    """
    words = query.strip().split()
    search_term = query if len(words) > 3 else f"{query} explained"
    return f"https://www.youtube.com/results?search_query={quote_plus(search_term)}"
