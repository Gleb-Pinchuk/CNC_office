from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CategoryRule:
    category: str
    remark: str
    keywords: list[str]


@dataclass
class ModerationRules:
    category_rules: list[CategoryRule]
    keywords: list[str]
    blocked_hashes: list[str]
    blocked_hashes_by_category: dict[str, list[str]]
    allowed_hashes: list[str]


def _normalize_keywords(items) -> list[str]:
    return [str(x).strip().lower() for x in items or [] if str(x).strip()]


def _default_category_rules() -> list[CategoryRule]:
    return [
        CategoryRule(
            category="cigarettes",
            remark="курит сигареты",
            keywords=["сигарет", "курит", "курение", "вейп", "vape", "smoking", "cigarette"],
        ),
        CategoryRule(
            category="alcohol",
            remark="употребляет алкоголь",
            keywords=["алкогол", "пьет", "пиво", "вино", "водка", "drunk", "alcohol", "beer"],
        ),
        CategoryRule(
            category="car_driving",
            remark="вождение автомобиля без прав",
            keywords=["за рулем", "машин", "автомобил", "car", "driving car", "drive car"],
        ),
        CategoryRule(
            category="motorcycle_driving",
            remark="вождение мотоцикла без прав",
            keywords=["мотоцикл", "мото", "байк", "motorcycle", "bike", "riding moto"],
        ),
    ]


def load_rules(path: Path) -> ModerationRules:
    if not path.exists():
        defaults = _default_category_rules()
        return ModerationRules(
            category_rules=defaults,
            keywords=[],
            blocked_hashes=[],
            blocked_hashes_by_category={rule.category: [] for rule in defaults},
            allowed_hashes=[],
        )
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    defaults_map = {rule.category: rule for rule in _default_category_rules()}
    category_rules: list[CategoryRule] = []
    for raw in payload.get("category_rules", []) or []:
        if not isinstance(raw, dict):
            continue
        category = str(raw.get("category") or "").strip().lower()
        remark = str(raw.get("remark") or "").strip().lower()
        keywords = _normalize_keywords(raw.get("keywords", []))
        if not category or not remark:
            continue
        category_rules.append(CategoryRule(category=category, remark=remark, keywords=keywords))
    if not category_rules:
        category_rules = _default_category_rules()
    else:
        for cat, rule in defaults_map.items():
            if not any(x.category == cat for x in category_rules):
                category_rules.append(rule)

    blocked_by_category_raw = payload.get("blocked_hashes_by_category", {}) or {}
    blocked_by_category: dict[str, list[str]] = {}
    if isinstance(blocked_by_category_raw, dict):
        for category, hashes in blocked_by_category_raw.items():
            c = str(category).strip().lower()
            if not c:
                continue
            blocked_by_category[c] = _normalize_keywords(hashes)
    for rule in category_rules:
        blocked_by_category.setdefault(rule.category, [])

    return ModerationRules(
        category_rules=category_rules,
        keywords=_normalize_keywords(payload.get("keywords", [])),
        blocked_hashes=_normalize_keywords(payload.get("blocked_hashes", [])),
        blocked_hashes_by_category=blocked_by_category,
        allowed_hashes=_normalize_keywords(payload.get("allowed_hashes", [])),
    )


def save_rules(path: Path, rules: ModerationRules) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    category_rules = []
    for rule in rules.category_rules:
        category_rules.append(
            {
                "category": rule.category,
                "remark": rule.remark,
                "keywords": sorted(set(_normalize_keywords(rule.keywords))),
            }
        )
    payload = {
        "category_rules": category_rules,
        "keywords": sorted(set(rules.keywords)),
        "blocked_hashes": sorted(set(rules.blocked_hashes)),
        "blocked_hashes_by_category": {
            key: sorted(set(_normalize_keywords(values)))
            for key, values in sorted((rules.blocked_hashes_by_category or {}).items())
        },
        "allowed_hashes": sorted(set(rules.allowed_hashes)),
    }
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

