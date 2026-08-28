"""Tests for agent handlers — offline/unit tests using mocks."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from orchestrator.events import NexusEvent

# Agent modules import cleanly because conftest.py has already mocked
# all heavy third-party deps in sys.modules.
import agents.fallback_agent as fallback_mod
import agents.revenue_agent as revenue_mod
import agents.inventory_agent as inventory_mod
import agents.scoring_agent as scoring_mod


def _event(source: str = "stripe", intent: str = "revenue",
           payload: dict | None = None) -> NexusEvent:
    return NexusEvent(
        source=source,
        type="test.event",
        intent=intent,
        payload=payload or {},
    )


# ── fallback agent ────────────────────────────────────────────────────────────

class TestFallbackAgent:
    @pytest.mark.asyncio
    async def test_returns_logged_status(self):
        fallback_mod.notion_client.write_memory = AsyncMock()
        result = await fallback_mod.handle(_event(intent="default"))
        assert result["agent"] == "fallback"
        assert result["status"] == "logged"

    @pytest.mark.asyncio
    async def test_notion_failure_does_not_raise(self):
        fallback_mod.notion_client.write_memory = AsyncMock(
            side_effect=Exception("notion down")
        )
        result = await fallback_mod.handle(_event())
        assert result["status"] == "logged"


# ── revenue agent ────────────────────────────────────────────────────────────

class TestRevenueAgent:
    @pytest.mark.asyncio
    async def test_extracts_amount(self):
        revenue_mod.linear_client.create_issue = AsyncMock(return_value={"id": "lin-1"})
        revenue_mod.notion_client.write_memory = AsyncMock()
        result = await revenue_mod.handle(_event(payload={"amount": 4900}))
        assert result["amount"] == 4900
        assert result["agent"] == "revenue"

    @pytest.mark.asyncio
    async def test_handles_shopify_total_price(self):
        revenue_mod.linear_client.create_issue = AsyncMock(return_value={"id": "lin-1"})
        revenue_mod.notion_client.write_memory = AsyncMock()
        result = await revenue_mod.handle(
            _event(source="shopify", payload={"total_price": "99.00"})
        )
        assert result["amount"] == "99.00"

    @pytest.mark.asyncio
    async def test_linear_failure_does_not_raise(self):
        revenue_mod.linear_client.create_issue = AsyncMock(
            side_effect=Exception("linear down")
        )
        revenue_mod.notion_client.write_memory = AsyncMock()
        result = await revenue_mod.handle(_event())
        assert result["status"] == "processed"


# ── inventory agent ──────────────────────────────────────────────────────────

class TestInventoryAgent:
    @pytest.mark.asyncio
    async def test_low_stock_creates_linear_issue(self):
        mock_create = AsyncMock(return_value={"id": "lin-inv-1"})
        inventory_mod.linear_client.create_issue = mock_create
        inventory_mod.notion_client.write_memory = AsyncMock()
        payload = {"id": "prod-1", "title": "Widget",
                   "variants": [{"inventory_quantity": 2}]}
        await inventory_mod.handle(_event(payload=payload))
        mock_create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_high_stock_no_linear_issue(self):
        mock_create = AsyncMock()
        inventory_mod.linear_client.create_issue = mock_create
        inventory_mod.notion_client.write_memory = AsyncMock()
        payload = {"id": "prod-2", "title": "Widget",
                   "variants": [{"inventory_quantity": 100}]}
        await inventory_mod.handle(_event(payload=payload))
        mock_create.assert_not_awaited()


# ── scoring agent ────────────────────────────────────────────────────────────

class TestScoringAgent:
    @pytest.mark.asyncio
    async def test_returns_score_and_priority(self):
        scoring_mod.huggingface_client.score_deal = AsyncMock(return_value=0.9)
        scoring_mod.linear_client.create_issue = AsyncMock(
            return_value={"id": "lin-s-1"}
        )
        result = await scoring_mod.handle(
            _event(intent="deal", payload={"company": "Acme", "company_size": 500})
        )
        assert result["score"] == 0.9
        assert result["priority"] == 1

    @pytest.mark.asyncio
    async def test_medium_score_priority_2(self):
        scoring_mod.huggingface_client.score_deal = AsyncMock(return_value=0.6)
        scoring_mod.linear_client.create_issue = AsyncMock(
            return_value={"id": "lin-s-2"}
        )
        result = await scoring_mod.handle(_event(intent="deal"))
        assert result["priority"] == 2

    @pytest.mark.asyncio
    async def test_low_score_priority_3(self):
        scoring_mod.huggingface_client.score_deal = AsyncMock(return_value=0.3)
        scoring_mod.linear_client.create_issue = AsyncMock(
            return_value={"id": "lin-s-3"}
        )
        result = await scoring_mod.handle(_event(intent="deal"))
        assert result["priority"] == 3


# ── NexusEvent model ──────────────────────────────────────────────────────────

class TestNexusEvent:
    def test_defaults_populated(self):
        event = NexusEvent(source="test", type="t", intent="i")
        assert event.id
        assert event.trace_id
        assert event.ts
        assert event.priority == 5

    def test_payload_default_empty_dict(self):
        event = NexusEvent(source="test", type="t", intent="i")
        assert event.payload == {}

    def test_custom_priority(self):
        event = NexusEvent(source="test", type="t", intent="i", priority=1)
        assert event.priority == 1
