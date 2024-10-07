import logging
from typing import Any, Dict, List

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import SUPPORT_FLAGS, HVAC_MODES, PRESET_MODES
from .utils import (
    calculate_average_temperature,
    get_max_temperature,
    get_most_common_value,
)

_LOGGER = logging.getLogger(__name__)


class GroupedThermostat(ClimateEntity):
    """Representation of a Grouped Thermostat."""

    def __init__(self, hass: HomeAssistant, name: str, thermostats: List[str]):
        """Initialize the Grouped Thermostat."""
        self._hass = hass
        self._name = name
        self._thermostats = thermostats
        self._hvac_mode = HVACMode.HEAT
        self._target_temperature = None
        self._attr_preset_mode = PRESET_MODES[1]  # PRESET_NONE
        self._current_temperature = None
        self._available = True
        self._unit_of_measurement = UnitOfTemperature.CELSIUS
        self._sub_values: Dict[str, Dict[str, Any]] = {t: {} for t in thermostats}

    async def async_added_to_hass(self):
        """Set up a listener for state changes in child thermostats."""
        await super().async_added_to_hass()

        @callback
        def async_state_changed_listener(event):
            """Handle child updates."""
            self.async_schedule_update_ha_state(True)

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._thermostats, async_state_changed_listener
            )
        )

    async def async_update(self):
        """Fetch new state data for this entity."""
        for thermostat in self._thermostats:
            state = self.hass.states.get(thermostat)
            if state and state.state != "unavailable":
                self._update_sub_value(thermostat, state)
        self._update_aggregate_state()
        _LOGGER.info(f"Updated GroupedThermostat {self._name}: {self._sub_values}")

    def _update_sub_value(self, entity_id: str, state):
        """Update the stored state for a single child thermostat."""
        # Extract state values
        current_state = state.state
        current_temp = state.attributes.get("current_temperature")
        target_temp = state.attributes.get("temperature")
        preset_mode = state.attributes.get("preset_mode")
        hvac_action = state.attributes.get("hvac_action")

        # Log raw state data
        _LOGGER.debug(
            f"Raw state data for {entity_id}: "
            f"state={current_state}, "
            f"current_temp={current_temp}, "
            f"target_temp={target_temp}, "
            f"preset_mode={preset_mode}, "
            f"hvac_action={hvac_action}"
        )

        # Create new sub_value dictionary
        new_sub_value = {
            "state": current_state,
            "current_temperature": current_temp,
            "temperature": target_temp,
            "preset_mode": preset_mode,
            "hvac_action": hvac_action,
        }

        # Update the sub_values dictionary
        self._sub_values[entity_id] = new_sub_value

        # Log the updated sub_value
        _LOGGER.info(f"Child thermostat {entity_id} updated: {new_sub_value}")

        # Log the entire _sub_values dictionary for debugging
        _LOGGER.debug(f"Current _sub_values: {self._sub_values}")

    def _update_aggregate_state(self):
        """Recalculate the aggregate state based on all child thermostat states."""
        current_temps = [
            v.get("current_temperature")
            for v in self._sub_values.values()
            if v.get("current_temperature") is not None
        ]
        self._current_temperature = calculate_average_temperature(current_temps)

        target_temps = [
            v.get("temperature")
            for v in self._sub_values.values()
            if v.get("temperature") is not None
        ]
        self._target_temperature = get_max_temperature(target_temps)

        hvac_modes = [
            v.get("state")
            for v in self._sub_values.values()
            if v.get("state") is not None
        ]
        self._hvac_mode = get_most_common_value(hvac_modes)

        preset_modes = [
            v.get("preset_mode")
            for v in self._sub_values.values()
            if v.get("preset_mode") is not None
        ]
        self._attr_preset_mode = get_most_common_value(preset_modes)

        _LOGGER.info(
            f"Updated aggregate state: "
            f"current_temp={self._current_temperature}, "
            f"target_temp={self._target_temperature}, "
            f"hvac_mode={self._hvac_mode}, "
            f"preset_mode={self._attr_preset_mode}"
        )

    @property
    def name(self):
        """Return the name of the grouped thermostat."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Return current operation."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return HVAC_MODES

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        return self._attr_preset_mode

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return PRESET_MODES

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature for all child thermostats."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            for thermostat in self._thermostats:
                await self._hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {"entity_id": thermostat, "temperature": temperature},
                    blocking=True,
                )
            _LOGGER.info(
                f"Set temperature to {temperature} for all thermostats in {self._name}"
            )

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new HVAC mode for all child thermostats."""
        if hvac_mode in self.hvac_modes:
            for thermostat in self._thermostats:
                await self._hass.services.async_call(
                    "climate",
                    "set_hvac_mode",
                    {"entity_id": thermostat, "hvac_mode": hvac_mode},
                    blocking=True,
                )
            _LOGGER.info(
                f"Set HVAC mode to {hvac_mode} for all thermostats in {self._name}"
            )

    async def async_set_preset_mode(self, preset_mode):
        """Set new preset mode for all child thermostats."""
        if preset_mode in self.preset_modes:
            for thermostat in self._thermostats:
                await self._hass.services.async_call(
                    "climate",
                    "set_preset_mode",
                    {"entity_id": thermostat, "preset_mode": preset_mode},
                    blocking=True,
                )
            _LOGGER.info(
                f"Set preset mode to {preset_mode} for all thermostats in {self._name}"
            )

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        return {
            "grouped_thermostats": self._thermostats,
            "sub_values": self._sub_values,
        }
