from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ModerationRules:
    keywords: list[str]
    blocked_hashes: list[str]
    allowed_hashes: list[str]


def load_rules(path: Path) -> ModerationRules:
    if not path.exists():
        return ModerationRules(keywords=[], blocked_hashes=[], allowed_hashes=[])
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return ModerationRules(
        keywords=[str(x).strip().lower() for x in payload.get("keywords", []) if str(x).strip()],
        blocked_hashes=[
            str(x).strip().lower() for x in payload.get("blocked_hashes", []) if str(x).strip()
        ],
        allowed_hashes=[
            str(x).strip().lower() for x in payload.get("allowed_hashes", []) if str(x).strip()
        ],
    )


def save_rules(path: Path, rules: ModerationRules) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "keywords": sorted(set(rules.keywords)),
        "blocked_hashes": sorted(set(rules.blocked_hashes)),
        "allowed_hashes": sorted(set(rules.allowed_hashes)),
    }
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

