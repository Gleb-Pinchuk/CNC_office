from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import yt_dlp

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


def _as_entries(source_url: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries = payload.get("entries")
    if isinstance(entries, list) and entries:
        return [item for item in entries if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def fetch_social_entries(source_url: str, max_entries: int, timeout_sec: int) -> list[SocialEntry]:
    options = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": False,
        "playlistend": max_entries,
        "socket_timeout": timeout_sec,
        "noplaylist": False,
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(source_url, download=False)
    except Exception:
        logger.exception("yt-dlp failed for %s", source_url)
        return []

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
    return out

