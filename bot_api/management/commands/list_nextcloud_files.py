"""Рекурсивный PROPFIND по Nextcloud, чтобы найти реальный путь к xlsx."""

import os
import xml.etree.ElementTree as ET

import requests
from django.core.management.base import BaseCommand, CommandError
from requests.auth import HTTPBasicAuth


NS = {"d": "DAV:"}


class Command(BaseCommand):
    help = "Перечисляет файлы/папки в Nextcloud (WebDAV PROPFIND). Помогает найти NEXTCLOUD_FILE_PATH."

    def add_arguments(self, parser):
        parser.add_argument("--path", default="", help="Относительный путь внутри домашнего каталога (по умолчанию корень).")
        parser.add_argument("--depth", type=int, default=2, help="Глубина обхода (1=только текущая папка). По умолчанию 2.")
        parser.add_argument("--ext", default=".xlsx", help="Показать только файлы с таким расширением (пусто — показывать всё).")

    def handle(self, *args, **options):
        base = os.getenv("NEXTCLOUD_BASE_URL", "").rstrip("/")
        user = os.getenv("NEXTCLOUD_USERNAME", "")
        pwd = os.getenv("NEXTCLOUD_PASSWORD", "") or os.getenv("NEXTCLOUD_APP_TOKEN", "")
        if not base or not user or not pwd:
            raise CommandError("Нужны NEXTCLOUD_BASE_URL, NEXTCLOUD_USERNAME, NEXTCLOUD_PASSWORD/TOKEN в окружении.")

        ext = (options.get("ext") or "").lower().strip()
        max_depth = int(options.get("depth") or 2)
        start_rel = (options.get("path") or "").strip().strip("/").replace("\\", "/")

        auth = HTTPBasicAuth(user, pwd)
        headers = {"OCS-APIRequest": "true", "Depth": "1", "Content-Type": "text/xml"}

        user_root = f"/remote.php/dav/files/{user}"
        start_abs_rel = "/".join([p for p in (user_root + "/" + start_rel).split("/") if p])
        start_abs_rel = "/" + start_abs_rel + ("/" if start_rel else "/")

        def propfind(href: str):
            url = base + href
            r = requests.request("PROPFIND", url, auth=auth, headers=headers, timeout=30)
            if r.status_code not in (207, 200):
                self.stdout.write(self.style.WARNING(f"PROPFIND {url} -> {r.status_code}"))
                return []
            root = ET.fromstring(r.content)
            out = []
            for resp in root.findall("d:response", NS):
                h = resp.find("d:href", NS)
                if h is None:
                    continue
                href_val = h.text or ""
                is_dir = False
                for prop in resp.findall("d:propstat/d:prop", NS):
                    rt = prop.find("d:resourcetype", NS)
                    if rt is not None and rt.find("d:collection", NS) is not None:
                        is_dir = True
                out.append((href_val, is_dir))
            return out

        visited = set()

        def walk(href: str, depth: int):
            if href in visited:
                return
            visited.add(href)
            if depth > max_depth:
                return
            items = propfind(href)
            for child_href, is_dir in items:
                if child_href.rstrip("/") == href.rstrip("/"):
                    continue  # саму папку не показываем
                rel = requests.utils.unquote(child_href)
                if is_dir:
                    self.stdout.write(f"[DIR ] {rel}")
                    walk(child_href, depth + 1)
                else:
                    if not ext or rel.lower().endswith(ext):
                        self.stdout.write(self.style.SUCCESS(f"[FILE] {rel}"))

        self.stdout.write(f"Старт: {base}{start_abs_rel} (depth={max_depth}, ext='{ext}')")
        walk(start_abs_rel, 1)
        self.stdout.write(
            "\nПодсказка: путь для NEXTCLOUD_FILE_PATH = всё, что ПОСЛЕ '/remote.php/dav/files/USER/'."
        )
