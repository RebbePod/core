"""The ADA RS-232 integration."""

from ada_rs232 import AdaClient

from homeassistant.const import CONF_DEVICE, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant

from .const import CONF_ADDRESS
from .coordinator import AdaConfigEntry, AdaCoordinator

PLATFORMS = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: AdaConfigEntry) -> None:
    """Set up ADA RS-232 from a config entry."""
    client = AdaClient(entry.data[CONF_DEVICE], address=entry.data[CONF_ADDRESS])
    coordinator = AdaCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    async def _async_stop(event: Event) -> None:
        await coordinator.async_shutdown()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: AdaConfigEntry) -> None:
    """Unload the platforms before releasing the connection."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
