"""The F&F Fox devices integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from foxrestapiclient.devices.const import (
    DEVICE_MODEL_DIM1S2,
    DEVICE_MODEL_LED2S2,
    DEVICE_MODEL_R1S1,
    DEVICE_MODEL_R2S2,
    DEVICE_MODEL_RGBW,
    DEVICE_MODEL_STR1S2,
    DEVICE_PLATFORM,
    DEVICES,
    SUPPORTED_PLATFORM_COVER,
    SUPPORTED_PLATFORM_GATE,
    SUPPORTED_PLATFORM_LIGHT,
    SUPPORTED_PLATFORM_SENSOR,
    SUPPORTED_PLATFORM_SWITCH,
)
from foxrestapiclient.devices.fox_base_device import DeviceData
from foxrestapiclient.devices.fox_dim1s2_device import FoxDIM1S2Device
from foxrestapiclient.devices.fox_led2s2_device import FoxLED2S2Device
from foxrestapiclient.devices.fox_r1s1_device import FoxR1S1Device
from foxrestapiclient.devices.fox_r2s2_device import FoxR2S2Device
from foxrestapiclient.devices.fox_rgbw_device import FoxRGBWDevice
from foxrestapiclient.devices.fox_str1s2_device import FoxSTR1S2Device

from .const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)
_LOGGER.propagate = False
THROTTLE_TIME = timedelta(seconds=1)
# Supported platforms.
PLATFORMS = [Platform.COVER, Platform.LIGHT, Platform.SWITCH, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up F&F Fox devices from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    #Set update callback
    entry.async_on_unload(entry.add_update_listener(update_listener))
    fox_devices_coordinator = FoxDevicesCoordinator()
    hass.data[DOMAIN][entry.entry_id] = fox_devices_coordinator
    for device_config in entry.data["discovered_devices"]:
        fox_devices_coordinator.add_device_by_config(DeviceData(**device_config))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

async def update_listener(hass, entry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

class FoxDevicesCoordinator:
    """Fox devices coordinator."""

    def __init__(self) -> None:
        """Store devices as map agregated by platform."""
        self.__devices_map: dict[str, list] = {
            SUPPORTED_PLATFORM_COVER: [],
            SUPPORTED_PLATFORM_GATE: [],
            SUPPORTED_PLATFORM_LIGHT: [],
            SUPPORTED_PLATFORM_SENSOR: [],
            SUPPORTED_PLATFORM_SWITCH: [],
        }

    def add_device_by_config(self, device_data: DeviceData):
        """Add device to map with proper platform."""
        #Should skip config
        if device_data.skip is True:
            return
        try:
            if DEVICES[device_data.dev_type] == DEVICE_MODEL_LED2S2:
                self.__devices_map[DEVICE_PLATFORM[device_data.dev_type]].append(
                    FoxLED2S2Device(device_data)
                )
            elif DEVICES[device_data.dev_type] == DEVICE_MODEL_DIM1S2:
                self.__devices_map[DEVICE_PLATFORM[device_data.dev_type]].append(
                    FoxDIM1S2Device(device_data)
                )
            elif DEVICES[device_data.dev_type] == DEVICE_MODEL_RGBW:
                self.__devices_map[DEVICE_PLATFORM[device_data.dev_type]].append(
                    FoxRGBWDevice(device_data)
                )
            elif DEVICES[device_data.dev_type] == DEVICE_MODEL_R1S1:
                self.__devices_map[DEVICE_PLATFORM[device_data.dev_type]].append(
                    FoxR1S1Device(device_data)
                )
            elif DEVICES[device_data.dev_type] == DEVICE_MODEL_R2S2:
                self.__devices_map[DEVICE_PLATFORM[device_data.dev_type]].append(
                    FoxR2S2Device(device_data)
                )
            elif DEVICES[device_data.dev_type] == DEVICE_MODEL_STR1S2:
                self.__devices_map[DEVICE_PLATFORM[device_data.dev_type]].append(
                    FoxSTR1S2Device(device_data)
                )
        except KeyError:
            _LOGGER.error("Unsupported F&F Fox device type.")

    @Throttle(THROTTLE_TIME)
    async def async_fetch_light_devices(self):
        """Get light device list."""
        # First call update method for each device
        await asyncio.gather(
            *(
                light.async_fetch_device_available_data()
                for light in self.__devices_map[SUPPORTED_PLATFORM_LIGHT]
            )
        )

    @Throttle(THROTTLE_TIME)
    async def async_fetch_switch_devices(self):
        """Get all switch devices."""
        await asyncio.gather(
            *(
                switch.async_fetch_device_available_data()
                for switch in self.__devices_map[SUPPORTED_PLATFORM_SWITCH]
            )
        )

    @Throttle(THROTTLE_TIME)
    async def async_fetch_cover_devices(self):
        """Get all covers devices."""
        await asyncio.gather(
            *(
                cover.async_fetch_device_available_data()
                for cover in self.__devices_map[SUPPORTED_PLATFORM_COVER]
            )
        )

    def get_cover_devices(self):
        """Get cover devices."""
        return self.__devices_map[SUPPORTED_PLATFORM_COVER]

    def get_light_devices(self):
        """Get light devices."""
        return self.__devices_map[SUPPORTED_PLATFORM_LIGHT]

    def get_switch_devices(self):
        """Get switch devices."""
        return self.__devices_map[SUPPORTED_PLATFORM_SWITCH]

    def get_sensor_devices(self):
        """Get sensor devices."""
        sensors = []
        for switch in self.__devices_map[SUPPORTED_PLATFORM_SWITCH]:
            if isinstance(switch, FoxR1S1Device):
                sensors.append(switch)
        return sensors
