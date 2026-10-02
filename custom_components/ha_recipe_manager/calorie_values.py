"""Validation and recipe fingerprints for whole-recipe nutrition totals."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
import re
from typing import Any
from urllib.parse import urlparse

GRAM_FIELDS = {
    "total_protein_g": "Protein",
    "total_fat_g": "Fett",
    "total_sugar_g": "Zucker",
}
NUTRIENT_FIELDS = ("total_kcal", *GRAM_FIELDS)


def total_calories(value: Any) -> int | None:
    """Accept an optional whole, non-negative kcal total."""
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not re.fullmatch(r"\d{1,8}", str(value).strip()):
        raise ValueError("Gesamtkalorien müssen eine ganze Zahl ab 0 sein.")
    return int(str(value).strip())


def total_grams(value: Any, label: str) -> float | None:
    """Accept finite non-negative grams and round estimates to one decimal."""
    if value is None or value == "":
        return None
    text = str(value).strip().replace(",", ".")
    if isinstance(value, bool) or not re.fullmatch(r"\d{1,7}(?:\.\d{1,10})?", text):
        raise ValueError(f"{label} muss eine Zahl ab 0 in Gramm sein.")
    amount = Decimal(text)
    if amount > Decimal("9999999.9"):
        raise ValueError(f"{label} muss kleiner als 10 Millionen Gramm sein.")
    return float(amount.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def nutrition_totals(raw: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    """Preserve omitted fields; keep unknown values distinct from zero."""
    previous = existing or {}
    return {
        "total_kcal": total_calories(raw.get("total_kcal", previous.get("total_kcal"))),
        **{key: total_grams(raw.get(key, previous.get(key)), label) for key, label in GRAM_FIELDS.items()},
    }


def calorie_basis(recipe: dict[str, Any]) -> str:
    """Ignore IDs, row order, servings and other non-caloric metadata."""
    rows = sorted(
        tuple(str(row.get(key) or "").strip() for key in ("name", "quantity", "unit", "note"))
        for row in recipe.get("ingredients", [])
        if isinstance(row, dict) and str(row.get("name") or "").strip()
    )
    content = json.dumps(
        [rows, str(recipe.get("instructions") or "").strip()],
        ensure_ascii=False, separators=(",", ":"),
    )
    return sha256(content.encode("utf-8")).hexdigest()


def calorie_sources(value: Any) -> list[dict[str, str]]:
    """Keep a small set of safe source links supplied with the estimate."""
    sources = []
    seen = set()
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        try:
            parsed = urlparse(url)
        except ValueError:
            continue
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or url in seen):
            continue
        seen.add(url)
        sources.append({"url": url, "title": str(item.get("title") or parsed.hostname).strip()[:200]})
        if len(sources) == 8:
            break
    return sources
