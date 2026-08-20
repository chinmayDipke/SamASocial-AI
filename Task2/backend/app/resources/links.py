"""Checking that the resources in a plan actually exist.

Resources are the one place this app can invent facts. The prompt side of the defence
is an allow-list of public platforms; this is the other side -- every URL is fetched
before the mentor sees it, and the badge on the row says what happened.

YouTube needs its own path, and it is the reason this module exists. Fetching a watch
page tells you nothing: `youtube.com/watch?v=<anything>` returns HTTP 200 with a
player shell, so a deleted, private or entirely fictional video id all look fine. The
oEmbed endpoint is the honest question -- "describe this video" -- and it answers 404
when there is no video to describe. That is the difference between checking links and
appearing to check them.

Three properties matter for the rest of the app:

- it only ever opens http(s): every other scheme is refused unfetched;
- it never raises: a link check failing must not fail the mentor's turn;
- it never deletes: an unreachable resource is shown with a badge, because the model
  may have the right idea with a stale URL and the mentor can judge;
- it can be switched off (`VERIFY_RESOURCE_LINKS=false`) so a demo works offline,
  in which case everything honestly stays `unchecked`.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlparse

import httpx

from ..config import get_settings
from ..schemas import LinkStatus, Resource

logger = logging.getLogger(__name__)

_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}

_OEMBED_URL = "https://www.youtube.com/oembed"

# The only two schemes this module will open. Model output is untrusted input, so
# `file:`, `data:` and friends are refused by name rather than left to fail inside
# whichever HTTP library happens to be installed -- a security property that
# depends on a dependency's error behaviour breaks silently when it is upgraded.
_FETCHABLE_SCHEMES = frozenset({"http", "https"})

# Plenty of CDNs answer an unknown user agent with 403, which would read as a dead
# link. Identify as a normal browser so the check measures the URL, not our manners.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


def youtube_watch_url(url: str) -> str | None:
    """Normalise any YouTube video URL to a canonical watch URL, or None.

    Channel, playlist and search URLs return None on purpose: they are ordinary web
    pages, and oEmbed has nothing to say about them.
    """
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    if host not in _YOUTUBE_HOSTS:
        return None

    segments = [segment for segment in parsed.path.split("/") if segment]
    video_id = ""
    if host.endswith("youtu.be"):
        video_id = segments[0] if segments else ""
    elif parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [""])[0]
    elif len(segments) >= 2 and segments[0] in ("shorts", "embed", "live", "v"):
        video_id = segments[1]

    video_id = video_id.strip()
    return f"https://www.youtube.com/watch?v={video_id}" if video_id else None


def is_fetchable(url: str) -> bool:
    """True when this is a URL a link check may open at all."""
    return urlparse(url.strip()).scheme.lower() in _FETCHABLE_SCHEMES


def _classify(status_code: int) -> LinkStatus:
    """2xx and 3xx mean the URL resolves; a 4xx or 5xx means it does not."""
    if status_code < 400:
        return LinkStatus.VERIFIED
    return LinkStatus.UNREACHABLE


async def _probe_youtube(client: httpx.AsyncClient, watch_url: str) -> LinkStatus:
    response = await client.get(_OEMBED_URL, params={"url": watch_url, "format": "json"})
    if response.status_code < 300:
        return LinkStatus.VERIFIED
    if response.status_code in (400, 401, 403, 404):
        # oEmbed reports a missing, private or region-locked video this way.
        return LinkStatus.UNREACHABLE
    # A 429 or a 5xx from the oEmbed service says nothing about the video.
    return LinkStatus.UNCHECKED


async def _probe_http(client: httpx.AsyncClient, url: str) -> LinkStatus:
    """HEAD first because it is cheap, then GET for the hosts that refuse HEAD."""
    response = await client.head(url)
    if response.status_code < 400:
        return LinkStatus.VERIFIED

    async with client.stream("GET", url) as streamed:
        return _classify(streamed.status_code)


async def _probe(client: httpx.AsyncClient, url: str) -> LinkStatus:
    watch_url = youtube_watch_url(url)
    if watch_url:
        return await _probe_youtube(client, watch_url)
    return await _probe_http(client, url)


async def _check_one(
    client: httpx.AsyncClient, gate: asyncio.Semaphore, resource: Resource
) -> None:
    if not is_fetchable(resource.url):
        # Nothing was tried, so nothing is known: `unreachable` would claim we
        # looked. The badge stays honest and the mentor still sees the resource.
        resource.link_status = LinkStatus.UNCHECKED
        return

    async with gate:
        try:
            resource.link_status = await _probe(client, resource.url)
        except Exception as exc:
            # A timeout or a DNS failure is our problem, not evidence about the link.
            logger.info("Link check gave up on %s: %s", resource.url, exc)
            resource.link_status = LinkStatus.UNCHECKED


@asynccontextmanager
async def _default_client() -> AsyncIterator[httpx.AsyncClient]:
    timeout = float(get_settings().link_check_timeout_seconds)
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers=_HEADERS,
    ) as client:
        yield client


async def verify_links(
    resources: Sequence[Resource],
    client: httpx.AsyncClient | None = None,
) -> None:
    """Fill in `link_status` on each resource, in place and concurrently.

    Concurrency is bounded by `LINK_CHECK_CONCURRENCY` so a twelve-module plan does
    not open sixty sockets at once. `client` exists so the tests can drive this
    against a stub transport instead of the internet.
    """
    settings = get_settings()
    if not settings.verify_resource_links or not resources:
        return  # Everything stays `unchecked`, which is the truth.

    gate = asyncio.Semaphore(max(1, settings.link_check_concurrency))
    if client is not None:
        await asyncio.gather(*(_check_one(client, gate, r) for r in resources))
        return

    async with _default_client() as owned:
        await asyncio.gather(*(_check_one(owned, gate, r) for r in resources))
