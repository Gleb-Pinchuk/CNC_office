"""Синхронизация SectionTable ↔ Nextcloud WebDAV (общая логика для команды и Celery)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone as dj_tz

from bot_api.nextcloud_webdav import build_user_file_path, webdav_get, webdav_put
from bot_api.xlsx_sync import (
    content_to_excel_bytes,
    excel_bytes_to_content,
    merge_content_into_excel_bytes,
)
from sections.models import SectionTable


@dataclass
class NextcloudSyncConfig:
    key: str
    label: str
    base_url: str
    username: str
    password: str
    file_relative_path: str
    owner_username: str
    section_type: str
    title_fragment: str


def load_nextcloud_sync_config_from_env() -> Optional[NextcloudSyncConfig]:
    """Backward-compatible loader for a single sync config."""
    all_cfgs = load_nextcloud_sync_configs_from_env()
    return all_cfgs[0] if all_cfgs else None


def load_nextcloud_sync_configs_from_env() -> List[NextcloudSyncConfig]:
    """Load one or many sync configs from env.

    Preferred format:
    NEXTCLOUD_SYNC_GROUPS_JSON='[{"key":"prod","label":"...","file_relative_path":"...","title_fragment":"...","direction_sheets":[...]}]'

    Russian names can be passed as JSON unicode escapes (ASCII-safe), for example:
    "\\u0420\\u0435\\u0439\\u043d\\u0434..."
    """
    multi_raw = (os.getenv("NEXTCLOUD_SYNC_GROUPS_JSON") or "").strip()
    if multi_raw:
        try:
            parsed = json.loads(multi_raw)
            if not isinstance(parsed, list):
                raise ValueError("NEXTCLOUD_SYNC_GROUPS_JSON должен быть JSON-массивом")
            out: List[NextcloudSyncConfig] = []
            for idx, item in enumerate(parsed):
                if not isinstance(item, dict):
                    continue
                base = str(item.get("base_url") or os.getenv("NEXTCLOUD_BASE_URL") or "").strip().rstrip("/")
                user = str(item.get("username") or os.getenv("NEXTCLOUD_USERNAME") or "").strip()
                pwd = str(
                    item.get("password")
                    or os.getenv("NEXTCLOUD_PASSWORD")
                    or os.getenv("NEXTCLOUD_APP_TOKEN")
                    or ""
                ).strip()
                rel = str(item.get("file_relative_path") or item.get("file_path") or "").strip()
                owner = str(item.get("owner_username") or os.getenv("CNC_BOT_TABLE_OWNER_USERNAME") or "").strip()
                st = str(item.get("section_type") or os.getenv("CNC_SECTION_TYPE") or "rangers").strip()
                title = str(item.get("title_fragment") or "").strip()
                key = str(item.get("key") or f"group_{idx + 1}").strip()
                label = str(item.get("label") or key).strip()
                if not all([base, user, pwd, rel, owner, key]):
                    continue
                out.append(
                    NextcloudSyncConfig(
                        key=key,
                        label=label,
                        base_url=base,
                        username=user,
                        password=pwd,
                        file_relative_path=rel,
                        owner_username=owner,
                        section_type=st,
                        title_fragment=title,
                    )
                )
            if out:
                return out
        except Exception:
            # Не валим воркер: в случае ошибки формата используем single-config fallback.
            pass

    base = (os.getenv("NEXTCLOUD_BASE_URL") or "").strip().rstrip("/")
    user = (os.getenv("NEXTCLOUD_USERNAME") or "").strip()
    pwd = (os.getenv("NEXTCLOUD_PASSWORD") or os.getenv("NEXTCLOUD_APP_TOKEN") or "").strip()
    rel = (os.getenv("NEXTCLOUD_FILE_PATH") or os.getenv("NEXTCLOUD_XLSX_RELATIVE_PATH") or "").strip()
    owner = (os.getenv("CNC_BOT_TABLE_OWNER_USERNAME") or "").strip()
    st = (os.getenv("CNC_SECTION_TYPE") or "rangers").strip()
    title = (os.getenv("CNC_TABLE_TITLE_FRAGMENT") or "").strip()
    if not all([base, user, pwd, rel, owner]):
        return []
    return [
        NextcloudSyncConfig(
            key="default",
            label="default",
            base_url=base,
            username=user,
            password=pwd,
            file_relative_path=rel,
            owner_username=owner,
            section_type=st,
            title_fragment=title,
        )
    ]


def find_section_table(cfg: NextcloudSyncConfig) -> Optional[SectionTable]:
    User = get_user_model()
    owner = User.objects.filter(username=cfg.owner_username).first()
    if not owner:
        return None
    qs = SectionTable.objects.filter(owner=owner, section_type=cfg.section_type)
    if cfg.title_fragment:
        qs = qs.filter(title__icontains=cfg.title_fragment.strip().lower())
    table = qs.order_by("-updated_at").first()
    if not table and cfg.title_fragment:
        table = (
            SectionTable.objects.filter(owner=owner, section_type=cfg.section_type)
            .order_by("-updated_at")
            .first()
        )
    return table


def webdav_path_for_config(cfg: NextcloudSyncConfig) -> str:
    return build_user_file_path(cfg.username, cfg.file_relative_path)


def pull_from_nextcloud(cfg: NextcloudSyncConfig) -> Dict[str, Any]:
    path = webdav_path_for_config(cfg)
    raw, _etag = webdav_get(cfg.base_url, path, cfg.username, cfg.password)
    new_content = excel_bytes_to_content(raw)
    table = find_section_table(cfg)
    if not table:
        return {"ok": False, "error": "section_table_not_found"}
    with transaction.atomic():
        st = SectionTable.objects.select_for_update().get(pk=table.pk)
        if st.needs_nextcloud_push:
            return {
                "ok": True,
                "skipped": True,
                "reason": "local_pending_push",
                "table_id": table.pk,
                "action": "pull",
            }
        st.content = new_content
        st.needs_nextcloud_push = False
        st.save(update_fields=["content", "needs_nextcloud_push", "updated_at"])
    return {"ok": True, "table_id": table.pk, "action": "pull"}


def push_to_nextcloud(cfg: NextcloudSyncConfig, *, force: bool = False) -> Dict[str, Any]:
    table = find_section_table(cfg)
    if not table:
        return {"ok": False, "error": "section_table_not_found"}
    if not force and not table.needs_nextcloud_push:
        return {"ok": True, "skipped": True, "reason": "no_pending_push"}
    table.refresh_from_db()
    path = webdav_path_for_config(cfg)
    # Важно: сначала читаем текущий файл с Nextcloud и накладываем изменения поверх.
    # Это сохраняет форматирование, ширины колонок и листы вне зоны работы бота.
    remote_blob, _etag = webdav_get(cfg.base_url, path, cfg.username, cfg.password)
    if remote_blob:
        blob = merge_content_into_excel_bytes(remote_blob, table.content or {})
    else:
        blob = content_to_excel_bytes(table.content or {})
    webdav_put(cfg.base_url, path, cfg.username, cfg.password, blob)
    now = dj_tz.now()
    SectionTable.objects.filter(pk=table.pk).update(
        needs_nextcloud_push=False,
        last_nextcloud_push_at=now,
        updated_at=now,
    )
    return {"ok": True, "table_id": table.pk, "action": "push"}
