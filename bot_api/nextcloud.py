import base64
import json
import logging
import posixpath
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)


class NextcloudWriteError(RuntimeError):
    pass


class NextcloudEventWriter:
    """
    Writes bot events to Nextcloud via WebDAV as immutable JSON files.
    Uses stdlib urllib to avoid external runtime dependency.
    """

    def __init__(self):
        self.enabled = bool(getattr(settings, "NEXTCLOUD_BOT_WRITE_ENABLED", False))
        self.strict = bool(getattr(settings, "NEXTCLOUD_BOT_WRITE_STRICT", False))
        self.base_url = (getattr(settings, "NEXTCLOUD_BASE_URL", "") or "").rstrip("/")
        self.username = getattr(settings, "NEXTCLOUD_USERNAME", "") or ""
        self.password = getattr(settings, "NEXTCLOUD_APP_PASSWORD", "") or ""
        self.root_path = (
            getattr(settings, "NEXTCLOUD_BOT_ROOT", "CNC_office/vk_bot") or ""
        ).strip("/")
        self.timeout = int(getattr(settings, "NEXTCLOUD_TIMEOUT_SECONDS", 10))
        self.retry_count = int(getattr(settings, "NEXTCLOUD_RETRY_COUNT", 2))

    def _auth_header(self) -> str:
        token = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8"))
        return f"Basic {token.decode('ascii')}"

    def _request(
        self, method: str, url: str, data: Optional[bytes] = None, content_type: str = ""
    ) -> int:
        headers = {"Authorization": self._auth_header()}
        if content_type:
            headers["Content-Type"] = content_type
        req = Request(url=url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                return int(getattr(resp, "status", 200))
        except HTTPError as exc:
            return exc.code
        except URLError as exc:
            raise NextcloudWriteError(str(exc)) from exc

    def _validate(self) -> None:
        if not self.enabled:
            return
        missing = []
        if not self.base_url:
            missing.append("NEXTCLOUD_BASE_URL")
        if not self.username:
            missing.append("NEXTCLOUD_USERNAME")
        if not self.password:
            missing.append("NEXTCLOUD_APP_PASSWORD")
        if missing:
            raise NextcloudWriteError(
                f"Nextcloud writer misconfigured, missing: {', '.join(missing)}"
            )

    def _dav_root(self) -> str:
        parsed = urlsplit(self.base_url)
        if not parsed.scheme or not parsed.netloc:
            raise NextcloudWriteError("NEXTCLOUD_BASE_URL must include scheme and host")
        return (
            f"{parsed.scheme}://{parsed.netloc}/remote.php/dav/files/"
            f"{quote(self.username, safe='')}"
        )

    def _mkcol(self, full_url: str) -> None:
        code = self._request("MKCOL", full_url)
        if code in (201, 301, 302, 307, 308, 405):
            return
        raise NextcloudWriteError(f"MKCOL failed ({code}) for {full_url}")

    def _ensure_dirs(self, rel_parts) -> None:
        current_rel = ""
        base = self._dav_root()
        for part in rel_parts:
            current_rel = posixpath.join(current_rel, part)
            self._mkcol(f"{base}/{quote(current_rel, safe='/')}")

    def _put_json(self, rel_path: str, payload: Dict) -> None:
        url = f"{self._dav_root()}/{quote(rel_path, safe='/')}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last_error = None
        for _ in range(self.retry_count + 1):
            code = self._request("PUT", url, data=body, content_type="application/json")
            if code in (200, 201, 204):
                return
            last_error = NextcloudWriteError(f"PUT failed ({code}) for {rel_path}")
        raise last_error or NextcloudWriteError(f"PUT failed for {rel_path}")

    def write_set_cell_event(self, payload: Dict) -> None:
        if not self.enabled:
            return
        self._validate()
        now = datetime.now(timezone.utc)
        date_parts = [f"{now.year:04d}", f"{now.month:02d}", f"{now.day:02d}"]
        self._ensure_dirs([self.root_path, *date_parts])
        event_id = uuid.uuid4().hex
        filename = (
            f"{now.strftime('%H%M%S')}_{payload.get('table_id', 'table')}_{event_id}.json"
        )
        rel_path = posixpath.join(self.root_path, *date_parts, filename)
        self._put_json(rel_path, payload)

    def safe_write_set_cell_event(self, payload: Dict) -> None:
        if not self.enabled:
            return
        try:
            self.write_set_cell_event(payload)
        except Exception as exc:  # noqa: BLE001 - keep bot writes resilient by default
            if self.strict:
                raise
            logger.exception("Nextcloud write failed, continuing: %s", exc)
