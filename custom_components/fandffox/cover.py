"""F&F Fox cover platform implementation."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.helpers import entity_platform
import voluptuous as vol
from . import FoxDevicesCoordinator
from .const import DOMAIN, POOLING_INTERVAL, SCHEMA_INPUT_UPDATE_POOLING
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

        await device_coordinator.async_fetch_cover_devices()

        return device_coordinator.get_cover_devices()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="cover",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=(
            POOLING_INTERVAL if SCHEMA_INPUT_UPDATE_POOLING not in config_entry.options
            else config_entry.options.get(SCHEMA_INPUT_UPDATE_POOLING))),
    )

    await coordinator.async_config_entry_first_refresh()
    for idx, ent in enumerate(coordinator.data):
        entities.append(FoxBaseCover(coordinator, idx))
    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "set_cover_and_tilt_positions",
        {
            vol.Required(ATTR_POSITION): vol.Coerce(int),
            vol.Required(ATTR_TILT_POSITION): vol.Coerce(int),
        },
        "async_set_cover_and_tilt_positions_service",
    )
    platform.async_register_entity_service(
        "set_cover_position_with_blocking",
        {
            vol.Required(ATTR_POSITION): vol.Coerce(int),
            vol.Required("blocking_time"): vol.Coerce(int),
        },
        "async_set_cover_position_with_blocking_service",
    )

    return True


class FoxBaseCover(CoordinatorEntity, CoverEntity):
    """Fox base cover implementation."""

    def __init__(self, coordinator: DataUpdateCoordinator, idx: int) -> None:
        """Initialize object."""
        super().__init__(coordinator)
        self._idx = idx

    @property
    def name(self):
        """Return the name of the device."""
        return self.coordinator.data[self._idx].name

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.data[self._idx].is_available

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        device = self.coordinator.data[self._idx]
        return f"{device.mac_addr}-{device.device_platform}"

    @property
    def device_info(self):
        """Return device info."""
        return self.coordinator.data[self._idx].get_device_info()

    @property
    def supported_features(self):
        """Return supported features."""
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.SET_TILT_POSITION
            | CoverEntityFeature.STOP
        )

    @property
    def device_class(self):
        """Return device class."""
        return CoverDeviceClass.BLIND

    @property
    def is_closed(self) -> bool | None:
        """Return is closed."""
        return self.coordinator.data[self._idx].is_cover_closed()

    @property
    def current_cover_position(self) -> int | None:
        """Return current cover position."""
        return self.coordinator.data[self._idx].get_cover_position()

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current cover tilt position."""
        return self.coordinator.data[self._idx].get_tilt_position()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self.coordinator.data[self._idx].async_open_cover()
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        await self.coordinator.data[self._idx].async_close_cover()
        await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs):
        """Set cover position."""
        position = kwargs.get(ATTR_POSITION)
        if position is None:
            return
        await self.coordinator.data[self._idx].async_set_cover_position(int(position))
        await self.coordinator.async_request_refresh()

    async def async_set_cover_tilt_position(self, **kwargs):
        """Set cover tilt position."""
        position = kwargs.get(ATTR_TILT_POSITION)
        if position is None:
            return
        await self.coordinator.data[self._idx].async_set_tilt_position(int(position))
        await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs):
        """Stop cover movement."""
        await self.coordinator.data[self._idx].async_stop()
        await self.coordinator.async_request_refresh()

    async def async_set_cover_and_tilt_positions_service(
        self, position: int, tilt_position: int
    ):
        """Set cover and tilt positions in one call."""
        await self.coordinator.data[self._idx].async_set_cover_and_tilt_positions(
            int(position), int(tilt_position)
        )
        await self.coordinator.async_request_refresh()

    async def async_set_cover_position_with_blocking_service(
        self, position: int, blocking_time: int
    ):
        """Set cover position with blocking time."""
        await self.coordinator.data[self._idx].async_set_cover_position_with_blocking(
            int(position), int(blocking_time)
        )
        await self.coordinator.async_request_refresh()
