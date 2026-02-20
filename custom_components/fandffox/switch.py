"""Platform for switch integration."""
from datetime import timedelta
import logging

from foxrestapiclient.devices.fox_r1s1_device import FoxR1S1Device
from foxrestapiclient.devices.fox_r2s2_device import FoxR2S2Device

from . import FoxDevicesCoordinator
from .const import DOMAIN, POOLING_INTERVAL, SCHEMA_INPUT_UPDATE_POOLING
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switch entries."""

    device_coordinator: FoxDevicesCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """

        await device_coordinator.async_fetch_switch_devices()

        return device_coordinator.get_switch_devices()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="switch",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=(
            POOLING_INTERVAL if SCHEMA_INPUT_UPDATE_POOLING not in config_entry.options
            else config_entry.options.get(SCHEMA_INPUT_UPDATE_POOLING))),
    )

    await coordinator.async_config_entry_first_refresh()
    for idx, ent in enumerate(coordinator.data):
        if isinstance(ent, FoxR2S2Device):
            for channel in ent.channels:
                entities.append(FoxBaseSwitch(coordinator, idx, channel))
        if isinstance(ent, FoxR1S1Device):
            entities.append(FoxBaseSwitch(coordinator, idx))

    async_add_entities(entities)
    return True


class FoxBaseSwitch(CoordinatorEntity, SwitchEntity):
    """Fox base switch implementation."""

    def __init__(self, coordinator, idx: int, channel: int = None):
        """Initialize object."""
        super().__init__(coordinator)
        self._idx = idx
        self._channel = channel

    @property
    def name(self):
        """Return the name of the device."""
        return (
            self.coordinator.data[self._idx].name
            if self._channel is None
            else self.coordinator.data[self._idx].get_channel_name(self._channel)
        )

    @property
    def is_on(self):
        """Return the is on property."""
        return self.coordinator.data[self._idx].is_on(self._channel)

    @property
    def available(self):
        """Return device availability."""
        return self.coordinator.data[self._idx].is_available

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        device = self.coordinator.data[self._idx]
        return f"{device.mac_addr}-{device.device_platform}-{self._channel}"

    @property
    def device_info(self):
        """Return device info data."""
        return self.coordinator.data[self._idx].get_device_info()

    @property
    def should_poll(self):
        """Return the polling state. Polling is needed."""
        return True

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the device."""
        if self.coordinator.data[self._idx].is_on(self._channel) is False:
            await self.coordinator.data[self._idx].async_update_channel_state(
                True, self._channel
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the device."""
        if self.coordinator.data[self._idx].is_on(self._channel) is True:
            await self.coordinator.data[self._idx].async_update_channel_state(
                False, self._channel
            )
        await self.coordinator.async_request_refresh()
