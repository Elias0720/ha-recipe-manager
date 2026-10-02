"""Storage layer for HA Recipe Manager."""

from __future__ import annotations

from asyncio import Lock
from typing import Any
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION
from .calorie_values import calorie_basis
from .models import RANKING_KINDS, Recipe, normalize_rankings, normalize_recipe, sort_recipes, utc_timestamp


class RecipeStore:
    """Persist and retrieve recipes from Home Assistant storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the recipe store."""
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._recipes: dict[str, Recipe] = {}
        self._rankings: dict[str, list[str]] = {kind: [] for kind in RANKING_KINDS}
        self._write_lock = Lock()

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
        self._rankings = normalize_rankings((data or {}).get("rankings"), self.list_recipes())

    def get_rankings(self) -> dict[str, list[str]]:
        """Return independent copies of the two recipe orders."""
        return {kind: list(order) for kind, order in self._rankings.items()}

    def list_recipes(self) -> list[Recipe]:
        """Return all recipes."""
        return sort_recipes(list(self._recipes.values()))

    def get_recipe(self, recipe_id: str) -> Recipe | None:
        """Return one recipe by id."""
        return self._recipes.get(recipe_id)

    async def async_save_recipe(self, raw_recipe: dict[str, Any]) -> Recipe:
        """Create or update a recipe."""
        async with self._write_lock:
            existing = self._recipes.get(str(raw_recipe.get("id", "")))
            recipe = normalize_recipe(raw_recipe, existing=existing)
            recipes = {**self._recipes, recipe["id"]: recipe}
            await self._async_save(recipes, self._rankings)
            return recipe

    async def async_delete_recipe(self, recipe_id: str) -> bool:
        """Delete a recipe by id."""
        async with self._write_lock:
            if recipe_id not in self._recipes:
                return False
            recipes = {key: recipe for key, recipe in self._recipes.items() if key != recipe_id}
            await self._async_save(recipes, self._rankings)
            return True

    async def async_save_calorie_estimate(self, snapshot: Recipe, estimate: dict[str, Any]) -> Recipe:
        """Apply an estimate atomically without overwriting newer edits."""
        async with self._write_lock:
            current = self._recipes.get(snapshot["id"])
            if current is None:
                raise ValueError("Das Rezept wurde während der Schätzung gelöscht.")
            if calorie_basis(current) != calorie_basis(snapshot) or any(
                current.get(key) != snapshot.get(key)
                for key in ("total_kcal", "calories_source", "calories_basis", "calories_revision")
            ):
                raise ValueError("Das Rezept wurde während der Schätzung geändert. Bitte erneut schätzen.")
            timestamp = utc_timestamp()
            recipe = {**current, **estimate, "calories_source": "ai",
                      "calories_basis": calorie_basis(current), "calories_stale": False,
                      "calories_revision": uuid4().hex,
                      "calories_updated_at": timestamp, "updated_at": timestamp}
            await self._async_save({**self._recipes, recipe["id"]: recipe}, self._rankings)
            return recipe

    async def async_save_ranking(self, kind: str, recipe_ids: list[str]) -> dict[str, list[str]]:
        """Save one complete order without replacing the other ranking."""
        async with self._write_lock:
            if kind not in RANKING_KINDS:
                raise ValueError("Unknown ranking kind.")
            if len(recipe_ids) != len(self._recipes) or set(recipe_ids) != set(self._recipes):
                raise ValueError("The recipe list has changed. Reload the recipes and try again.")
            rankings = {**self._rankings, kind: list(recipe_ids)}
            await self._async_save(self._recipes, rankings)
            return self.get_rankings()

    async def _async_save(self, recipes: dict[str, Recipe], rankings: dict[str, list[str]]) -> None:
        """Persist all recipes."""
        normalized_rankings = normalize_rankings(rankings, list(recipes.values()))
        await self._store.async_save({
            "recipes": sort_recipes(list(recipes.values())), "rankings": normalized_rankings,
        })
        self._recipes = recipes
        self._rankings = normalized_rankings
