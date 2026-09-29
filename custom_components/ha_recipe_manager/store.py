"""Storage layer for HA Recipe Manager."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION
from .models import Recipe, normalize_recipe, sort_recipes


class RecipeStore:
    """Persist and retrieve recipes from Home Assistant storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the recipe store."""
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._recipes: dict[str, Recipe] = {}

    async def async_load(self) -> None:
        """Load recipes from Home Assistant storage."""
        data = await self._store.async_load()
        self._recipes = {}

        for raw_recipe in (data or {}).get("recipes", []):
            try:
                recipe = normalize_recipe(
                    raw_recipe, existing=raw_recipe, preserve_updated_at=True
                )
            except ValueError:
                continue
            self._recipes[recipe["id"]] = recipe

    def list_recipes(self) -> list[Recipe]:
        """Return all recipes."""
        return sort_recipes(list(self._recipes.values()))

    def get_recipe(self, recipe_id: str) -> Recipe | None:
        """Return one recipe by id."""
        return self._recipes.get(recipe_id)

    async def async_save_recipe(self, raw_recipe: dict[str, Any]) -> Recipe:
        """Create or update a recipe."""
        existing = self._recipes.get(str(raw_recipe.get("id", "")))
        recipe = normalize_recipe(raw_recipe, existing=existing)
        self._recipes[recipe["id"]] = recipe
        await self._async_save()
        return recipe

    async def async_delete_recipe(self, recipe_id: str) -> bool:
        """Delete a recipe by id."""
        if recipe_id not in self._recipes:
            return False

        del self._recipes[recipe_id]
        await self._async_save()
        return True

    async def _async_save(self) -> None:
        """Persist all recipes."""
        await self._store.async_save({"recipes": self.list_recipes()})
