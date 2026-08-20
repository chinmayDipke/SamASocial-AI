"""Link verification, driven against a stubbed transport rather than the internet.

The YouTube case is the one worth having a test for: a watch page answers 200 for a
video id that was never real, so the only honest check is oEmbed, and the only way to
prove we do that is to answer its 404 and assert the badge.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.config import get_settings
from app.resources.links import is_fetchable, verify_links, youtube_watch_url
from app.schemas import LinkStatus, Resource

WATCH = "https://www.youtube.com/watch?v=deadbeef123"
BLOG = "https://example.dev/posts/loops"


def resource(url: str) -> Resource:
    return Resource(title="Something", url=url)


def check(resources: list[Resource], handler: object) -> None:
    """Run verification against a MockTransport, inside its own event loop."""

    async def run() -> None:
        transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport) as client:
            await verify_links(resources, client=client)

    asyncio.run(run())


@pytest.fixture(autouse=True)
def _fresh_settings() -> object:
    """Settings are cached process-wide, so tests that change the env must reset it."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=abc123", "https://www.youtube.com/watch?v=abc123"),
        ("https://youtu.be/abc123", "https://www.youtube.com/watch?v=abc123"),
        ("https://www.youtube.com/shorts/abc123", "https://www.youtube.com/watch?v=abc123"),
        ("https://m.youtube.com/watch?v=abc123&t=30s", "https://www.youtube.com/watch?v=abc123"),
        # Not videos: oEmbed has nothing to say about these, so they take the HTTP path.
        ("https://www.youtube.com/@freecodecamp", None),
        ("https://www.youtube.com/playlist?list=PL123", None),
        ("https://example.dev/watch?v=abc123", None),
    ],
)
def test_youtube_video_urls_are_normalised(url: str, expected: str | None) -> None:
    assert youtube_watch_url(url) == expected


def test_a_deleted_video_is_unreachable_even_though_the_watch_page_is_fine() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.path == "/oembed":
            return httpx.Response(404)
        return httpx.Response(200, text="<html>player shell</html>")

    resources = [resource(WATCH)]
    check(resources, handler)

    assert resources[0].link_status is LinkStatus.UNREACHABLE
    # The watch page was never used as evidence.
    assert all("/oembed" in url for url in seen)


def test_a_real_video_is_verified_through_oembed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["url"] == WATCH
        return httpx.Response(200, json={"title": "Loops in Python"})

    resources = [resource(WATCH)]
    check(resources, handler)

    assert resources[0].link_status is LinkStatus.VERIFIED


def test_an_oembed_server_error_says_nothing_about_the_video() -> None:
    resources = [resource(WATCH)]
    check(resources, lambda request: httpx.Response(503))

    assert resources[0].link_status is LinkStatus.UNCHECKED


def test_an_ordinary_page_is_checked_with_head() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        return httpx.Response(200)

    resources = [resource(BLOG)]
    check(resources, handler)

    assert methods == ["HEAD"]
    assert resources[0].link_status is LinkStatus.VERIFIED


def test_a_host_that_refuses_head_is_retried_with_get() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        return httpx.Response(405) if request.method == "HEAD" else httpx.Response(200)

    resources = [resource(BLOG)]
    check(resources, handler)

    assert methods == ["HEAD", "GET"]
    assert resources[0].link_status is LinkStatus.VERIFIED


def test_a_missing_page_is_unreachable() -> None:
    resources = [resource(BLOG)]
    check(resources, lambda request: httpx.Response(404))

    assert resources[0].link_status is LinkStatus.UNREACHABLE


def test_a_timeout_leaves_the_resource_unchecked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    resources = [resource(BLOG)]
    check(resources, handler)

    assert resources[0].link_status is LinkStatus.UNCHECKED


def test_every_resource_in_a_batch_is_checked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404 if "gone" in str(request.url) else 200)

    resources = [resource(BLOG), resource("https://example.dev/gone"), resource(WATCH)]
    check(resources, handler)

    assert [r.link_status for r in resources] == [
        LinkStatus.VERIFIED,
        LinkStatus.UNREACHABLE,
        LinkStatus.VERIFIED,
    ]


def test_the_off_switch_leaves_everything_unchecked(monkeypatch: pytest.MonkeyPatch) -> None:
    """An offline demo must not fail; it must be honest that nothing was checked."""
    monkeypatch.setenv("VERIFY_RESOURCE_LINKS", "false")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should be made when verification is off")

    resources = [resource(BLOG)]
    check(resources, handler)

    assert resources[0].link_status is LinkStatus.UNCHECKED


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "data:text/html,<h1>hi</h1>",
        "javascript:alert(1)",
        "ftp://example.dev/syllabus.pdf",
        "not a url at all",
    ],
)
def test_only_http_urls_are_ever_opened(url: str) -> None:
    """A scheme this module refuses must be refused by name, not by a library error."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"{request.url} should never have been fetched")

    resources = [resource(url)]
    check(resources, handler)

    # Nothing was tried, so nothing is known -- "unreachable" would claim we looked.
    assert resources[0].link_status is LinkStatus.UNCHECKED


def test_a_refused_scheme_does_not_stop_the_rest_of_the_batch() -> None:
    resources = [resource("file:///etc/passwd"), resource(BLOG)]
    check(resources, lambda request: httpx.Response(200))

    assert [r.link_status for r in resources] == [LinkStatus.UNCHECKED, LinkStatus.VERIFIED]


@pytest.mark.parametrize(
    "url",
    ["https://example.dev/x", "http://example.dev/x", "HTTPS://example.dev/x", "  https://a.dev  "],
)
def test_http_and_https_stay_fetchable(url: str) -> None:
    assert is_fetchable(url) is True
