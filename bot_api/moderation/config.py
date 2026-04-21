from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings


@dataclass(frozen=True)
class ModerationConfig:
    table_owner_username: str
    section_type: str
    title_fragment: str
    social_cols: list[int]
    fio_col: int
    group_col: int
    status_col: int
    remark_col: int
    rules_path: Path
    max_entries_per_link: int
    max_links_per_student: int
    block_hash_distance: int
    allow_hash_distance: int
    request_timeout_sec: int
    ytdlp_timeout_sec: int
    proxy_url: str
    skip_tg: bool
    skip_tiktok: bool


def _parse_int_list(raw: str, fallback: str) -> list[int]:
    out: list[int] = []
    value = raw or fallback
    for token in str(value).split(","):
        token = token.strip()
        if not token:
            continue
        try:
            out.append(int(token))
        except ValueError:
            continue
    return out


def load_moderation_config() -> ModerationConfig:
    owner = os.getenv(
        "CNC_BOT_TABLE_OWNER_USERNAME", getattr(settings, "CNC_BOT_TABLE_OWNER_USERNAME", "")
    ).strip()
    social_cols = _parse_int_list(
        os.getenv("BOT_SHEET_SOCIAL_COLS", ""),
        getattr(settings, "BOT_SHEET_SOCIAL_COLS", "13,14,15"),
    )
    default_rules_path = settings.BASE_DIR / "bot_api" / "moderation_data" / "rules.json"
    rules_path = Path(os.getenv("SOCIAL_MOD_RULES_PATH", str(default_rules_path)))
    return ModerationConfig(
        table_owner_username=owner,
        section_type=os.getenv("CNC_SECTION_TYPE", "rangers").strip(),
        title_fragment=os.getenv("CNC_TABLE_TITLE_FRAGMENT", "").strip(),
        social_cols=social_cols,
        fio_col=int(os.getenv("BOT_SHEET_FIO_COL", getattr(settings, "BOT_SHEET_FIO_COL", 2))),
        group_col=int(
            os.getenv("BOT_SHEET_GROUP_COL", getattr(settings, "BOT_SHEET_GROUP_COL", 1))
        ),
        status_col=int(
            os.getenv("BOT_SHEET_STATUS_COL", getattr(settings, "BOT_SHEET_STATUS_COL", 11))
        ),
        remark_col=int(
            os.getenv("BOT_SHEET_REMARK_COL", getattr(settings, "BOT_SHEET_REMARK_COL", 12))
        ),
        rules_path=rules_path,
        max_entries_per_link=int(os.getenv("SOCIAL_MOD_MAX_ENTRIES_PER_LINK", "5")),
        max_links_per_student=int(os.getenv("SOCIAL_MOD_MAX_LINKS_PER_STUDENT", "3")),
        block_hash_distance=int(os.getenv("SOCIAL_MOD_BLOCK_HASH_DISTANCE", "6")),
        allow_hash_distance=int(os.getenv("SOCIAL_MOD_ALLOW_HASH_DISTANCE", "4")),
        request_timeout_sec=int(os.getenv("SOCIAL_MOD_REQUEST_TIMEOUT_SEC", "10")),
        ytdlp_timeout_sec=int(os.getenv("SOCIAL_MOD_YTDLP_TIMEOUT_SEC", "20")),
        proxy_url=os.getenv("SOCIAL_MOD_PROXY_URL", "").strip(),
        skip_tg=os.getenv("SOCIAL_MOD_SKIP_TG", "False").lower() in ("true", "1", "yes"),
        skip_tiktok=os.getenv("SOCIAL_MOD_SKIP_TIKTOK", "False").lower()
        in ("true", "1", "yes"),
    )

