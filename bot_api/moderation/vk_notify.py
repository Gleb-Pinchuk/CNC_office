"""Отправка прогресса ИИ-скана инициатору в VK."""

from __future__ import annotations

import logging
import os
import random
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def send_vk_message(peer_id: int, text: str) -> None:
    token = (os.getenv("VK_TOKEN") or "").strip()
    if not token or not peer_id:
        logger.warning("VK notify skipped: no token or peer_id")
        return
    try:
        import vk_api

        session = vk_api.VkApi(token=token)
        session.method(
            "messages.send",
            {
                "peer_id": int(peer_id),
                "message": text[:4000],
                "random_id": random.randint(0, 2**31),
            },
        )
    except Exception:
        logger.exception("VK progress send failed peer=%s", peer_id)


def make_progress_notifier(
    peer_id: Optional[int],
    *,
    sheet_name: str,
    min_interval_sec: float = 25.0,
    step_pct: int = 10,
) -> Callable[[dict[str, Any]], None]:
    """
    Колбэк прогресса: шлёт старт/промежуточные %/финал только peer_id.
    Не чаще min_interval_sec и только на границах step_pct (кроме финала).
    """
    state = {"last_pct_sent": -1, "last_ts": 0.0, "started": False}

    def notify(info: dict[str, Any]) -> None:
        if not peer_id:
            return
        done = bool(info.get("done"))
        pct = int(info.get("pct") or 0)
        checked = int(info.get("checked") or 0)
        total = int(info.get("total") or 0)
        flagged = int(info.get("flagged") or 0)
        evidence = int(info.get("evidence") or 0)
        direction = str(info.get("sheet_name") or sheet_name)

        diagnostic = bool(info.get("diagnostic"))
        mode = "диагностика" if diagnostic else "проверка ИИ"

        if done:
            if diagnostic:
                with_links = int(info.get("with_links") or 0)
                links_tried = int(info.get("links_tried") or 0)
                links_ok = int(info.get("links_ok") or 0)
                links_fail = int(info.get("links_fail") or 0)
                links_skipped = int(info.get("links_skipped") or 0)
                posts = int(info.get("posts") or 0)
                cols = info.get("social_cols") or []
                sample_errors = info.get("sample_errors") or []
                sample_links = info.get("sample_links") or []
                lines = [
                    f"🔎 Диагностика ИИ завершена",
                    f"Направление: {direction}",
                    f"Студентов: {checked}" + (f" / {total}" if total else ""),
                    f"С ссылками: {with_links}",
                    f"Ссылок: ok {links_ok} / fail {links_fail} "
                    f"(tried {links_tried}, skip {links_skipped})",
                    f"Постов получено: {posts}",
                    f"Срабатываний правил: {flagged}",
                    f"Колонки соцсетей: {cols}",
                    f"skip_tg={info.get('skip_tg')} skip_tiktok={info.get('skip_tiktok')} "
                    f"proxy={'да' if info.get('proxy') else 'нет'}",
                    "",
                    "В таблицу ничего не записано.",
                ]
                if sample_links:
                    lines.append("Примеры ссылок:")
                    lines.extend(f"· {x}" for x in sample_links[:3])
                if sample_errors:
                    lines.append("Ошибки yt-dlp:")
                    lines.extend(f"· {x}" for x in sample_errors[:3])
                send_vk_message(int(peer_id), "\n".join(lines))
            else:
                send_vk_message(
                    int(peer_id),
                    (
                        f"✅ Проверка ИИ завершена\n"
                        f"Направление: {direction}\n"
                        f"Проверено: {checked}"
                        + (f" / {total}" if total else "")
                        + f"\nС замечаниями: {flagged}\n"
                        f"Скринов сохранено: {evidence}\n\n"
                        f"Можно нажать «Отчет Word»."
                    ),
                )
            return

        if not state["started"]:
            state["started"] = True
            state["last_ts"] = time.monotonic()
            state["last_pct_sent"] = 0
            send_vk_message(
                int(peer_id),
                (
                    f"⏳ {'Диагностика' if diagnostic else 'Проверка ИИ'} запущена\n"
                    f"Направление: {direction}\n"
                    f"Студентов в листе: {total or '—'}\n"
                    + (
                        "Режим без записи в таблицу.\n"
                        if diagnostic
                        else "Прогресс буду присылать по ходу…"
                    )
                ),
            )
            return

        bucket = (pct // step_pct) * step_pct
        now = time.monotonic()
        if bucket <= state["last_pct_sent"]:
            return
        if now - state["last_ts"] < min_interval_sec and bucket < 100:
            return
        state["last_pct_sent"] = bucket
        state["last_ts"] = now
        extra = ""
        if diagnostic:
            extra = (
                f"\nСсылки ok/fail: {int(info.get('links_ok') or 0)}/"
                f"{int(info.get('links_fail') or 0)}"
            )
        send_vk_message(
            int(peer_id),
            (
                f"⏳ {mode.capitalize()}: {bucket}%\n"
                f"Направление: {direction}\n"
                f"Проверено: {checked}/{total or '?'}\n"
                f"Срабатываний: {flagged}{extra}"
            ),
        )

    return notify
