"""Constants for the Grouped Thermostat integration."""

from homeassistant.components.climate.const import (
    HVACMode,
    PRESET_BOOST,
    PRESET_NONE,
    ClimateEntityFeature,
)

DOMAIN = "grouped_thermostat"

SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
)

HVAC_MODES = [HVACMode.OFF, HVACMode.HEAT]
PRESET_MODES = [PRESET_BOOST, PRESET_NONE]
