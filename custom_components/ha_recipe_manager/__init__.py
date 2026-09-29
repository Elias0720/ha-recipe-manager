"""The HA Recipe Manager integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType

from .const import (
    DATA_FRONTEND_REGISTERED,
    DATA_STORE,
    DOMAIN,
    EVENT_SHOPPING_LIST_FILLED,
    FRONTEND_BASE,
    PANEL_ICON,
    PANEL_MODULE_URL,
    PANEL_NAME,
    PANEL_TITLE,
    PANEL_URL_PATH,
    SERVICE_ADD_MISSING,
)
from .shopping import async_add_missing_to_shopping_list
from .store import RecipeStore
from .websocket import async_register_websocket_commands


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up HA Recipe Manager."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    async_register_websocket_commands(hass)

    if not domain_data.get(DATA_FRONTEND_REGISTERED):
        frontend_path = Path(__file__).parent / "frontend"
        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_BASE, str(frontend_path), True)]
        )
        domain_data[DATA_FRONTEND_REGISTERED] = True

    async def handle_add_missing(call: ServiceCall) -> None:
        labels = await async_add_missing_to_shopping_list(
            hass,
            call.data["recipe_id"],
            call.data.get("checked_ingredient_ids", []),
        )
        hass.bus.async_fire(
            EVENT_SHOPPING_LIST_FILLED,
            {
                "recipe_id": call.data["recipe_id"],
                "items": labels,
                "count": len(labels),
            },
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_MISSING,
        handle_add_missing,
        schema=vol.Schema(
            {
                vol.Required("recipe_id"): str,
                vol.Optional("checked_ingredient_ids", default=[]): [str],
            }
        ),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA Recipe Manager from a config entry."""
    store = RecipeStore(hass)
    await store.async_load()
    hass.data.setdefault(DOMAIN, {})[DATA_STORE] = store

    await _async_register_panel(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload HA Recipe Manager."""
    hass.data.get(DOMAIN, {}).pop(DATA_STORE, None)
    frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
    return True


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Register the sidebar panel."""
    if frontend.async_panel_exists(hass, PANEL_URL_PATH):
        frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)

    await panel_custom.async_register_panel(
        hass=hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_NAME,
        module_url=PANEL_MODULE_URL,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=False,
        embed_iframe=False,
        config={"domain": DOMAIN},
    )
