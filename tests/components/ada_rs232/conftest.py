"""Fixtures for the ADA RS-232 integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ada_rs232.const import CONF_ADDRESS, DOMAIN
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant

from . import MOCK_ADDRESS, MOCK_PORT


@pytest.fixture(autouse=True)
def mock_usb_component(hass: HomeAssistant) -> None:
    """Skip hardware enumeration when testing the amplifier integration."""
    hass.config.components.add("usb")


@pytest.fixture
def mock_client(mock_bus: MagicMock) -> Generator[MagicMock]:
    """Mock the external library, keeping Home Assistant setup real."""
    with patch(
        "homeassistant.components.ada_rs232.AdaClient", autospec=True
    ) as factory:
        client = factory.return_value
        client.async_get_state.return_value = (False,) * 8
        client.async_set_zone.return_value = (True,) + (False,) * 7
        client.subscribe.return_value = MagicMock()
        yield client


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create an amplifier config entry without a fabricated hardware ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="01KPBBPM6WCQ8148EFR0TCG1WW",
        title=f"ADA PTM-1645 ({MOCK_ADDRESS})",
        data={CONF_DEVICE: MOCK_PORT, CONF_ADDRESS: MOCK_ADDRESS},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_setup_entry(mock_client: MagicMock) -> Generator[AsyncMock]:
    """Keep flow tests from also setting up the entry."""
    with patch(
        "homeassistant.components.ada_rs232.async_setup_entry", return_value=None
    ) as setup:
        yield setup


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the integration through Home Assistant."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def mock_bus() -> Generator[MagicMock]:
    """Mock the serial library boundary while keeping shared ownership real."""
    with patch(
        "homeassistant.components.ada_rs232.connection.AdaBus", autospec=True
    ) as factory:
        bus = factory.return_value
        bus.port = MOCK_PORT
        bus.async_get_states.return_value = {MOCK_ADDRESS: (False,) * 8}
        bus.async_get_state.return_value = (False,) * 8
        bus.subscribe.return_value = MagicMock()
        yield bus
