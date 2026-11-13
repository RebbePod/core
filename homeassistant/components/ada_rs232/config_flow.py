"""Config flow for the ADA RS-232 integration."""

import logging
from typing import Any, override

from ada_rs232 import AdaClient, AdaError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SerialPortSelector,
)

from .const import CONF_ADDRESS, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _async_attempt_connect(port: str, address: int) -> str | None:
    """Verify a response without changing amplifier state."""
    client = AdaClient(port, address=address)
    try:
        await client.async_get_state()
    except AdaError, ValueError:
        return "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception connecting to ADA amplifier")
        return "unknown"
    finally:
        await client.async_close()
    return None


class AdaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ADA RS-232."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_DEVICE: user_input[CONF_DEVICE]})
            data = {**user_input, CONF_ADDRESS: int(user_input[CONF_ADDRESS])}
            error = await _async_attempt_connect(data[CONF_DEVICE], data[CONF_ADDRESS])
            if error is None:
                return self.async_create_entry(title="ADA PTM-1645", data=data)
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(CONF_DEVICE): SerialPortSelector(),
                        probatio.Required(CONF_ADDRESS, default=1): NumberSelector(
                            NumberSelectorConfig(
                                min=1, max=9, step=1, mode=NumberSelectorMode.BOX
                            )
                        ),
                    }
                ),
                user_input or {},
            ),
            errors=errors,
        )
