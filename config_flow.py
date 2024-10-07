"""Config flow for Grouped Thermostat integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Grouped Thermostat."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("name"): str,
                        vol.Required("thermostats"): selector.EntitySelector(
                            selector.EntitySelectorConfig(
                                domain="climate", multiple=True
                            )
                        ),
                    }
                ),
            )

        return self.async_create_entry(title=user_input["name"], data=user_input)
