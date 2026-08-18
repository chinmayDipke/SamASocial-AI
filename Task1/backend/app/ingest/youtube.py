"""YouTube ingestion via captions.

Captions are used rather than audio transcription: they are free, instant, and
already timestamped, which is what makes "at 3:22" citations possible. When a video
has no captions at all we say so explicitly instead of failing vaguely -- audio
transcription needs ffmpeg, which is behind the `ENABLE_AUDIO_FALLBACK` flag.
"""

from __future__ import annotations

import asyncio
import re

import httpx
from youtube_transcript_api import (
    AgeRestricted,
    CouldNotRetrieveTranscript,
    IpBlocked,
    NoTranscriptFound,
    PoTokenRequired,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApi,
)

from ..config import get_settings
from ..schemas import Segment, SourceKind
from .base import IngestError, IngestResult, ensure_not_empty

_PREFERRED_LANGUAGES = ("en", "en-US", "en-GB")
_SEGMENT_TARGET_CHARS = 500

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_URL_PATTERNS = (
    re.compile(r"(?:youtube\.com|youtube-nocookie\.com)/watch\?(?:.*&)?v=([A-Za-z0-9_-]{11})"),
    re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})"),
    re.compile(r"youtube\.com/(?:embed|shorts|v|live)/([A-Za-z0-9_-]{11})"),
)


def is_youtube_url(url: str) -> bool:
    return extract_video_id(url) is not None


def extract_video_id(url: str) -> str | None:
    candidate = url.strip()
    if _VIDEO_ID_RE.match(candidate):
        return candidate
    for pattern in _URL_PATTERNS:
        match = pattern.search(candidate)
        if match:
            return match.group(1)
    return None


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _fetch_snippets(video_id: str) -> list[dict]:
    """Fetch the best available caption track, translating to English if needed."""
    api = YouTubeTranscriptApi()
    try:
        return api.fetch(video_id, languages=_PREFERRED_LANGUAGES).to_raw_data()
    except NoTranscriptFound:
        pass  # No English track; fall through to whatever the video does have.
    except TranscriptsDisabled as exc:
        raise IngestError(
            "This video has captions disabled, so there is no transcript to read. "
            "Try a video with captions, or use a different source."
        ) from exc
    except (VideoUnavailable, AgeRestricted) as exc:
        raise IngestError("This video is unavailable or age restricted, so it cannot be read.") from exc
    except (IpBlocked, RequestBlocked, PoTokenRequired) as exc:
        raise IngestError(
            "YouTube is currently blocking transcript requests from this network. "
            "Try again later or use a different source."
        ) from exc

    try:
        available = list(YouTubeTranscriptApi().list(video_id))
        if not available:
            raise IngestError("This video has no caption tracks, so there is no transcript to read.")
        # Prefer a human-written track; fall back to auto-generated captions.
        transcript = next((t for t in available if not t.is_generated), available[0])
        if transcript.language_code not in _PREFERRED_LANGUAGES and transcript.is_translatable:
            transcript = transcript.translate("en")
        return transcript.fetch().to_raw_data()
    except CouldNotRetrieveTranscript as exc:
        raise IngestError(
            f"The transcript for this video could not be retrieved ({type(exc).__name__})."
        ) from exc


def _group_snippets(snippets: list[dict]) -> list[Segment]:
    """Merge caption cues into readable windows, anchored at the window's start time."""
    segments: list[Segment] = []
    buffer: list[str] = []
    start_time = 0.0
    length = 0

    for snippet in snippets:
        text = (snippet.get("text") or "").replace("\n", " ").strip()
        if not text:
            continue
        if not buffer:
            start_time = float(snippet.get("start", 0.0))
        buffer.append(text)
        length += len(text) + 1
        if length >= _SEGMENT_TARGET_CHARS:
            segments.append(
                Segment(
                    text=" ".join(buffer),
                    position=int(start_time),
                    locator=format_timestamp(start_time),
                )
            )
            buffer, length = [], 0

    if buffer:
        segments.append(
            Segment(
                text=" ".join(buffer),
                position=int(start_time),
                locator=format_timestamp(start_time),
            )
        )
    return segments


async def _fetch_title(video_id: str) -> str:
    """Look up the video title through oEmbed (no API key required)."""
    settings = get_settings()
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.get(url)
            response.raise_for_status()
            return str(response.json().get("title") or f"YouTube video {video_id}")
    except (httpx.HTTPError, ValueError):
        return f"YouTube video {video_id}"


async def ingest_youtube(url: str) -> IngestResult:
    video_id = extract_video_id(url)
    if not video_id:
        raise IngestError("That does not look like a YouTube video URL.")

    snippets, title = await asyncio.gather(
        asyncio.to_thread(_fetch_snippets, video_id),
        _fetch_title(video_id),
    )

    result = IngestResult(
        kind=SourceKind.YOUTUBE,
        title=title,
        segments=_group_snippets(snippets),
        url=f"https://www.youtube.com/watch?v={video_id}",
    )
    return ensure_not_empty(result, "This video's transcript came back empty.")
