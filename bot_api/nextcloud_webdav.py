"""WebDAV GET/PUT для файла в Nextcloud."""

from __future__ import annotations

import logging
import urllib.parse
from typing import Optional, Tuple

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


def _join_webdav_url(base_url: str, webdav_path: str) -> str:
    base = base_url.rstrip("/")
    path = webdav_path if webdav_path.startswith("/") else f"/{webdav_path}"
    return f"{base}{path}"


def webdav_get(
    base_url: str,
    webdav_path: str,
    username: str,
    password: str,
    timeout: int = 60,
) -> Tuple[bytes, Optional[str]]:
    """
    Скачивает файл. webdav_path — путь вида /remote.php/dav/files/user/file.xlsx
    Возвращает (body, etag или None).
    """
    url = _join_webdav_url(base_url, webdav_path)
    r = requests.get(
        url,
        auth=HTTPBasicAuth(username, password),
        timeout=timeout,
        headers={"OCS-APIRequest": "true"},
    )
    r.raise_for_status()
    etag = r.headers.get("ETag") or r.headers.get("etag")
    return r.content, etag


def webdav_put(
    base_url: str,
    webdav_path: str,
    username: str,
    password: str,
    body: bytes,
    timeout: int = 120,
) -> None:
    url = _join_webdav_url(base_url, webdav_path)
    r = requests.put(
        url,
        data=body,
        auth=HTTPBasicAuth(username, password),
        timeout=timeout,
        headers={
            "OCS-APIRequest": "true",
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
    )
    if r.status_code >= 400:
        logger.error("WebDAV PUT failed: %s %s", r.status_code, r.text[:500])
    r.raise_for_status()


def build_user_file_path(username: str, relative_path: str) -> str:
    """
    Строит путь WebDAV к файлу в домашнем каталоге пользователя Nextcloud.
    relative_path — например Shared/foo.xlsx или table.xlsx (без ведущего /)
    """
    parts = [p for p in relative_path.replace("\\", "/").split("/") if p]
    enc = "/".join(urllib.parse.quote(p, safe="") for p in parts)
    return f"/remote.php/dav/files/{urllib.parse.quote(username, safe='')}/{enc}"
