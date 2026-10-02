"""Pure recipe model helpers."""

from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from .calorie_values import calorie_basis, calorie_sources, total_calories

Recipe = dict[str, Any]
Ingredient = dict[str, str]
RANKING_KINDS = ("taste", "effort")


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

    duration = clean_text(raw.get("duration_minutes", (existing or {}).get("duration_minutes")))
    if duration and (not re.fullmatch(r"\d+", duration) or int(duration) < 1):
        raise ValueError("Time required must be a positive whole number of minutes.")

    recipe = {
        "id": recipe_id,
        "name": name,
        "servings": clean_text(raw.get("servings")),
        "duration_minutes": int(duration) if duration else None,
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
    previous = existing or {}
    calories = total_calories(raw.get("total_kcal", previous.get("total_kcal")))
    recipe["total_kcal"] = calories
    if calories is None:
        recipe.update(calories_source=None, calories_basis="", calories_notes="",
                      calories_sources=[], calories_updated_at="", calories_revision="", calories_stale=False)
    elif calories != previous.get("total_kcal") or raw.get("calories_manual") is True:
        recipe.update(calories_source="manual", calories_basis=calorie_basis(recipe),
                      calories_notes="", calories_sources=[], calories_updated_at=timestamp,
                      calories_revision=uuid4().hex, calories_stale=False)
    else:
        basis = clean_text(previous.get("calories_basis"))
        recipe.update(
            calories_source="ai" if previous.get("calories_source") == "ai" else "manual",
            calories_basis=basis,
            calories_notes=clean_text(previous.get("calories_notes"))[:4000],
            calories_sources=calorie_sources(previous.get("calories_sources")),
            calories_updated_at=clean_text(previous.get("calories_updated_at")),
            calories_revision=clean_text(previous.get("calories_revision")),
            calories_stale=basis != calorie_basis(recipe),
        )
    return recipe


def sort_recipes(recipes: list[Recipe]) -> list[Recipe]:
    """Sort recipes by their display name."""
    return sorted(recipes, key=lambda recipe: recipe.get("name", "").casefold())


def normalize_rankings(raw: Any, recipes: list[Recipe]) -> dict[str, list[str]]:
    """Keep existing ranks, remove stale IDs and append newly created recipes."""
    recipe_ids = [recipe["id"] for recipe in sort_recipes(recipes)]
    valid_ids = set(recipe_ids)
    rankings = {}
    for kind in RANKING_KINDS:
        order = raw.get(kind, []) if isinstance(raw, dict) else []
        if not isinstance(order, list):
            order = []
        seen = set()
        rankings[kind] = []
        for recipe_id in [*order, *recipe_ids]:
            if isinstance(recipe_id, str) and recipe_id in valid_ids and recipe_id not in seen:
                rankings[kind].append(recipe_id)
                seen.add(recipe_id)
    return rankings


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

    for ingredient in recipe.get("ingredients", []):
        if not isinstance(ingredient, dict):
            continue
        ingredient_id = clean_text(ingredient.get("id"))
        if ingredient_id in checked:
            continue

        normalized = normalize_ingredient(ingredient)
        if normalized is None:
            continue

        missing.append(normalized)

    return missing
