"""Fail-closed outbound tests: no policy receipt means no SendGrid call."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import pytest

from integrations.sendgrid_client import SendGridClient
from agents.engagement_agent import EngagementAgent


@pytest.mark.asyncio
async def test_plain_send_requires_verified_approval(monkeypatch):
    client = SendGridClient()
    client.api_key = "fake-key"
    client._outbound_approved = AsyncMock(return_value=False)
    class ForbiddenHTTP:
        def __init__(self, *args, **kwargs):
            raise AssertionError("SendGrid was contacted without approval")
    monkeypatch.setattr("integrations.sendgrid_client.httpx.AsyncClient", ForbiddenHTTP)
    result = await client.send_email(to="buyer@example.invalid", subject="Offer", text="Hello")
    assert result == {"ok": False, "skipped": True, "reason": "approval_required"}
    client._outbound_approved.assert_awaited_once()


@pytest.mark.asyncio
async def test_template_send_requires_verified_approval(monkeypatch):
    client = SendGridClient()
    client.api_key = "fake-key"
    client._outbound_approved = AsyncMock(return_value=False)
    class ForbiddenHTTP:
        def __init__(self, *args, **kwargs):
            raise AssertionError("SendGrid was contacted without approval")
    monkeypatch.setattr("integrations.sendgrid_client.httpx.AsyncClient", ForbiddenHTTP)
    result = await client.send_template_email(to="buyer@example.invalid", template_id="d-abc")
    assert result["reason"] == "approval_required"


@pytest.mark.asyncio
async def test_approval_id_alone_fails_closed(monkeypatch):
    client = SendGridClient()
    monkeypatch.delenv("OUTBOUND_APPROVAL_REDEEM_URL", raising=False)
    assert not await client._outbound_approved("untrusted-id", {"hello": "world"})
    assert not await client._outbound_approved(None, {"hello": "world"})


@pytest.mark.asyncio
async def test_redeemed_matching_receipt_is_accepted(monkeypatch):
    client = SendGridClient()
    monkeypatch.setenv("OUTBOUND_APPROVAL_REDEEM_URL", "https://approval.example.invalid/redeem")
    monkeypatch.setattr("integrations.sendgrid_client.get_secret", lambda key, default="": "private-test-token")
    class FakeResponse:
        status_code = 200
        def __init__(self, request):
            self.request = request
        def json(self):
            return dict(self.request, approved=True, consumed=True)
    class FakeHTTP:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def post(self, url, headers, json):
            assert url.startswith("https://")
            assert headers["Authorization"] == "Bearer private-test-token"
            return FakeResponse(json)
    monkeypatch.setattr("integrations.sendgrid_client.httpx.AsyncClient", FakeHTTP)
    assert await client._outbound_approved("real-approval", {"to": ["buyer@example.invalid"]})


@pytest.mark.asyncio
async def test_unconsumed_replay_is_denied(monkeypatch):
    client = SendGridClient()
    monkeypatch.setenv("OUTBOUND_APPROVAL_REDEEM_URL", "https://approval.example.invalid/redeem")
    monkeypatch.setattr("integrations.sendgrid_client.get_secret", lambda key, default="": "private-test-token")
    class FakeResponse:
        status_code = 200
        def __init__(self, request):
            self.request = request
        def json(self):
            return dict(self.request, approved=True, consumed=False)
    class FakeHTTP:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def post(self, url, headers, json):
            return FakeResponse(json)
    monkeypatch.setattr("integrations.sendgrid_client.httpx.AsyncClient", FakeHTTP)
    assert not await client._outbound_approved("used-approval", {"to": ["buyer@example.invalid"]})


@pytest.mark.asyncio
async def test_engagement_logs_blocked_not_sent(monkeypatch):
    agent = EngagementAgent()
    agent._log_event = AsyncMock(return_value="event-1")
    fake_sendgrid = MagicMock()
    fake_sendgrid.send_email = AsyncMock(return_value={"ok": False, "skipped": True, "reason": "approval_required"})
    monkeypatch.setattr("agents.engagement_agent.get_sendgrid", lambda: fake_sendgrid)
    result = await agent.engage_lead({"id": "lead-1", "email": "buyer@example.invalid", "source": "direct"})
    assert result["status"] == "blocked"
    assert result["email_sent"] is False
    assert agent._log_event.call_args.kwargs["event_type"] == "engagement_blocked"
