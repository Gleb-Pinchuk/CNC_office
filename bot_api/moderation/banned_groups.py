"""Запрещённые сообщества VK для сверки вступлений."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BannedVkGroup:
    group_id: int  # положительный id сообщества
    screen_name: str
    title: str
    category: str
    remark: str


@dataclass
class BannedVkGroups:
    by_id: dict[int, BannedVkGroup]
    by_screen: dict[str, BannedVkGroup]

    def match(self, group_id: int, screen_name: str = "") -> Optional[BannedVkGroup]:
        gid = abs(int(group_id))
        if gid in self.by_id:
            return self.by_id[gid]
        screen = (screen_name or "").strip().lower()
        if screen and screen in self.by_screen:
            return self.by_screen[screen]
        return None

    @property
    def count(self) -> int:
        return len(self.by_id)


def load_banned_vk_groups(path: Path) -> BannedVkGroups:
    by_id: dict[int, BannedVkGroup] = {}
    by_screen: dict[str, BannedVkGroup] = {}
    if not path.exists():
        logger.warning("Banned VK groups file missing: %s", path)
        return BannedVkGroups(by_id=by_id, by_screen=by_screen)
    try:
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except Exception:
        logger.exception("Failed to load banned VK groups from %s", path)
        return BannedVkGroups(by_id=by_id, by_screen=by_screen)

    raw_groups = payload.get("groups") if isinstance(payload, dict) else payload
    if not isinstance(raw_groups, list):
        return BannedVkGroups(by_id=by_id, by_screen=by_screen)

    for item in raw_groups:
        if not isinstance(item, dict):
            continue
        try:
            gid = abs(int(item.get("id") or item.get("group_id") or 0))
        except (TypeError, ValueError):
            continue
        if not gid:
            continue
        screen = str(item.get("screen_name") or "").strip().lstrip("@").lower()
        title = str(item.get("title") or "").strip()
        category = str(item.get("category") or "").strip().lower()
        remark = str(item.get("remark") or "состоит в запрещённом сообществе").strip()
        entry = BannedVkGroup(
            group_id=gid,
            screen_name=screen,
            title=title,
            category=category,
            remark=remark,
        )
        by_id[gid] = entry
        if screen:
            by_screen[screen] = entry

    logger.info("Loaded %s banned VK groups from %s", len(by_id), path)
    return BannedVkGroups(by_id=by_id, by_screen=by_screen)
