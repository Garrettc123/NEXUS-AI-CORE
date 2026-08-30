"""Tests for autonomous gateway agents and endpoints."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest

from agents.deal_pipeline_agent import DealPipelineAgent
from agents.lead_scoring_agent import LeadScoringAgent
from agents.property_scoring_agent import PropertyScoringAgent
from agents.revenue_loop_agent import RevenueLoopAgent
import agents.deal_pipeline_agent as deal_pipeline_mod
import agents.revenue_loop_agent as revenue_loop_mod
import app.main as gateway_mod
from app.main import app


class _Result:
    def __init__(self, data):
        self.data = data


class _Table:
    def __init__(self, db: "_FakeSupabase", name: str):
        self.db = db
        self.name = name
        self._filters: list[tuple[str, object]] = []
        self._single = False
        self._upsert_row: dict | None = None
        self._insert_row: dict | None = None
        self._select = False
        self._order_field: str | None = None
        self._order_desc = False

    def select(self, *_args):
        self._select = True
        return self

    def insert(self, row: dict):
        self._insert_row = row
        return self

    def upsert(self, row: dict, on_conflict: str = "id"):
        row["_on_conflict"] = on_conflict
        self._upsert_row = row
        return self

    def eq(self, field: str, value: object):
        self._filters.append((field, value))
        return self

    def order(self, field: str, desc: bool = False):
        self._order_field = field
        self._order_desc = desc
        return self

    def maybe_single(self):
        self._single = True
        return self

    async def execute(self):
        table = self.db.tables.setdefault(self.name, [])
        if self._insert_row is not None:
            table.append(dict(self._insert_row))
            return _Result(self._insert_row)
        if self._upsert_row is not None:
            row = dict(self._upsert_row)
            key = row.pop("_on_conflict")
            matched = False
            for idx, existing in enumerate(table):
                if existing.get(key) == row.get(key):
                    table[idx] = row
                    matched = True
                    break
            if not matched:
                table.append(row)
            return _Result(row)
        rows = list(table)
        for field, value in self._filters:
            rows = [row for row in rows if row.get(field) == value]
        if self._order_field is not None:
            rows = sorted(
                rows,
                key=lambda row: row.get(self._order_field, ""),
                reverse=self._order_desc,
            )
        if self._single:
            return _Result(rows[0] if rows else None)
        if self._select:
            return _Result(rows)
        return _Result(None)


class _FakeSupabase:
    def __init__(self):
        self.tables: dict[str, list[dict]] = {}

    def table(self, name: str) -> _Table:
        return _Table(self, name)


@pytest.mark.asyncio
async def test_lead_scoring_agent_parses_llm_score():
    agent = LeadScoringAgent()
    agent._request_score = AsyncMock(return_value="88")
    score = await agent.score_lead("Jane", "jane@example.com", "1 Main St")
    assert score == 88


@pytest.mark.asyncio
async def test_deal_pipeline_agent_upserts_and_lists(monkeypatch):
    fake_sb = _FakeSupabase()

    async def _get_client():
        return fake_sb

    monkeypatch.setattr(deal_pipeline_mod, "get_client", _get_client)
    agent = DealPipelineAgent()
    saved = await agent.upsert_deal("lead-1", "analysis", "good lead", "deal-1")
    listed = await agent.list_deals()
    assert saved["stage"] == "analysis"
    assert listed[0]["id"] == "deal-1"


@pytest.mark.asyncio
async def test_property_scoring_agent_returns_score_and_cap_rate():
    agent = PropertyScoringAgent()
    result = await agent.score_property(
        "100 Market St",
        {
            "annual_rent": 36000,
            "annual_expenses": 12000,
            "price": 300000,
            "bedrooms": 3,
            "year_built": 2010,
            "neighborhood_grade": "A",
        },
    )
    assert result["investment_score"] > 0
    assert result["cap_rate_estimate"] == 0.08


@pytest.mark.asyncio
async def test_revenue_loop_agent_logs_supported_events(monkeypatch):
    fake_sb = _FakeSupabase()

    async def _get_client():
        return fake_sb

    monkeypatch.setattr(revenue_loop_mod, "get_client", _get_client)
    agent = RevenueLoopAgent()
    result = await agent.handle_stripe_event(
        {
            "id": "evt_1",
            "type": "payment_intent.succeeded",
            "data": {"object": {"amount_received": 12500}},
        }
    )
    assert result["status"] == "processed"
    ignored = await agent.handle_stripe_event(
        {"id": "evt_2", "type": "customer.created", "data": {"object": {}}}
    )
    assert ignored["status"] == "ignored"


def test_api_required_endpoints(monkeypatch):
    fake_sb = _FakeSupabase()
    fake_sb.tables["deals"] = [{"id": "deal-1", "lead_id": "lead-1", "stage": "offer"}]

    async def _get_client():
        return fake_sb

    monkeypatch.setattr(gateway_mod, "get_client", _get_client)
    monkeypatch.setattr(
        gateway_mod.stripe.Webhook,
        "construct_event",
        lambda *_args, **_kwargs: {
            "id": "evt_1",
            "type": "checkout.session.completed",
            "data": {"object": {"amount_total": 5000}},
        },
    )

    with TestClient(app) as client:
        app.state.lead_scoring_agent = SimpleNamespace(
            score_lead=AsyncMock(return_value=77),
            run_pending=AsyncMock(return_value={}),
        )
        app.state.deal_pipeline_agent = SimpleNamespace(
            upsert_deal=AsyncMock(
                return_value={"id": "deal-1", "lead_id": "lead-1", "stage": "analysis"}
            ),
            list_deals=AsyncMock(return_value=fake_sb.tables["deals"]),
            run_pending=AsyncMock(return_value={}),
        )
        app.state.property_scoring_agent = SimpleNamespace(
            score_property=AsyncMock(
                return_value={"investment_score": 81, "cap_rate_estimate": 0.083}
            ),
            run_pending=AsyncMock(return_value={}),
        )
        app.state.revenue_loop_agent = SimpleNamespace(
            handle_stripe_event=AsyncMock(return_value={"status": "processed"}),
            run_pending=AsyncMock(return_value={}),
        )

        lead_resp = client.post(
            "/lead",
            json={
                "name": "Jane",
                "email": "jane@example.com",
                "property_address": "123 Main St",
            },
        )
        assert lead_resp.status_code == 200
        assert lead_resp.json()["score"] == 77

        deal_resp = client.post("/deal", json={"lead_id": "lead-1", "stage": "analysis"})
        assert deal_resp.status_code == 200

        deals_resp = client.get("/deals")
        assert deals_resp.status_code == 200
        assert isinstance(deals_resp.json(), list)

        property_resp = client.post(
            "/property/score",
            json={"address": "123 Main St", "property_data": {"price": 300000}},
        )
        assert property_resp.status_code == 200

        webhook_resp = client.post(
            "/stripe/webhook",
            data=b"{}",
            headers={"stripe-signature": "sig"},
        )
        assert webhook_resp.status_code == 200

        health_resp = client.get("/health")
        assert health_resp.status_code == 200
