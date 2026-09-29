"""Pure recipe model helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

Recipe = dict[str, Any]
Ingredient = dict[str, str]


def utc_timestamp() -> str:
    """Return a compact UTC timestamp for persisted recipes."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def clean_text(value: Any) -> str:
    """Normalize arbitrary user input to a trimmed string."""
    if value is None:
        return ""
    return str(value).strip()


def normalize_tags(value: Any) -> list[str]:
    """Normalize tags from a list or comma-separated string."""
    if isinstance(value, list):
        raw_tags = value
    else:
        raw_tags = clean_text(value).split(",")

    tags: list[str] = []
    seen: set[str] = set()
    for raw_tag in raw_tags:
        tag = clean_text(raw_tag)
        key = tag.casefold()
        if tag and key not in seen:
            tags.append(tag)
            seen.add(key)
    return tags


def normalize_ingredient(raw: Any) -> Ingredient | None:
    """Normalize one ingredient row and drop empty rows."""
    if not isinstance(raw, dict):
        return None

    name = clean_text(raw.get("name"))
    if not name:
        return None

    return {
        "id": clean_text(raw.get("id")) or uuid4().hex,
        "name": name,
        "quantity": clean_text(raw.get("quantity")),
        "unit": clean_text(raw.get("unit")),
        "note": clean_text(raw.get("note")),
    }


def normalize_recipe(
    raw: Any,
    existing: Recipe | None = None,
    now: str | None = None,
    *,
    preserve_updated_at: bool = False,
) -> Recipe:
    """Normalize a recipe payload for storage."""
    if not isinstance(raw, dict):
        raise ValueError("Recipe data must be an object.")

    timestamp = now or utc_timestamp()
    recipe_id = clean_text(raw.get("id")) or clean_text((existing or {}).get("id")) or uuid4().hex
    name = clean_text(raw.get("name"))
    if not name:
        raise ValueError("Recipe name is required.")

    source_url = clean_text(raw.get("source_url"))
    if source_url:
        parsed_source = urlparse(source_url)
        if parsed_source.scheme not in {"http", "https"} or not parsed_source.netloc:
            raise ValueError("Recipe source URL must be an HTTP or HTTPS address.")

    ingredients = [
        ingredient
        for ingredient in (normalize_ingredient(item) for item in raw.get("ingredients", []))
        if ingredient is not None
    ]

    return {
        "id": recipe_id,
        "name": name,
        "servings": clean_text(raw.get("servings")),
        "source_url": source_url,
        "tags": normalize_tags(raw.get("tags", [])),
        "ingredients": ingredients,
        "instructions": clean_text(raw.get("instructions")),
        "created_at": clean_text(raw.get("created_at"))
        or clean_text((existing or {}).get("created_at"))
        or timestamp,
        "updated_at": (
            clean_text(raw.get("updated_at")) or timestamp
            if preserve_updated_at
            else timestamp
        ),
    }


def sort_recipes(recipes: list[Recipe]) -> list[Recipe]:
    """Sort recipes by their display name."""
    return sorted(recipes, key=lambda recipe: recipe.get("name", "").casefold())


def ingredient_to_shopping_item(ingredient: Ingredient) -> str:
    """Render one ingredient as a Home Assistant shopping-list item."""
    quantity = clean_text(ingredient.get("quantity"))
    unit = clean_text(ingredient.get("unit"))
    name = clean_text(ingredient.get("name"))
    note = clean_text(ingredient.get("note"))

    prefix = " ".join(part for part in (quantity, unit) if part)
    label = f"{prefix} {name}".strip()
    if note:
        label = f"{label} ({note})"
    return label


def missing_ingredients(recipe: Recipe, checked_ingredient_ids: list[str] | set[str]) -> list[Ingredient]:
    """Return ingredients that were not checked as already available."""
    checked = {clean_text(item) for item in checked_ingredient_ids if clean_text(item)}
    missing: list[Ingredient] = []
    seen_labels: set[str] = set()

    for ingredient in recipe.get("ingredients", []):
        if not isinstance(ingredient, dict):
            continue
        ingredient_id = clean_text(ingredient.get("id"))
        if ingredient_id in checked:
            continue

        normalized = normalize_ingredient(ingredient)
        if normalized is None:
            continue

        label_key = ingredient_to_shopping_item(normalized).casefold()
        if label_key in seen_labels:
            continue

        missing.append(normalized)
        seen_labels.add(label_key)

    return missing
