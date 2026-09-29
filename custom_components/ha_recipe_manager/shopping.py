"""Shopping-list integration helpers."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DATA_STORE, DOMAIN
from .models import ingredient_to_shopping_item, missing_ingredients
from .store import RecipeStore


def get_store(hass: HomeAssistant) -> RecipeStore:
    """Return the loaded recipe store."""
    store = hass.data.get(DOMAIN, {}).get(DATA_STORE)
    if store is None:
        raise HomeAssistantError("HA Recipe Manager is not loaded yet.")
    return store


async def async_add_missing_to_shopping_list(
    hass: HomeAssistant, recipe_id: str, checked_ingredient_ids: list[str] | None = None
) -> list[str]:
    """Add unchecked ingredients for one recipe to the Home Assistant shopping list."""
    if not hass.services.has_service("shopping_list", "add_item"):
        raise HomeAssistantError(
            "The Home Assistant Shopping list integration is not available."
        )

    store = get_store(hass)
    recipe = store.get_recipe(recipe_id)
    if recipe is None:
        raise HomeAssistantError("Recipe was not found.")

    labels = [
        ingredient_to_shopping_item(ingredient)
        for ingredient in missing_ingredients(recipe, checked_ingredient_ids or [])
    ]

    for label in labels:
        await hass.services.async_call(
            "shopping_list",
            "add_item",
            {"name": label},
            blocking=True,
        )

    return labels
