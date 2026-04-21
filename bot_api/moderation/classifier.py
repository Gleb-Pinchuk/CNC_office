from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional

import imagehash
import requests
from PIL import Image

from .rules_store import ModerationRules
from .social_scan import SocialEntry


@dataclass
class MatchResult:
    is_violation: bool
    reason: str
    post_url: str


class LightweightClassifier:
    def __init__(
        self,
        rules: ModerationRules,
        block_hash_distance: int,
        allow_hash_distance: int,
        timeout_sec: int,
    ):
        self.rules = rules
        self.block_hash_distance = block_hash_distance
        self.allow_hash_distance = allow_hash_distance
        self.timeout_sec = timeout_sec

    @staticmethod
    def _distance_to_set(ph: imagehash.ImageHash, hashes: list[str]) -> Optional[int]:
        best: Optional[int] = None
        for raw in hashes:
            try:
                candidate = imagehash.hex_to_hash(raw)
            except Exception:
                continue
            dist = ph - candidate
            if best is None or dist < best:
                best = dist
        return best

    def _match_by_keywords(self, text: str) -> Optional[str]:
        t = (text or "").lower()
        for kw in self.rules.keywords:
            if kw and kw in t:
                return kw
        return None

    def _download_hash(self, url: str) -> Optional[imagehash.ImageHash]:
        if not url:
            return None
        try:
            resp = requests.get(url, timeout=self.timeout_sec)
            resp.raise_for_status()
            image = Image.open(io.BytesIO(resp.content)).convert("RGB")
            return imagehash.phash(image)
        except Exception:
            return None

    def classify(self, entry: SocialEntry) -> MatchResult:
        keyword = self._match_by_keywords(entry.text)
        if keyword:
            return MatchResult(
                is_violation=True,
                reason=f"ключевое слово: {keyword}",
                post_url=entry.post_url,
            )

        ph = self._download_hash(entry.thumbnail_url)
        if ph is None:
            return MatchResult(is_violation=False, reason="", post_url=entry.post_url)

        allow_dist = self._distance_to_set(ph, self.rules.allowed_hashes)
        if allow_dist is not None and allow_dist <= self.allow_hash_distance:
            return MatchResult(is_violation=False, reason="", post_url=entry.post_url)

        block_dist = self._distance_to_set(ph, self.rules.blocked_hashes)
        if block_dist is not None and block_dist <= self.block_hash_distance:
            return MatchResult(
                is_violation=True,
                reason=f"похожее запрещенное изображение (dist={block_dist})",
                post_url=entry.post_url,
            )
        return MatchResult(is_violation=False, reason="", post_url=entry.post_url)

