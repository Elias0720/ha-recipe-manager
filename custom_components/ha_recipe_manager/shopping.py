"""Shopping-list integration helpers."""

from __future__ import annotations

from asyncio import Lock
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DATA_SHOPPING_LOCK, DATA_STORE, DOMAIN
from .models import ingredient_to_shopping_item, missing_ingredients
from .shopping_items import parse_shopping_label, shopping_ingredient
from .store import RecipeStore


def get_store(hass: HomeAssistant) -> RecipeStore:
    """Return the loaded recipe store."""
    store = hass.data.get(DOMAIN, {}).get(DATA_STORE)
    if store is None:
        raise HomeAssistantError("HA Recipe Manager is not loaded yet.")
    return store


def _shopping_data(hass: HomeAssistant) -> Any:
    """Find the HA shopping data in both legacy and config-entry based versions."""
    data = hass.data.get("shopping_list")
    if hasattr(data, "items") and hasattr(data, "async_update"):
        return data
    for entry in hass.config_entries.async_entries("shopping_list"):
        data = getattr(entry, "runtime_data", None)
        if hasattr(data, "items") and hasattr(data, "async_update"):
            return data
    raise HomeAssistantError("The Home Assistant Shopping list is not loaded yet.")


async def async_add_missing_to_shopping_list(
    hass: HomeAssistant, recipe_id: str, checked_ingredient_ids: list[str] | None = None
) -> list[str]:
    """Add unchecked ingredients and combine compatible open shopping-list items."""
    if not hass.services.has_service("shopping_list", "add_item"):
        raise HomeAssistantError(
            "The Home Assistant Shopping list integration is not available."
        )

    store = get_store(hass)
    recipe = store.get_recipe(recipe_id)
    if recipe is None:
        raise HomeAssistantError("Recipe was not found.")

    ingredients = missing_ingredients(recipe, checked_ingredient_ids or [])
    if not ingredients:
        return []
    lock = hass.data[DOMAIN].setdefault(DATA_SHOPPING_LOCK, Lock())
    async with lock:
        data = _shopping_data(hass)
        labels: dict[str, str] = {}
        for ingredient in ingredients:
            incoming = shopping_ingredient(ingredient)
            matches = []
            total = None
            if incoming is not None:
                for item in list(data.items):
                    if item.get("complete"):
                        continue
                    existing = parse_shopping_label(item.get("name", ""), ingredient.get("unit", ""))
                    if existing is not None and existing.key == incoming.key:
                        matches.append(item)
                        total = existing if total is None else total.add(existing)
            if matches:
                label = total.add(incoming).label()
                item_id = matches[0]["id"]
                # Update through HA so storage, todo entities and list events stay in sync.
                await data.async_update(item_id, {"name": label})
                for duplicate in matches[1:]:
                    await data.async_remove(duplicate["id"])
                    labels.pop(duplicate["id"], None)
            else:
                label = ingredient_to_shopping_item(ingredient)
                previous_ids = {item["id"] for item in data.items}
                await hass.services.async_call(
                    "shopping_list", "add_item", {"name": label}, blocking=True,
                )
                item_id = next((item["id"] for item in data.items if item["id"] not in previous_ids), label)
            labels[item_id] = label
        return list(labels.values())
