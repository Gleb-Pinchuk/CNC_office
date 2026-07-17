from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError

logger = logging.getLogger(__name__)


@dataclass
class SocialEntry:
    source_url: str
    post_url: str
    title: str
    description: str
    thumbnail_url: str

    @property
    def text(self) -> str:
        return " ".join([self.title, self.description]).strip().lower()


@dataclass
class FetchResult:
    entries: list[SocialEntry]
    error: str = ""


def _as_entries(source_url: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries = payload.get("entries")
    if isinstance(entries, list) and entries:
        return [item for item in entries if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def fetch_social_entries(
    source_url: str,
    max_entries: int,
    timeout_sec: int,
    proxy_url: str = "",
) -> list[SocialEntry]:
    return fetch_social_entries_result(
        source_url, max_entries, timeout_sec, proxy_url=proxy_url
    ).entries


def fetch_social_entries_result(
    source_url: str,
    max_entries: int,
    timeout_sec: int,
    proxy_url: str = "",
) -> FetchResult:
    options = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": False,
        "playlistend": max_entries,
        "socket_timeout": timeout_sec,
        "noplaylist": False,
        "retries": 0,
        "extractor_retries": 0,
    }
    if proxy_url:
        options["proxy"] = proxy_url
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(source_url, download=False)
    except DownloadError as exc:
        msg = str(exc)
        if "Unsupported URL" in msg:
            logger.warning("yt-dlp unsupported url: %s", source_url)
            return FetchResult([], error="unsupported_url")
        logger.warning("yt-dlp download error for %s: %s", source_url, msg[:240])
        return FetchResult([], error=msg[:180] or "download_error")
    except Exception as exc:
        logger.exception("yt-dlp failed for %s", source_url)
        return FetchResult([], error=str(exc)[:180] or "ytdlp_exception")

    out: list[SocialEntry] = []
    for item in _as_entries(source_url, info)[:max_entries]:
        post_url = str(item.get("webpage_url") or item.get("url") or source_url).strip()
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        thumb = str(item.get("thumbnail") or "").strip()
        out.append(
            SocialEntry(
                source_url=source_url,
                post_url=post_url,
                title=title,
                description=description,
                thumbnail_url=thumb,
            )
        )
    if not out:
        return FetchResult([], error="empty_extract")
    return FetchResult(out)
