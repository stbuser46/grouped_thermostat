"""Platform for climate integration."""

import logging
from typing import Any, Dict, List, Optional
from datetime import timedelta

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_HVAC_ACTION,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback, State
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SUPPORT_FLAGS, HVAC_MODES, PRESET_MODES
from .utils import (
    calculate_average_temperature,
    get_max_temperature,
    get_most_common_value,
)

_LOGGER = logging.getLogger(__name__)

TEMPERATURE_HYSTERESIS = 0.1
UPDATE_INTERVAL = timedelta(seconds=30)


class GroupedThermostat(ClimateEntity):
    """Representation of a Grouped Thermostat."""

    def __init__(self, hass: HomeAssistant, name: str, thermostats: List[str]):
        """Initialize the Grouped Thermostat."""
        self._hass = hass
        self._name = name
        self._thermostats = thermostats
        self._hvac_mode = HVACMode.HEAT
        self._hvac_action = None
        self._target_temperature = None
        self._attr_preset_mode = PRESET_MODES[1]  # PRESET_NONE
        self._current_temperature = None
        self._available = True
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_min_temp = 7
        self._attr_max_temp = 35
        self._attr_hvac_modes = HVAC_MODES
        self._attr_preset_modes = PRESET_MODES
        self._attr_supported_features = SUPPORT_FLAGS
        self._sub_values: Dict[str, Dict[str, Any]] = {t: {} for t in thermostats}

        self.coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="grouped_thermostat",
            update_method=self._async_update_data,
            update_interval=UPDATE_INTERVAL,
        )

    @property
    def thermostats(self) -> List[str]:
        """Return the list of child thermostats."""
        return self._thermostats.copy()

    async def async_added_to_hass(self):
        """Set up a listener for state changes in child thermostats."""
        await super().async_added_to_hass()

        @callback
        def async_state_changed_listener(event):
            """Handle child updates."""
            self._update_sub_value(
                event.data["entity_id"], self.hass.states.get(event.data["entity_id"])
            )
            self._update_aggregate_state()
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._thermostats, async_state_changed_listener
            )
        )

        # Initial data update
        await self.coordinator.async_config_entry_first_refresh()

    async def _async_update_data(self):
        """Update data via library."""
        try:
            for entity_id in self._thermostats:
                state = self.hass.states.get(entity_id)
                if state:
                    self._update_sub_value(entity_id, state)
            self._update_aggregate_state()
            return self._sub_values
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    def _update_sub_value(self, entity_id: str, state: State):
        """Update the stored state for a single child thermostat."""
        if not state:
            _LOGGER.warning(f"No state available for {entity_id}")
            return

        try:
            new_sub_value = {
                "state": state.state,
                "current_temperature": state.attributes.get("current_temperature"),
                "temperature": state.attributes.get("temperature"),
                "preset_mode": state.attributes.get("preset_mode"),
                "hvac_action": state.attributes.get("hvac_action"),
            }
            self._sub_values[entity_id] = new_sub_value
            _LOGGER.debug(f"Updated sub_value for {entity_id}: {new_sub_value}")
        except AttributeError as e:
            _LOGGER.error(f"Error updating sub_value for {entity_id}: {e}")

    def _update_aggregate_state(self):
        """Recalculate the aggregate state based on all child thermostat states."""
        should_update = False

        current_temps = [
            v.get("current_temperature")
            for v in self._sub_values.values()
            if v.get("current_temperature") is not None
        ]
        new_current_temp = calculate_average_temperature(current_temps)
        if new_current_temp is not None and (
            self._current_temperature is None
            or abs(new_current_temp - self._current_temperature)
            >= TEMPERATURE_HYSTERESIS
        ):
            self._current_temperature = new_current_temp
            should_update = True

        target_temps = [
            v.get("temperature")
            for v in self._sub_values.values()
            if v.get("temperature") is not None
        ]
        new_target_temp = get_max_temperature(target_temps)
        if new_target_temp != self._target_temperature:
            self._target_temperature = new_target_temp
            should_update = True

        hvac_modes = [
            v.get("state")
            for v in self._sub_values.values()
            if v.get("state") in HVAC_MODES
        ]
        new_hvac_mode = get_most_common_value(hvac_modes)
        if new_hvac_mode != self._hvac_mode:
            self._hvac_mode = new_hvac_mode
            should_update = True

        preset_modes = [
            v.get("preset_mode")
            for v in self._sub_values.values()
            if v.get("preset_mode") in PRESET_MODES
        ]
        new_preset_mode = get_most_common_value(preset_modes)
        if new_preset_mode != self._attr_preset_mode:
            self._attr_preset_mode = new_preset_mode
            should_update = True

        hvac_actions = [
            v.get("hvac_action")
            for v in self._sub_values.values()
            if v.get("hvac_action") is not None
        ]
        new_hvac_action = get_most_common_value(hvac_actions)
        if new_hvac_action != self._hvac_action:
            self._hvac_action = new_hvac_action
            should_update = True

        self._available = any(
            v.get("state") != "unavailable" for v in self._sub_values.values()
        )

        if should_update:
            _LOGGER.info(
                f"Updated aggregate state for {self._name}: "
                f"current_temp={self._current_temperature}, "
                f"target_temp={self._target_temperature}, "
                f"hvac_mode={self._hvac_mode}, "
                f"hvac_action={self._hvac_action}, "
                f"preset_mode={self._attr_preset_mode}, "
                f"available={self._available}"
            )

    async def async_update(self):
        """Update the entity."""
        await self.coordinator.async_request_refresh()

    @property
    def name(self):
        """Return the name of the grouped thermostat."""
        return self._name

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
    def hvac_action(self) -> Optional[str]:
        """Return the current running hvac operation if supported."""
        return self._hvac_action

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

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
            "grouped_thermostats": self.thermostats,
            "sub_values": self._sub_values,
        }
