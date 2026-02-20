"""Platform for light integration."""
from datetime import timedelta
import logging

from foxrestapiclient.devices.fox_dim1s2_device import FoxDIM1S2Device
from foxrestapiclient.devices.fox_led2s2_device import FoxLED2S2Device
from foxrestapiclient.devices.fox_rgbw_device import FoxRGBWDevice

from . import FoxDevicesCoordinator
from .const import DOMAIN, POOLING_INTERVAL, SCHEMA_INPUT_UPDATE_POOLING
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntityFeature,
    LightEntity,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up lights entries."""

    device_coordinator: FoxDevicesCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """

        await device_coordinator.async_fetch_light_devices()

        return device_coordinator.get_light_devices()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="light",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=(
            POOLING_INTERVAL if SCHEMA_INPUT_UPDATE_POOLING not in config_entry.options
            else config_entry.options.get(SCHEMA_INPUT_UPDATE_POOLING))),
    )

    await coordinator.async_config_entry_first_refresh()
    for idx, ent in enumerate(coordinator.data):
        if isinstance(ent, FoxLED2S2Device):
            for channel in ent.channels:
                entities.append(FoxLED2S2Light(coordinator, idx, channel))
        elif isinstance(ent, FoxDIM1S2Device):
            entities.append(FoxDIM1S2Light(coordinator, idx, 1))
        elif isinstance(ent, FoxRGBWDevice):
            entities.append(FoxRGBWLight(coordinator, idx, 1))

    async_add_entities(entities)
    return True


class FoxBaseLight(CoordinatorEntity, LightEntity):
    """Fox base light implementation."""

    def __init__(self, coordinator, idx, channel=None) -> None:
        """Initialize object."""
        super().__init__(coordinator)
        self._idx = idx
        self._channel = channel

    @property
    def name(self):
        """Return the name of the device."""
        return self.coordinator.data[self._idx].name

    @property
    def is_on(self):
        """Return is on value."""
        return self.coordinator.data[self._idx].is_on(self._channel)

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.data[self._idx].is_available

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        device = self.coordinator.data[self._idx]
        return f"{device.mac_addr}-{device.device_platform}-{self._channel}"

    @property
    def device_info(self):
        """Return device info."""
        return self.coordinator.data[self._idx].get_device_info()

    @property
    def should_poll(self):
        """Return the polling state. Polling is needed."""
        return True

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on light."""
        if self.coordinator.data[self._idx].is_on(self._channel) is False:
            await self.coordinator.data[self._idx].async_update_channel_state(
                True, self._channel
            )
        if kwargs == {}:
            await self.coordinator.async_request_refresh()
            return
        if ATTR_BRIGHTNESS in kwargs:
            await self.coordinator.data[self._idx].async_update_channel_brightness(
                kwargs[ATTR_BRIGHTNESS], self._channel
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off light."""
        if self.coordinator.data[self._idx].is_on(self._channel) is True:
            await self.coordinator.data[self._idx].async_update_channel_state(
                False, self._channel
            )
        await self.coordinator.async_request_refresh()


class FoxDimmableLight(FoxBaseLight):
    """Fox dimmable light implementation."""

    def __init__(self, coordinator, idx, channel) -> None:
        """Initialize object."""
        super().__init__(coordinator, idx, channel=channel)

    @property
    def supported_features(self):
        """Return supported features."""
        return LightEntityFeature.BRIGHTNESS

    @property
    def color_mode(self):
        """Return the color mode of the light."""
        return ColorMode.BRIGHTNESS


class FoxLED2S2Light(FoxDimmableLight):
    """Fox led2s2 light implementation."""

    def __init__(self, coordinator, idx, channel) -> None:
        """Initialize object."""
        super().__init__(coordinator, idx, channel=channel)

    @property
    def brightness(self):
        """Set brightness."""
        if self._channel == 1:
            return self.coordinator.data[self._idx].channel_one_brightness
        return self.coordinator.data[self._idx].channel_two_brightness


class FoxDIM1S2Light(FoxDimmableLight):
    """Fox dim1s2 light implementation."""

    def __init__(self, coordinator, idx, channel=None) -> None:
        """Initialize object."""
        super().__init__(coordinator, idx, channel=channel)

    @property
    def brightness(self):
        """Get brightness."""
        return self.coordinator.data[self._idx].brightness

    @property
    def is_on(self):
        """Get is on property."""
        return self.coordinator.data[self._idx].is_on()


class FoxRGBWLight(FoxBaseLight):
    """Fox rgbw light implementation."""

    def __init__(self, coordinator, idx, channel=None) -> None:
        """Initialize object."""
        super().__init__(coordinator, idx, channel=channel)

    @property
    def supported_features(self):
        """Return supported features."""
        return LightEntityFeature.BRIGHTNESS | LightEntityFeature.COLOR

    @property
    def brightness(self):
        """Return brightness value."""
        return self.coordinator.data[self._idx].get_brightness()

    @property
    def hs_color(self):
        """Get HS color."""
        return self.coordinator.data[self._idx].get_hs_color()

    @property
    def color_mode(self):
        """Return the color mode of the light."""
        return ColorMode.HS

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on device."""
        if self.coordinator.data[self._idx].is_on(self._channel) is False:
            await self.coordinator.data[self._idx].async_update_channel_state(
                True, self._channel
            )
        if kwargs == {}:
            await self.coordinator.async_request_refresh()
            return
        if ATTR_HS_COLOR in kwargs:
            hs = kwargs[ATTR_HS_COLOR]
            # Hue minus 1 because Fox RGBW device supports hue in range 0 - 359
            await self.coordinator.data[self._idx].async_set_color_hsv(hs[0] - 1, hs[1])
        elif ATTR_BRIGHTNESS in kwargs:
            await self.coordinator.data[self._idx].async_set_brightness(
                (kwargs[ATTR_BRIGHTNESS] / 255)
                * 100  # Fox RGBW light supports brightness from 0 to 100
            )
        await self.coordinator.async_request_refresh()
