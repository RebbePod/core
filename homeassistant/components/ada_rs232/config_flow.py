"""Config flow for the ADA RS-232 integration."""

import logging
from typing import Any, override
from uuid import uuid4

from ada_rs232 import AdaError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SerialPortSelector,
)

from .connection import acquire_connection, async_release_connection
from .const import CONF_ADDRESS, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _async_discover(hass: HomeAssistant, port: str) -> list[int]:
    """Read existing addresses without changing any amplifier settings."""
    owner = uuid4().hex
    bus = acquire_connection(hass, port, owner)
    try:
        return sorted(await bus.async_get_states())
    finally:
        await async_release_connection(hass, port, owner)


class AdaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Discover amplifiers on a selected serial connection."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the selected connection and discovered addresses."""
        self._port = ""
        self._addresses: list[int] = []

    def _address_configured(self, address: int) -> bool:
        """Return if this address already has an entry on the selected port."""
        return any(
            entry.data[CONF_DEVICE] == self._port
            and entry.data[CONF_ADDRESS] == address
            for entry in self._async_current_entries()
        )

    def _finish(self, address: int) -> ConfigFlowResult:
        """Create an entry after rechecking for duplicates."""
        self._async_abort_entries_match(
            {CONF_DEVICE: self._port, CONF_ADDRESS: address}
        )
        return self.async_create_entry(
            title=f"ADA PTM-1645 ({address})",
            data={CONF_DEVICE: self._port, CONF_ADDRESS: address},
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a port and scan for existing amplifiers."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._port = user_input[CONF_DEVICE]
            try:
                found = await _async_discover(self.hass, self._port)
            except AdaError, ValueError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception discovering ADA amplifiers")
                errors["base"] = "unknown"
            else:
                if not found:
                    errors["base"] = "cannot_connect"
                else:
                    self._addresses = [
                        address
                        for address in found
                        if not self._address_configured(address)
                    ]
                    if not self._addresses:
                        return self.async_abort(reason="already_configured")
                    if len(self._addresses) == 1:
                        return self._finish(self._addresses[0])
                    return await self.async_step_amplifier()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema({probatio.Required(CONF_DEVICE): SerialPortSelector()}),
                user_input or {},
            ),
            errors=errors,
        )

    async def async_step_amplifier(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select an unconfigured amplifier when several respond."""
        if user_input is not None:
            return self._finish(int(user_input[CONF_ADDRESS]))
        return self.async_show_form(
            step_id="amplifier",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_ADDRESS): SelectSelector(
                        SelectSelectorConfig(
                            options=[str(address) for address in self._addresses],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )
