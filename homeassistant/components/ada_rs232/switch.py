"""Support for ADA amplifier zone power switches."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ADDRESS, DOMAIN
from .coordinator import AdaConfigEntry, AdaCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the eight stereo zone switches."""
    async_add_entities(AdaZoneSwitch(entry, zone) for zone in range(1, 9))


class AdaZoneSwitch(CoordinatorEntity[AdaCoordinator], SwitchEntity):
    """A stereo zone on an ADA PTM-1645."""

    _attr_has_entity_name = True
    _attr_translation_key = "zone"

    def __init__(self, entry: AdaConfigEntry, zone: int) -> None:
        """Initialize the zone switch."""
        super().__init__(entry.runtime_data)
        self._zone = zone
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone}"
        self._attr_translation_placeholders = {"zone": str(zone)}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Audio Design Associates",
            model="PTM-1645",
            name=f"ADA PTM-1645 ({entry.data[CONF_ADDRESS]})",
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return the reported output state."""
        return self.coordinator.data[self._zone - 1]

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the zone on."""
        await self.coordinator.async_set_zone(self._zone, True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the zone off."""
        await self.coordinator.async_set_zone(self._zone, False)
