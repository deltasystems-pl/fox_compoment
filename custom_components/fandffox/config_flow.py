"""Config flow for F&F Fox devices."""
from __future__ import annotations

import ipaddress
import logging
import re
from typing import Any

from foxrestapiclient.devices.const import DEVICES
from foxrestapiclient.devices.fox_base_device import DeviceData, FoxBaseDevice
from foxrestapiclient.devices.fox_service_discovery import FoxServiceDiscovery
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar

from .const import (
    DOMAIN,
    POOLING_INTERVAL,
    SCHEMA_INPUT_DEVICE_API_KEY,
    SCHEMA_INPUT_DEVICE_HOST,
    SCHEMA_INPUT_DEVICE_MAC,
    SCHEMA_INPUT_DEVICE_NAME_KEY,
    SCHEMA_INPUT_DEVICE_TYPE,
    SCHEMA_INPUT_ADD_ANOTHER,
    SCHEMA_INPUT_AUTO_ADD,
    SCHEMA_INPUT_ASSIGN_AREA,
    SCHEMA_INPUT_AREA_ID,
    SCHEMA_INPUT_UPDATE_POOLING,
    SCHEMA_INPUT_SKIP_CONFIG,
)

_LOGGER = logging.getLogger(__name__)

device_input_schema = vol.Schema(
    {
        vol.Optional(SCHEMA_INPUT_DEVICE_NAME_KEY): str,
        vol.Required(SCHEMA_INPUT_DEVICE_API_KEY, default="000"): str,
        vol.Optional(SCHEMA_INPUT_SKIP_CONFIG, default=False): bool,
    }
)

device_type_map = {DEVICES[k]: k for k in DEVICES}
manual_input_schema = vol.Schema(
    {
        vol.Optional(SCHEMA_INPUT_DEVICE_NAME_KEY): str,
        vol.Required(SCHEMA_INPUT_DEVICE_HOST): str,
        vol.Required(SCHEMA_INPUT_DEVICE_TYPE): vol.In(device_type_map),
        vol.Required(SCHEMA_INPUT_DEVICE_API_KEY, default="000"): str,
        vol.Optional(SCHEMA_INPUT_DEVICE_MAC): str,
        vol.Optional(SCHEMA_INPUT_ADD_ANOTHER, default=False): bool,
    }
)

_MAC_PATTERN = re.compile(r"^([0-9A-Fa-f]{2}([-:])){5}([0-9A-Fa-f]{2})$")

def _validate_manual_input(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate manual input fields."""
    errors: dict[str, str] = {}
    host = user_input.get(SCHEMA_INPUT_DEVICE_HOST)
    if host:
        try:
            ipaddress.ip_address(host)
        except ValueError:
            errors[SCHEMA_INPUT_DEVICE_HOST] = "invalid_host"
    mac = user_input.get(SCHEMA_INPUT_DEVICE_MAC)
    if mac:
        if not _MAC_PATTERN.match(mac):
            errors[SCHEMA_INPUT_DEVICE_MAC] = "invalid_mac"
    return errors

async def validate_input_pooling(
    hass: HomeAssistant, value: str
) -> dict[str, Any]:
    """Validate the user input allows us to set pooling."""
    errors = {}
    try:
        v = float(value)
        if v == 0:
            errors[SCHEMA_INPUT_UPDATE_POOLING] = "invalid_zero"
    except ValueError:
        errors[SCHEMA_INPUT_UPDATE_POOLING] = "invalid_value"
    return errors # errors

async def validate_input(
    hass: HomeAssistant, device_data: DeviceData
) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    errors = {}

    try:
        fetched_data = await FoxBaseDevice(device_data).async_fetch_device_info()
        if fetched_data is False:
            errors[SCHEMA_INPUT_DEVICE_API_KEY] = "wrong_api_key"
    except Exception:
        errors[SCHEMA_INPUT_DEVICE_HOST] = "cannot_connect"
    return errors # errors


async def serialize_dicovered_devices(
    hass: HomeAssistant, devices: list[DeviceData], area_id: str | None = None
) -> dict[str, list[str] | str]:
    """Serialize discovered and configured devices."""
    serialized: dict[str, list[str] | str] = {"discovered_devices": []}
    for device in devices:
        serialized["discovered_devices"].append(device.__dict__)
    if area_id:
        serialized["area_id"] = area_id
    return serialized


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ):
        """Manage the options."""
        #Set empty erros
        errors = {}
        if user_input is not None:
            errors = await validate_input_pooling(self.hass, user_input[SCHEMA_INPUT_UPDATE_POOLING])
            if errors == {}:
                user_input[SCHEMA_INPUT_UPDATE_POOLING] = float(user_input[SCHEMA_INPUT_UPDATE_POOLING])
                return self.async_create_entry(title="F&F Fox", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(SCHEMA_INPUT_UPDATE_POOLING,
                        default=("" if SCHEMA_INPUT_UPDATE_POOLING not in self.config_entry.options
                        else str(self.config_entry.options.get(SCHEMA_INPUT_UPDATE_POOLING)))): str,
                }
            ),
            errors=errors,
        )

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configuration flow."""

    VERSION = 2

    def __init__(self):
        """Initialize flow."""
        self._fox_service_discovery = FoxServiceDiscovery()
        self._discovered_devices: list[DeviceData] = []
        self._device_index = 0
        self._summary_displayed = False
        self._discover_task = None
        self._auto_add = True
        self._default_api_key = "000"
        self._assign_area = False
        self._area_id = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)

    async def _async_do_discover_task(self):
        """Do service discovery task."""

        # Discover F&F Fox devices in local network
        self._discovered_devices = await self._fox_service_discovery.async_discover_devices(
            default_tries=6, interval=2
        )
        # Filter out devices already configured
        existing_macs = set()
        for entry in self._async_current_entries():
            for dev in entry.data.get("discovered_devices", []):
                mac = dev.get("mac_addr")
                if mac:
                    existing_macs.add(mac)
        self._discovered_devices = [
            dev for dev in self._discovered_devices if dev.mac_addr not in existing_macs
        ]

        # Continue the flow after show progress when the task is done.
        # To avoid a potential deadlock we create a new task that continues the flow.
        # The task must be completely done so the flow can await the task
        # if needed and get the task result.
        self.hass.async_create_task(
            self.hass.config_entries.flow.async_configure(flow_id=self.flow_id)
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        # Check it is already configured
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            if user_input.get("manual", False):
                return self.async_show_form(
                    step_id="manual",
                    data_schema=manual_input_schema,
                    description_placeholders={},
                )
            self._auto_add = user_input.get(SCHEMA_INPUT_AUTO_ADD, True)
            self._default_api_key = user_input.get(SCHEMA_INPUT_DEVICE_API_KEY, "000")
            self._assign_area = user_input.get(SCHEMA_INPUT_ASSIGN_AREA, False)
            self._area_id = user_input.get(SCHEMA_INPUT_AREA_ID)
            self._discover_task = self.hass.async_create_task(self._async_do_discover_task())
            return self.async_show_progress(
                step_id="discovering_finished",
                progress_action="task",
                progress_task=self._discover_task,
            )
        area_reg = ar.async_get(self.hass)
        area_map = {a.name: a.id for a in area_reg.async_list_areas()}
        if area_map:
            area_selector = vol.In(area_map)
        else:
            area_selector = str
        data_schema = vol.Schema(
            {
                vol.Optional("manual", default=False): bool,
                vol.Optional(SCHEMA_INPUT_AUTO_ADD, default=True): bool,
                vol.Optional(SCHEMA_INPUT_DEVICE_API_KEY, default="000"): str,
                vol.Optional(SCHEMA_INPUT_ASSIGN_AREA, default=False): bool,
                vol.Optional(SCHEMA_INPUT_AREA_ID): area_selector,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            description_placeholders={},
        )

    async def async_step_discovering_finished(
        self, user_input: dict[str, Any] | None = None
    ):
        """Discovering finished."""
        return self.async_show_progress_done(next_step_id="discovering_summary")

    async def async_step_discovering_summary(
        self, user_input: dict[str, Any] | None = None
    ):
        """Handle the discovering summary."""
        # Get discovered devices
        devices = self._discovered_devices
        # There is no devices, abort.
        if len(devices) <= 0:
            return self.async_show_form(
                step_id="manual",
                data_schema=manual_input_schema,
                description_placeholders={},
            )
        if self._auto_add:
            for dev in devices:
                dev.api_key = self._default_api_key
            area_id = self._area_id if self._assign_area else None
            return self.async_create_entry(
                title="F&F Fox",
                data=await serialize_dicovered_devices(
                    self.hass, devices, area_id
                ),
            )
        if user_input is not None:
            if user_input.get("manual", False):
                return self.async_show_form(
                    step_id="manual",
                    data_schema=manual_input_schema,
                    description_placeholders={},
                )
        # If user input is not none, show configuration form.
        if getattr(self, "_summary_displayed", False):
            self._summary_displayed = False
            return self.async_show_form(
                step_id="configure_device",
                data_schema=device_input_schema,
                last_step=len(devices) == 1,
                description_placeholders={
                    "device_id": devices[0].mac_addr,
                    "device_host": devices[0].host,
                    "device_type": DEVICES[devices[0].dev_type]
                },
            )
        self._summary_displayed = True
        return self.async_show_form(
            step_id="discovering_summary",
            data_schema=vol.Schema({vol.Optional("manual", default=False): bool}),
            description_placeholders={"devices_amount": len(devices)},
            last_step=False,
        )

    async def async_step_configure_device(
        self, user_input: dict[str, Any] | None = None
    ):
        """Handle configure device step."""
        errors = {}
        if user_input is not None:
            current_device: DeviceData = (
                self._discovered_devices[self._device_index]
            )
            try:
                current_device.skip = user_input[SCHEMA_INPUT_SKIP_CONFIG]
                current_device.api_key = user_input[SCHEMA_INPUT_DEVICE_API_KEY]
                current_device.name = user_input[SCHEMA_INPUT_DEVICE_NAME_KEY]
            except KeyError:
                _LOGGER.info("Device name was not set. Default will be used.")
            errors = await validate_input(self.hass, current_device)
            if errors == {}:
                self._device_index = self._device_index + 1
                await self.async_set_unique_id(current_device.mac_addr)

        should_finish = len(self._discovered_devices) < (
            self._device_index + 1
        )
        if should_finish is True:
            return self.async_create_entry(
                title="F&F Fox",
                data=await serialize_dicovered_devices(
                    self.hass, self._discovered_devices
                ),
            )
        is_last_step = len(self._discovered_devices) == (
            self._device_index + 1
        )
        # Get next device to fill placeholders data
        next_device = self._discovered_devices[self._device_index]
        return self.async_show_form(
            step_id="configure_device",
            data_schema=device_input_schema,
            last_step=is_last_step,
            description_placeholders={
                "device_id": next_device.mac_addr,
                "device_host": next_device.host,
                "device_type": DEVICES[next_device.dev_type]
            },
            errors=errors,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ):
        """Manual setup when discovery fails."""
        errors = {}
        if user_input is not None:
            errors = _validate_manual_input(user_input)
            if errors:
                return self.async_show_form(
                    step_id="manual",
                    data_schema=manual_input_schema,
                    errors=errors,
                )
            device_type = user_input[SCHEMA_INPUT_DEVICE_TYPE]
            device_mac = user_input.get(SCHEMA_INPUT_DEVICE_MAC) or user_input[SCHEMA_INPUT_DEVICE_HOST]
            device = DeviceData(
                user_input.get(SCHEMA_INPUT_DEVICE_NAME_KEY),
                user_input[SCHEMA_INPUT_DEVICE_HOST],
                user_input[SCHEMA_INPUT_DEVICE_API_KEY],
                device_mac,
                device_type,
            )
            existing_macs = set()
            for entry in self._async_current_entries():
                for dev in entry.data.get("discovered_devices", []):
                    mac = dev.get("mac_addr")
                    if mac:
                        existing_macs.add(mac)
            if device.mac_addr in existing_macs:
                errors[SCHEMA_INPUT_DEVICE_MAC] = "device_exists"
                return self.async_show_form(
                    step_id="manual",
                    data_schema=manual_input_schema,
                    errors=errors,
                )
            errors = await validate_input(self.hass, device)
            if errors == {}:
                self._discovered_devices.append(device)
                if user_input.get(SCHEMA_INPUT_ADD_ANOTHER, False):
                    return self.async_show_form(
                        step_id="manual",
                        data_schema=manual_input_schema,
                        errors={},
                    )
                area_id = self._area_id if self._assign_area else None
                await self.async_set_unique_id(self._discovered_devices[0].mac_addr)
                return self.async_create_entry(
                    title="F&F Fox",
                    data=await serialize_dicovered_devices(
                        self.hass, self._discovered_devices, area_id
                    ),
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=manual_input_schema,
            errors=errors,
        )
