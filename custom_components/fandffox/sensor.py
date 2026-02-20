"""Support for F&F Fox sensors."""
from __future__ import annotations

from datetime import timedelta
import logging

from . import FoxDevicesCoordinator
from .const import DOMAIN, POOLING_INTERVAL, SCHEMA_INPUT_UPDATE_POOLING
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)

FOX_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="voltage",
        name="Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    SensorEntityDescription(
        key="current",
        name="Current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    SensorEntityDescription(
        key="power_active",
        name="Active power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SensorEntityDescription(
        key="power_reactive",
        name="Reactive power",
        device_class=None,
        native_unit_of_measurement="var",
    ),
    SensorEntityDescription(
        key="frequency",
        name="AC Frequency",
        device_class=None,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
    ),
    SensorEntityDescription(
        key="power_factor",
        name="Power factor",
        device_class=None,
    ),
    SensorEntityDescription(
        key="active_energy",
        name="Active energy",
        device_class=None,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SensorEntityDescription(
        key="reactive_energy",
        name="Reactive energy",
        device_class=None,
        native_unit_of_measurement="var",
    ),
    SensorEntityDescription(
        key="active_energy_import",
        name="Active energy import",
        device_class=None,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SensorEntityDescription(
        key="reactive_energy_import",
        name="Reactive energy import",
        device_class=None,
        native_unit_of_measurement="var",
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up F&F Fox Sensor from Config Entry."""

    entities = []
    device_coordinator: FoxDevicesCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        return device_coordinator.get_sensor_devices()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="sensor",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=(
            POOLING_INTERVAL if SCHEMA_INPUT_UPDATE_POOLING not in config_entry.options
            else config_entry.options.get(SCHEMA_INPUT_UPDATE_POOLING))),
    )

    await coordinator.async_config_entry_first_refresh()
    for idx, ent in enumerate(coordinator.data):
        # if isinstance(ent, FoxR1S1Device):
        entities += [
            FoxGenericSensor(coordinator, idx, description)
            for description in FOX_SENSORS
        ]
    async_add_entities(entities)
    return True


class FoxGenericSensor(CoordinatorEntity, SensorEntity):
    """Fox generic sensor implementation."""

    def __init__(self, coordinator, idx: int, description: SensorEntityDescription):
        """Initialize object."""
        super().__init__(coordinator)
        self._idx = idx
        self.entity_description = description
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def name(self):
        """Return the name of the device."""
        device = self.coordinator.data[self._idx]
        name = device.name if not device.name else "r1s1"
        return f"{name}-{device.mac_addr}-sensor-{self.entity_description.key}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        device = self.coordinator.data[self._idx]
        return f"{device.mac_addr}-sensor-{self.entity_description.key}"

    @property
    def device_info(self):
        """Return device info."""
        return self.coordinator.data[self._idx].get_device_info()

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data[self._idx].fetch_sensor_value_by_key(
            self.entity_description.key
        )
