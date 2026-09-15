"""Tests for EngagementAgent and e2e acquisition loop wiring."""
from __future__ import annotations

from agents.engagement_agent import EngagementAgent, _SEQUENCE


class TestEngagementTemplates:
    def test_all_sources_have_templates(self):
        for source in ("organic", "referral", "direct"):
            assert source in _SEQUENCE
            assert "subject" in _SEQUENCE[source]
            assert "{cta}" in _SEQUENCE[source]["body"]

    def test_organic_mentions_autonomous(self):
        body = _SEQUENCE["organic"]["body"]
        assert "autonomous" in body.lower() or "Garcar" in body

    def test_name_line_formatting(self):
        body = _SEQUENCE["direct"]["body"].format(name_line=" Alex", cta="https://x.test")
        assert "Hi Alex," in body
        assert "https://x.test" in body


class TestEngagementAgentUnit:
    def test_agent_constructs(self):
        agent = EngagementAgent()
        assert agent is not None

    def test_missing_email_skips(self):
        import asyncio

        agent = EngagementAgent()

        async def _run():
            return await agent.engage_lead({"id": "x"}, reason="test")

        result = asyncio.get_event_loop().run_until_complete(_run())
        assert result["status"] == "skipped"
