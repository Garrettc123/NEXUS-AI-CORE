"""Qualification is not payment: prevent fake conversions and auto-checkout."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call
import pytest
from api.main import _trigger_conversion


@pytest.mark.asyncio
async def test_qualified_lead_does_not_create_payment_or_conversion():
    db = MagicMock()
    db.table.return_value.update.return_value.eq.return_value.execute = AsyncMock()
    db.table.return_value.insert.return_value.execute = AsyncMock()

    result = await _trigger_conversion(db, {"id": "lead-123", "email": "buyer@example.invalid"}, 85)

    assert result is False
    assert db.table.call_args_list == [call("leads"), call("lead_events")]
    update = db.table.return_value.update.call_args.args[0]
    assert update["status"] == "qualified"
    event = db.table.return_value.insert.call_args.args[0]
    assert event["event_type"] == "qualified_pending_approval"
    assert event["metadata"]["checkout_created"] is False
    assert event["metadata"]["outreach_sent"] is False
    assert not any(c.args[0] == "conversions" for c in db.table.call_args_list)
