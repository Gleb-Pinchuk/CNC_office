from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

import requests
import yt_dlp
from yt_dlp.utils import DownloadError

logger = logging.getLogger(__name__)

_VK_HOSTS = ("vk.com", "vk.ru", "m.vk.com", "m.vk.ru")
_PLACEHOLDER_RE = re.compile(
    r"^[-–—._]+$"
    r"|^(нет|нету|н/?д|na|n/?a|none|null|no|отсутствует|пусто)$",
    re.IGNORECASE,
)


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


def is_placeholder_social_value(token: str) -> bool:
    t = (token or "").strip()
    if not t:
        return True
    if _PLACEHOLDER_RE.match(t):
        return True
    # @- / tiktok.com/@- / t.me/-
    nick = t.lstrip("@").strip()
    if _PLACEHOLDER_RE.match(nick):
        return True
    lower = t.lower()
    if any(
        lower.endswith(suf)
        for suf in (
            "tiktok.com/@-",
            "tiktok.com/@—",
            "t.me/-",
            "vk.com/-",
            "vk.ru/-",
        )
    ):
        return True
    return False


def _as_entries(source_url: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries = payload.get("entries")
    if isinstance(entries, list) and entries:
        return [item for item in entries if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def _platform(url: str) -> str:
    u = (url or "").lower()
    if "t.me/" in u or "telegram." in u:
        return "tg"
    if "tiktok.com/" in u:
        return "tiktok"
    if any(h in u for h in ("vk.com/", "vk.ru/", "m.vk.com/", "m.vk.ru/")):
        return "vk"
    return ""


def _normalize_vk_url(url: str) -> str:
    """vk.ru / m.vk.com → https://vk.com/..."""
    try:
        parsed = urlparse(url)
    except Exception:
        return url
    host = (parsed.netloc or "").lower().split(":")[0]
    if host in _VK_HOSTS or host.startswith("vk."):
        path = parsed.path or "/"
        return f"https://vk.com{path}"
    return url


def _parse_vk_owner(url: str) -> tuple[Optional[int], str]:
    """
    Вернуть (owner_id или None, screen_name).
    owner_id > 0 — пользователь, < 0 — сообщество.
    """
    path = urlparse(_normalize_vk_url(url)).path.strip("/")
    if not path:
        return None, ""
    # wall-123_456 or wall123_456 — берём owner из wall
    m = re.match(r"^wall(-?\d+)_(\d+)$", path, re.I)
    if m:
        return int(m.group(1)), ""
    m = re.match(r"^(id|club|public|event)(\d+)$", path, re.I)
    if m:
        kind, num = m.group(1).lower(), int(m.group(2))
        if kind == "id":
            return num, ""
        return -num, ""
    # screen name
    screen = path.split("/")[0].split("?")[0]
    if not screen or is_placeholder_social_value(screen):
        return None, ""
    return None, screen


def _vk_api(method: str, token: str, **params) -> dict[str, Any]:
    resp = requests.get(
        f"https://api.vk.com/method/{method}",
        params={**params, "access_token": token, "v": "5.199"},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        err = data["error"]
        raise RuntimeError(
            f"VK API {method}: {err.get('error_code')} {err.get('error_msg')}"
        )
    return data.get("response") or {}


def _best_photo_url(attachment: dict[str, Any]) -> str:
    photo = attachment.get("photo") or {}
    sizes = photo.get("sizes") or []
    if not isinstance(sizes, list) or not sizes:
        return str(photo.get("photo_2560") or photo.get("photo_1280") or "").strip()
    best = max(sizes, key=lambda s: int(s.get("width") or 0) * int(s.get("height") or 0))
    return str(best.get("url") or "").strip()


def fetch_vk_wall_entries(
    source_url: str,
    max_entries: int,
    token: str = "",
) -> FetchResult:
    token = (token or os.getenv("VK_TOKEN") or "").strip()
    if not token:
        return FetchResult([], error="vk_no_token")

    url = _normalize_vk_url(source_url)
    owner_id, screen = _parse_vk_owner(url)
    try:
        if owner_id is None and screen:
            resolved = _vk_api("utils.resolveScreenName", token, screen_name=screen)
            if not resolved:
                return FetchResult([], error="vk_screen_not_found")
            rtype = str(resolved.get("type") or "")
            rid = int(resolved.get("object_id") or 0)
            if rtype == "user":
                owner_id = rid
            elif rtype in ("group", "page", "event"):
                owner_id = -rid
            else:
                return FetchResult([], error=f"vk_unsupported_type:{rtype}")
        if owner_id is None:
            return FetchResult([], error="vk_bad_url")

        response = _vk_api(
            "wall.get",
            token,
            owner_id=owner_id,
            count=max(1, min(int(max_entries), 20)),
            filter="owner",
        )
    except Exception as exc:
        msg = str(exc)[:180]
        logger.warning("VK wall fetch failed for %s: %s", url, msg)
        return FetchResult([], error=msg or "vk_api_error")

    items = response.get("items") if isinstance(response, dict) else []
    if not isinstance(items, list):
        items = []

    out: list[SocialEntry] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        # пропускаем репосты без собственного текста — всё равно берём copy_history text
        text = str(item.get("text") or "").strip()
        if not text:
            copies = item.get("copy_history") or []
            if isinstance(copies, list) and copies and isinstance(copies[0], dict):
                text = str(copies[0].get("text") or "").strip()
        post_id = item.get("id")
        oid = item.get("owner_id", owner_id)
        post_url = f"https://vk.com/wall{oid}_{post_id}" if post_id is not None else url
        thumb = ""
        for att in item.get("attachments") or []:
            if not isinstance(att, dict):
                continue
            if att.get("type") == "photo":
                thumb = _best_photo_url(att)
                if thumb:
                    break
            if att.get("type") == "video":
                video = att.get("video") or {}
                images = video.get("image")
                if isinstance(images, list) and images:
                    thumb = str(images[-1].get("url") or "").strip()
                if not thumb:
                    thumb = str(
                        video.get("photo_800") or video.get("photo_320") or ""
                    ).strip()
                if thumb:
                    break
        out.append(
            SocialEntry(
                source_url=source_url,
                post_url=post_url,
                title="",
                description=text,
                thumbnail_url=thumb,
            )
        )
    if not out:
        return FetchResult([], error="vk_empty_wall")
    return FetchResult(out)


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
    if is_placeholder_social_value(source_url):
        return FetchResult([], error="placeholder")

    platform = _platform(source_url)
    if platform == "vk":
        return fetch_vk_wall_entries(source_url, max_entries)

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
