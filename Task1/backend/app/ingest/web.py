"""Webpage ingestion.

Two things get special attention: an SSRF guard (the URL comes from the user and
this server can reach private networks), and heading-aware extraction so a chunk
can be cited as "from the Installation section" rather than just "from the page".
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag

from ..config import get_settings
from ..schemas import Segment, SourceKind
from .base import IngestError, IngestResult, ensure_not_empty

# Chrome-like UA: many sites return 403 to the default httpx agent.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
_NOISE_TAGS = ("script", "style", "noscript", "nav", "footer", "header", "aside", "form", "iframe", "svg")
_HEADING_TAGS = ("h1", "h2", "h3", "h4")
_TEXT_TAGS = ("p", "li", "pre", "blockquote", "td", "dd", "dt", "figcaption")
_MAX_BYTES = 5 * 1024 * 1024


def normalise_url(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    if parsed.scheme not in ("http", "https"):
        raise IngestError("Only http and https URLs can be loaded.")
    if not parsed.hostname:
        raise IngestError("That URL is missing a hostname.")
    return urlunparse(parsed)


def _assert_public_host(hostname: str) -> None:
    """Reject loopback, private, link-local and reserved addresses (SSRF guard)."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise IngestError(f"The hostname '{hostname}' could not be resolved.") from exc

    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            raise IngestError("Only public web addresses can be loaded.")


def _page_title(soup: BeautifulSoup, fallback: str) -> str:
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if isinstance(og_title, Tag):
        content = og_title.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    heading = soup.find("h1")
    if isinstance(heading, Tag):
        text = heading.get_text(" ", strip=True)
        if text:
            return text
    return fallback


def _main_content(soup: BeautifulSoup) -> Tag:
    for selector in ("main", "article", '[role="main"]', "#content", ".content"):
        node = soup.select_one(selector)
        if isinstance(node, Tag) and len(node.get_text(strip=True)) > 200:
            return node
    return soup.body if isinstance(soup.body, Tag) else soup


def _extract(html: str, url: str) -> IngestResult:
    soup = BeautifulSoup(html, "html.parser")
    title = _page_title(soup, urlparse(url).netloc)

    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()

    root = _main_content(soup)
    segments: list[Segment] = []
    heading = "Introduction"
    buffer: list[str] = []
    position = 0

    def flush() -> None:
        nonlocal buffer, position
        text = "\n".join(buffer).strip()
        buffer = []
        if len(text) < 40:  # Drop nav crumbs and one-word list items.
            return
        position += 1
        segments.append(Segment(text=f"{heading}\n{text}", position=position, locator=heading))

    for node in root.descendants:
        if isinstance(node, NavigableString) or not isinstance(node, Tag):
            continue
        if node.name in _HEADING_TAGS:
            flush()
            candidate = node.get_text(" ", strip=True)
            if candidate:
                heading = candidate[:120]
        elif node.name in _TEXT_TAGS:
            text = node.get_text(" ", strip=True)
            if text:
                buffer.append(text)
    flush()

    result = IngestResult(kind=SourceKind.WEB, title=title, segments=segments, url=url)
    return ensure_not_empty(
        result,
        "No readable article text was found at this URL. The page may render its "
        "content with JavaScript -- try a direct article or documentation link.",
    )


async def ingest_web(url: str) -> IngestResult:
    settings = get_settings()
    normalised = normalise_url(url)
    hostname = urlparse(normalised).hostname or ""
    await asyncio.to_thread(_assert_public_host, hostname)

    try:
        async with httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        ) as client:
            response = await client.get(normalised)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise IngestError("That page took too long to respond.") from exc
    except httpx.HTTPStatusError as exc:
        raise IngestError(f"That page returned HTTP {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise IngestError(f"That page could not be fetched ({type(exc).__name__}).") from exc

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type and "xml" not in content_type:
        raise IngestError(f"That URL returned '{content_type or 'unknown content'}', not a web page.")
    if len(response.content) > _MAX_BYTES:
        raise IngestError("That page is too large to process.")

    return await asyncio.to_thread(_extract, response.text, normalised)
