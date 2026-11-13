"""Tests for read-only ADA amplifier discovery and selection."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from ada_rs232 import AdaConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ada_rs232.const import CONF_ADDRESS, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_ADDRESS, MOCK_PORT

INPUT = {CONF_DEVICE: MOCK_PORT}
DATA = {**INPUT, CONF_ADDRESS: MOCK_ADDRESS}
OFF = (False,) * 8


async def test_user_flow(
    hass: HomeAssistant,
    mock_bus: MagicMock,
    mock_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Select a single discovered amplifier without asking for its address."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert CONF_ADDRESS not in result["data_schema"].schema
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ADA PTM-1645 (1)"
    assert result["data"] == DATA
    assert result["result"].unique_id is None
    mock_bus.async_get_states.assert_awaited_once_with()
    mock_bus.async_close.assert_awaited_once()
    mock_bus.async_set_zone.assert_not_awaited()
    mock_bus.async_set_zones.assert_not_awaited()
    mock_bus.async_all_off.assert_not_awaited()
    mock_client.async_get_state.assert_not_awaited()
    mock_setup_entry.assert_awaited_once()


async def test_multiple_amplifiers(
    hass: HomeAssistant,
    mock_bus: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Offer only responding addresses, in order, and normalize the selection."""
    mock_bus.async_get_states.return_value = {9: OFF, 2: OFF}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "amplifier"
    assert result["data_schema"].schema[CONF_ADDRESS].config["options"] == ["2", "9"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: "9"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {**INPUT, CONF_ADDRESS: 9}
    mock_setup_entry.assert_awaited_once()
    mock_bus.async_get_states.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(AdaConnectionError("No reply"), "cannot_connect", id="connection"),
        pytest.param(ValueError("Invalid port"), "cannot_connect", id="invalid_port"),
        pytest.param(RuntimeError("Unexpected error"), "unknown", id="unexpected"),
    ],
)
async def test_error_recovery(
    hass: HomeAssistant,
    mock_bus: MagicMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Recover from every error to a successful config-entry result."""
    mock_bus.async_get_states.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    mock_bus.async_close.assert_awaited_once()
    mock_bus.async_get_states.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_setup_entry.assert_awaited_once()


async def test_empty_scan_recovery(
    hass: HomeAssistant,
    mock_bus: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Keep the connection form open until an amplifier responds."""
    mock_bus.async_get_states.return_value = {}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    mock_bus.async_get_states.return_value = {MOCK_ADDRESS: OFF}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_setup_entry.assert_awaited_once()


@pytest.mark.usefixtures("mock_config_entry")
async def test_duplicate_address(hass: HomeAssistant, mock_bus: MagicMock) -> None:
    """Reject a scan whose responding amplifier already has an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_config_entry")
async def test_existing_address_filtered(
    hass: HomeAssistant,
    mock_bus: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Select the remaining unconfigured amplifier without asking for a number."""
    mock_bus.async_get_states.return_value = {MOCK_ADDRESS: OFF, 9: OFF}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ADDRESS] == 9
    mock_setup_entry.assert_any_await(hass, result["result"])


async def test_duplicate_rechecked_after_selection(
    hass: HomeAssistant,
    mock_bus: MagicMock,
) -> None:
    """Reject an address configured by another flow while the chooser was open."""
    mock_bus.async_get_states.return_value = {1: OFF, 9: OFF}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["step_id"] == "amplifier"
    entry = MockConfigEntry(domain=DOMAIN, data={**INPUT, CONF_ADDRESS: 9})
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: "9"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_cancelled_scan_releases_connection(
    hass: HomeAssistant,
    mock_bus: MagicMock,
) -> None:
    """Release a temporary owner even if the config-flow request is cancelled."""
    started = asyncio.Event()

    async def scan() -> None:
        started.set()
        await asyncio.Future()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_bus.async_get_states.side_effect = scan
    task = asyncio.create_task(
        hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    mock_bus.async_close.assert_awaited_once()


async def test_overlapping_scan_cleanup(
    hass: HomeAssistant,
    mock_bus: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Overlapping last-owner closes must preserve connection-error recovery."""
    closing = [asyncio.Event(), asyncio.Event()]
    finish_close = [asyncio.Event(), asyncio.Event()]
    indices = iter(range(2))

    async def close() -> None:
        index = next(indices)
        closing[index].set()
        await finish_close[index].wait()

    first_form = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    second_form = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_bus.async_get_states.side_effect = AdaConnectionError("No reply")
    mock_bus.async_close.side_effect = close
    first = asyncio.create_task(
        hass.config_entries.flow.async_configure(first_form["flow_id"], INPUT)
    )
    await closing[0].wait()
    second = asyncio.create_task(
        hass.config_entries.flow.async_configure(second_form["flow_id"], INPUT)
    )
    await closing[1].wait()
    finish_close[0].set()
    first_result = await first
    finish_close[1].set()
    second_result = await second
    assert first_result["errors"] == {"base": "cannot_connect"}
    assert second_result["errors"] == {"base": "cannot_connect"}

    mock_bus.async_get_states.side_effect = None
    mock_bus.async_close.side_effect = None
    first_result = await hass.config_entries.flow.async_configure(
        first_result["flow_id"], INPUT
    )
    await hass.async_block_till_done()
    assert first_result["type"] is FlowResultType.CREATE_ENTRY
    mock_bus.async_get_states.return_value = {9: OFF}
    second_result = await hass.config_entries.flow.async_configure(
        second_result["flow_id"], INPUT
    )
    await hass.async_block_till_done()
    assert second_result["type"] is FlowResultType.CREATE_ENTRY
    mock_setup_entry.assert_any_await(hass, first_result["result"])
    mock_setup_entry.assert_any_await(hass, second_result["result"])
