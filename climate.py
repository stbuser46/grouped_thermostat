"""Platform for climate integration."""

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .grouped_thermostat import GroupedThermostat


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the GroupedThermostat platform."""
    name = entry.data.get("name")
    thermostats = entry.data.get("thermostats")
    async_add_entities([GroupedThermostat(hass, name, thermostats)])
