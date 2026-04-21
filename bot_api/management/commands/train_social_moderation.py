from __future__ import annotations

import io
from pathlib import Path

import imagehash
import requests
from PIL import Image
from django.core.management.base import BaseCommand, CommandError

from bot_api.moderation.config import load_moderation_config
from bot_api.moderation.rules_store import load_rules, save_rules


class Command(BaseCommand):
    help = "Простое обучение правил модерации: ключевые слова и image hash."

    def add_arguments(self, parser):
        parser.add_argument("--add-keyword", default="", help="Добавить запрещенное слово/фразу.")
        parser.add_argument(
            "--remove-keyword",
            default="",
            help="Удалить слово/фразу из списка запрещенных.",
        )
        parser.add_argument(
            "--label",
            choices=["blocked", "allowed"],
            default="",
            help="Куда записать hash изображения (blocked|allowed).",
        )
        parser.add_argument("--image", default="", help="Путь к изображению для hash.")
        parser.add_argument("--image-url", default="", help="URL изображения для hash.")

    def _read_image_bytes(self, image_path: str, image_url: str) -> bytes:
        if image_path:
            p = Path(image_path)
            if not p.exists():
                raise CommandError(f"Файл не найден: {image_path}")
            return p.read_bytes()
        if image_url:
            try:
                resp = requests.get(image_url, timeout=15)
                resp.raise_for_status()
            except Exception as exc:
                raise CommandError(f"Не удалось скачать изображение: {image_url}") from exc
            return resp.content
        raise CommandError("Нужно указать --image или --image-url")

    def handle(self, *args, **options):
        cfg = load_moderation_config()
        rules = load_rules(cfg.rules_path)

        add_kw = options["add_keyword"].strip().lower()
        if add_kw:
            rules.keywords.append(add_kw)

        remove_kw = options["remove_keyword"].strip().lower()
        if remove_kw:
            rules.keywords = [kw for kw in rules.keywords if kw != remove_kw]

        label = options["label"].strip()
        if label:
            payload = self._read_image_bytes(options["image"].strip(), options["image_url"].strip())
            image = Image.open(io.BytesIO(payload)).convert("RGB")
            ph = str(imagehash.phash(image)).lower()
            if label == "blocked":
                rules.blocked_hashes.append(ph)
            else:
                rules.allowed_hashes.append(ph)
            self.stdout.write(self.style.SUCCESS(f"Добавлен hash={ph} в {label}"))

        save_rules(cfg.rules_path, rules)
        self.stdout.write(
            self.style.SUCCESS(
                f"Сохранено: keywords={len(set(rules.keywords))}, "
                f"blocked={len(set(rules.blocked_hashes))}, "
                f"allowed={len(set(rules.allowed_hashes))}"
            )
        )

