"""
integrations/integration_bus.py

NEXUS-AI-CORE Integration Bus

Centralised event bus that connects all 8 platforms through a
unified publish/subscribe model. Agents and services emit events;
the bus fans them out to the appropriate downstream integrations.

Event types:
  revenue.received    → Supabase (ledger), Notion (log), Slack (alert)
  lead.scored         → Notion (upsert), Linear (issue), Slack (alert)
  shopify.order       → Supabase (ledger), Notion (log), Slack (revenue)
  base.transfer       → Supabase (ledger), Notion (log), Slack (alert)
  system.error        → Slack (error), GitHub (issue), Linear (issue)
  github.push         → Linear (status), Slack (info)
  deploy.success      → Slack (info), Notion (audit)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from integrations.github_client import GitHubClient
from integrations.slack_client import SlackClient
from integrations.base_coinbase_client import BaseCoinbaseClient
from integrations.shopify_client import ShopifyClient
from integrations.notion_client import NotionClient
from integrations.linear_client import LinearClient
from integrations.supabase_client import SupabaseClient
from integrations.huggingface_client import HuggingFaceClient

logger = logging.getLogger(__name__)


@dataclass
class BusEvent:
    type: str
    payload: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "nexus-core"


class IntegrationBus:
    """
    Singleton integration bus. Lazily initialises clients on first use.
    All secrets resolved through core.secrets (Vault-first).
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self._github = None
        self._slack = None
        self._base = None
        self._shopify = None
        self._notion = None
        self._linear = None
        self._supabase = None
        self._hf = None
        self._handlers: dict[str, list[Callable]] = {}
        self._register_default_handlers()
        logger.info("[Bus] Integration bus initialised")

    # ── Lazy client accessors ──────────────────────────────────────────────

    @property
    def github(self) -> GitHubClient:
        if not self._github:
            self._github = GitHubClient()
        return self._github

    @property
    def slack(self) -> SlackClient:
        if not self._slack:
            self._slack = SlackClient()
        return self._slack

    @property
    def base(self) -> BaseCoinbaseClient:
        if not self._base:
            self._base = BaseCoinbaseClient()
        return self._base

    @property
    def shopify(self) -> ShopifyClient:
        if not self._shopify:
            self._shopify = ShopifyClient()
        return self._shopify

    @property
    def notion(self) -> NotionClient:
        if not self._notion:
            self._notion = NotionClient()
        return self._notion

    @property
    def linear(self) -> LinearClient:
        if not self._linear:
            self._linear = LinearClient()
        return self._linear

    @property
    def supabase(self) -> SupabaseClient:
        if not self._supabase:
            self._supabase = SupabaseClient()
        return self._supabase

    @property
    def hf(self) -> HuggingFaceClient:
        if not self._hf:
            self._hf = HuggingFaceClient()
        return self._hf

    # ── Event system ───────────────────────────────────────────────────────

    def on(self, event_type: str, handler: Callable[[BusEvent], None]):
        self._handlers.setdefault(event_type, []).append(handler)

    def emit(self, event: BusEvent):
        logger.info("[Bus] emit %s from %s", event.type, event.source)
        handlers = self._handlers.get(event.type, []) + self._handlers.get("*", [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.error("[Bus] Handler error for %s: %s", event.type, exc)

    def publish(self, event_type: str, payload: dict, source: str = "nexus-core"):
        self.emit(BusEvent(type=event_type, payload=payload, source=source))

    # ── Default handlers ───────────────────────────────────────────────────

    def _register_default_handlers(self):

        def on_revenue_received(evt: BusEvent):
            p = evt.payload
            amount, currency, source = p.get("amount", 0), p.get("currency", "USD"), p.get("source", evt.source)
            try:
                self.supabase.log_revenue(source, amount, currency, meta=p)
            except Exception as e:
                logger.warning("[Bus] Supabase ledger write failed: %s", e)
            try:
                self.notion.log_revenue_event(source, amount, currency, notes=str(p))
            except Exception as e:
                logger.warning("[Bus] Notion revenue log failed: %s", e)
            try:
                self.slack.revenue_alert(amount, currency, source)
            except Exception as e:
                logger.warning("[Bus] Slack revenue alert failed: %s", e)

        def on_lead_scored(evt: BusEvent):
            p = evt.payload
            name, email = p.get("name", "Unknown"), p.get("email", "")
            score = p.get("score", 0.0)
            try:
                self.notion.upsert_lead(name, email, p.get("company", ""), score)
            except Exception as e:
                logger.warning("[Bus] Notion lead upsert failed: %s", e)
            if score >= 0.75:
                try:
                    self.linear.create_issue(
                        title=f"High-Value Lead: {name} ({email})",
                        description=f"Score: {score:.2f}\nCompany: {p.get('company', '')}\nSource: {evt.source}",
                        priority=1,
                    )
                except Exception as e:
                    logger.warning("[Bus] Linear issue creation failed: %s", e)
                try:
                    self.slack.alert(f":dart: High-value lead scored: *{name}* ({email}) — score `{score:.2f}`", level="success")
                except Exception as e:
                    logger.warning("[Bus] Slack lead alert failed: %s", e)

        def on_system_error(evt: BusEvent):
            p = evt.payload
            msg = p.get("message", "Unknown error")
            try:
                self.slack.alert(f"Error in `{evt.source}`: {msg}", level="error")
            except Exception as e:
                logger.warning("[Bus] Slack error alert failed: %s", e)
            try:
                self.linear.create_issue(
                    title=f"[ERROR] {evt.source}: {msg[:80]}",
                    description=str(p),
                    priority=1,
                )
            except Exception as e:
                logger.warning("[Bus] Linear error issue failed: %s", e)

        def on_shopify_order(evt: BusEvent):
            p = evt.payload
            self.publish("revenue.received", {
                "amount": float(p.get("total_price", 0)),
                "currency": p.get("currency", "USD"),
                "source": "shopify",
                "order_id": p.get("id"),
            }, source="shopify-bridge")

        def on_deploy_success(evt: BusEvent):
            p = evt.payload
            try:
                self.slack.alert(f":rocket: Deploy success: `{p.get('repo', '')}` @ `{p.get('sha', '')[:8]}`", level="success")
            except Exception as e:
                logger.warning("[Bus] Slack deploy alert failed: %s", e)
            try:
                self.notion.log_audit(f"Deploy: {p.get('repo', '')}", str(p))
            except Exception as e:
                logger.warning("[Bus] Notion audit log failed: %s", e)

        self.on("revenue.received", on_revenue_received)
        self.on("lead.scored", on_lead_scored)
        self.on("system.error", on_system_error)
        self.on("shopify.order", on_shopify_order)
        self.on("deploy.success", on_deploy_success)


# Module-level singleton
bus = IntegrationBus()
