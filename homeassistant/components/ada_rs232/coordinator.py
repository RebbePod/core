"""State updates for ADA RS-232 amplifiers."""

from datetime import timedelta
import logging
from typing import override

from ada_rs232 import AdaClient, AdaError, ZoneState

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AdaCoordinator(DataUpdateCoordinator[ZoneState]):
    """Combine amplifier feedback with a periodic state query."""

    def __init__(
        self, hass: HomeAssistant, entry: AdaConfigEntry, client: AdaClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
            always_update=False,
        )
        self.client = client
        self._unsubscribe = client.subscribe(self._handle_state)

    @callback
    def _handle_state(self, state: ZoneState | None) -> None:
        """Handle feedback or a lost connection."""
        if state is None:
            self.async_set_update_error(
                UpdateFailed(
                    translation_domain=DOMAIN, translation_key="cannot_connect"
                )
            )
        else:
            self.async_set_updated_data(state)

    @override
    async def _async_update_data(self) -> ZoneState:
        """Query the amplifier, reconnecting if necessary."""
        try:
            return await self.client.async_get_state()
        except AdaError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err

    async def async_set_zone(self, zone: int, enabled: bool) -> None:
        """Change zone power and publish the confirmed output state."""
        try:
            state = await self.client.async_set_zone(zone, enabled)
        except AdaError as err:
            self.async_set_update_error(
                UpdateFailed(
                    translation_domain=DOMAIN, translation_key="cannot_connect"
                )
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        self.async_set_updated_data(state)

    @override
    async def async_shutdown(self) -> None:
        """Release the subscription and serial connection."""
        self._unsubscribe()
        await super().async_shutdown()
        await self.client.async_close()


type AdaConfigEntry = ConfigEntry[AdaCoordinator]
