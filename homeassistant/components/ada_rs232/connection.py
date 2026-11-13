"""Share a PAC bus between amplifiers on the same serial connection."""

from dataclasses import dataclass, field

from ada_rs232 import AdaBus

from homeassistant.core import HomeAssistant
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN


@dataclass
class SharedConnection:
    """One connection and the config entries or probes using it."""

    bus: AdaBus
    owners: set[str] = field(default_factory=set)


_CONNECTIONS: HassKey[dict[str, SharedConnection]] = HassKey(DOMAIN)


def acquire_connection(hass: HomeAssistant, port: str, owner: str) -> AdaBus:
    """Reserve ownership before any operation can open the serial port."""
    registry = hass.data.setdefault(_CONNECTIONS, {})
    if (shared := registry.get(port)) is None:
        shared = registry[port] = SharedConnection(AdaBus(port))
    shared.owners.add(owner)
    return shared.bus


async def async_release_connection(hass: HomeAssistant, port: str, owner: str) -> None:
    """Close the bus when its last owner releases it."""
    registry = hass.data[_CONNECTIONS]
    if (shared := registry.get(port)) is None or owner not in shared.owners:
        return
    shared.owners.remove(owner)
    if shared.owners:
        return
    await shared.bus.async_close()
    if not shared.owners and registry.get(port) is shared:
        registry.pop(port)
