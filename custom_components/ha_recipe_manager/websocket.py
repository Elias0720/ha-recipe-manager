"""WebSocket API for HA Recipe Manager."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DATA_WEBSOCKET_REGISTERED,
    DOMAIN,
    EVENT_RECIPES_UPDATED,
    EVENT_SHOPPING_LIST_FILLED,
)
from .shopping import async_add_missing_to_shopping_list, get_store
from .calories import async_estimate_calories


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/list"})
@websocket_api.async_response
async def ws_list_recipes(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """List all recipes."""
    store = get_store(hass)
    connection.send_result(msg["id"], {"recipes": store.list_recipes(), "rankings": store.get_rankings()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/save_ranking",
        vol.Required("kind"): vol.In(("taste", "effort")),
        vol.Required("recipe_ids"): [str],
    }
)
@websocket_api.async_response
async def ws_save_ranking(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Persist one ranking and notify all open panels."""
    try:
        rankings = await get_store(hass).async_save_ranking(msg["kind"], msg["recipe_ids"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_ranking", str(err))
        return
    hass.bus.async_fire(EVENT_RECIPES_UPDATED, {"action": "ranking", "kind": msg["kind"]})
    connection.send_result(msg["id"], {"rankings": rankings})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/get",
        vol.Required("recipe_id"): str,
    }
)
@callback
def ws_get_recipe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return one recipe."""
    store = get_store(hass)
    recipe = store.get_recipe(msg["recipe_id"])
    if recipe is None:
        connection.send_error(msg["id"], "not_found", "Recipe was not found.")
        return
    connection.send_result(msg["id"], {"recipe": recipe})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/save",
        vol.Required("recipe"): dict,
    }
)
@websocket_api.async_response
async def ws_save_recipe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Create or update a recipe."""
    store = get_store(hass)
    try:
        recipe = await store.async_save_recipe(msg["recipe"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_recipe", str(err))
        return

    hass.bus.async_fire(EVENT_RECIPES_UPDATED, {"action": "save", "recipe_id": recipe["id"]})
    connection.send_result(msg["id"], {"recipe": recipe})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/delete",
        vol.Required("recipe_id"): str,
    }
)
@websocket_api.async_response
async def ws_delete_recipe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete a recipe."""
    store = get_store(hass)
    deleted = await store.async_delete_recipe(msg["recipe_id"])
    if not deleted:
        connection.send_error(msg["id"], "not_found", "Recipe was not found.")
        return

    hass.bus.async_fire(EVENT_RECIPES_UPDATED, {"action": "delete", "recipe_id": msg["recipe_id"]})
    connection.send_result(msg["id"], {"deleted": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/add_to_shopping_list",
        vol.Required("recipe_id"): str,
        vol.Optional("checked_ingredient_ids", default=[]): [str],
    }
)
@websocket_api.async_response
async def ws_add_to_shopping_list(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Add missing recipe ingredients to the Home Assistant shopping list."""
    try:
        labels = await async_add_missing_to_shopping_list(
            hass, msg["recipe_id"], msg["checked_ingredient_ids"]
        )
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "shopping_list_failed", str(err))
        return

    hass.bus.async_fire(
        EVENT_SHOPPING_LIST_FILLED,
        {"recipe_id": msg["recipe_id"], "items": labels, "count": len(labels)},
    )
    connection.send_result(msg["id"], {"items": labels, "count": len(labels)})


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register WebSocket commands once."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(DATA_WEBSOCKET_REGISTERED):
        return

    websocket_api.async_register_command(hass, ws_list_recipes)
    websocket_api.async_register_command(hass, ws_save_ranking)
    websocket_api.async_register_command(hass, ws_get_recipe)
    websocket_api.async_register_command(hass, ws_save_recipe)
    websocket_api.async_register_command(hass, ws_delete_recipe)
    websocket_api.async_register_command(hass, ws_add_to_shopping_list)
    websocket_api.async_register_command(hass, ws_estimate_calories)
    domain_data[DATA_WEBSOCKET_REGISTERED] = True


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/estimate_calories", vol.Required("recipe_id"): str}
)
@websocket_api.async_response
async def ws_estimate_calories(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Estimate and save whole-recipe nutrients, then notify every open view."""
    try:
        recipe = await async_estimate_calories(hass, msg["recipe_id"], connection.context(msg))
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "calories_failed", str(err))
        return
    hass.bus.async_fire(EVENT_RECIPES_UPDATED, {"action": "calories", "recipe_id": recipe["id"]})
    connection.send_result(msg["id"], {"recipe": recipe})
