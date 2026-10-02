"""Config flow for HA Recipe Manager."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import CONF_CALORIE_AGENT, DEFAULT_CALORIE_AGENT, DOMAIN, NAME


class RecipeManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Recipe Manager."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Allow the existing conversation agent to be changed."""
        return RecipeManagerOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle setup from the UI."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title=NAME, data={})

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))


class RecipeManagerOptionsFlow(config_entries.OptionsFlow):
    """Choose the calorie estimation agent without adding another API key."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_CALORIE_AGENT, default=self.config_entry.options.get(
                    CONF_CALORIE_AGENT, DEFAULT_CALORIE_AGENT
                )): selector.EntitySelector(selector.EntitySelectorConfig(domain="conversation")),
            }),
        )
