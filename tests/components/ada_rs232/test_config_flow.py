"""Tests for the ADA RS-232 config flow."""

from unittest.mock import AsyncMock, MagicMock

from ada_rs232 import AdaConnectionError
import pytest

from homeassistant.components.ada_rs232.const import CONF_ADDRESS, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_ADDRESS, MOCK_PORT

DATA = {CONF_DEVICE: MOCK_PORT, CONF_ADDRESS: MOCK_ADDRESS}


async def test_user_flow(
    hass: HomeAssistant, mock_client: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Verify that setup reads state and creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ADA PTM-1645"
    assert result["data"] == DATA
    assert result["result"].unique_id is None
    mock_client.async_get_state.assert_awaited_once()
    mock_client.async_set_zone.assert_not_awaited()
    mock_client.async_close.assert_awaited_once()
    mock_setup_entry.assert_awaited_once()


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
    mock_client: MagicMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Verify each error can recover to a successful terminal result."""
    mock_client.async_get_state.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    mock_client.async_close.assert_awaited_once()
    mock_client.async_get_state.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_setup_entry.assert_awaited_once()


@pytest.mark.usefixtures("mock_config_entry")
async def test_duplicate_port(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Reject a second entry for a port, even if the address differs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**DATA, CONF_ADDRESS: 2}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_client.async_get_state.assert_not_awaited()
