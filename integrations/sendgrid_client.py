"""SendGrid integration — transactional email for NEXUS revenue loops.

MCP-aligned tool surface (callable by agents and gateway):
  send_email          — plain / HTML transactional mail
  send_template_email — dynamic template by ID
  health              — API key present + optional authenticated probe

Credentials via core.secrets (Vault → env → default).
"""
from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

from core.secrets import SecretKey, get_secret

log = structlog.get_logger()

SENDGRID_API = "https://api.sendgrid.com/v3"


class SendGridClient:
    """Thin async client over SendGrid Mail Send API."""

    def __init__(self) -> None:
        self.api_key = get_secret(SecretKey.SENDGRID_API_KEY, "") or ""
        self.from_email = (
            get_secret(SecretKey.SENDGRID_FROM_EMAIL, "noreply@garcar.io")
            or os.getenv("SENDGRID_FROM_EMAIL", "noreply@garcar.io")
        )
        self.from_name = os.getenv("SENDGRID_FROM_NAME", "Garcar Enterprise")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def send_email(
        self,
        *,
        to: str | list[str],
        subject: str,
        text: str | None = None,
        html: str | None = None,
        from_email: str | None = None,
        from_name: str | None = None,
        reply_to: str | None = None,
        categories: list[str] | None = None,
        custom_args: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Send a transactional email. Returns status payload."""
        if not self.configured:
            log.info("sendgrid_skipped_no_key", to=to, subject=subject)
            return {"ok": False, "skipped": True, "reason": "missing_api_key"}

        recipients = [to] if isinstance(to, str) else list(to)
        if not recipients:
            return {"ok": False, "skipped": True, "reason": "no_recipients"}

        content: list[dict[str, str]] = []
        if text:
            content.append({"type": "text/plain", "value": text})
        if html:
            content.append({"type": "text/html", "value": html})
        if not content:
            content.append({"type": "text/plain", "value": subject})

        personalization: dict[str, Any] = {
            "to": [{"email": e} for e in recipients],
        }
        if custom_args:
            personalization["custom_args"] = custom_args

        payload: dict[str, Any] = {
            "personalizations": [personalization],
            "from": {
                "email": from_email or self.from_email,
                "name": from_name or self.from_name,
            },
            "subject": subject,
            "content": content,
        }
        if reply_to:
            payload["reply_to"] = {"email": reply_to}
        if categories:
            payload["categories"] = categories[:10]

        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{SENDGRID_API}/mail/send",
                headers=self._headers(),
                json=payload,
            )
            if r.status_code not in (200, 201, 202):
                log.warning(
                    "sendgrid_send_failed",
                    status=r.status_code,
                    body=r.text[:300],
                    to=recipients,
                )
                return {
                    "ok": False,
                    "status_code": r.status_code,
                    "error": r.text[:500],
                }

        log.info("sendgrid_sent", to=recipients, subject=subject, status=r.status_code)
        return {
            "ok": True,
            "status_code": r.status_code,
            "to": recipients,
            "subject": subject,
            "message_id": r.headers.get("X-Message-Id", ""),
        }

    async def send_template_email(
        self,
        *,
        to: str | list[str],
        template_id: str,
        dynamic_data: dict[str, Any] | None = None,
        from_email: str | None = None,
        from_name: str | None = None,
    ) -> dict[str, Any]:
        """Send using a SendGrid dynamic template."""
        if not self.configured:
            return {"ok": False, "skipped": True, "reason": "missing_api_key"}

        recipients = [to] if isinstance(to, str) else list(to)
        personalization: dict[str, Any] = {
            "to": [{"email": e} for e in recipients],
        }
        if dynamic_data:
            personalization["dynamic_template_data"] = dynamic_data

        payload = {
            "personalizations": [personalization],
            "from": {
                "email": from_email or self.from_email,
                "name": from_name or self.from_name,
            },
            "template_id": template_id,
        }

        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{SENDGRID_API}/mail/send",
                headers=self._headers(),
                json=payload,
            )
            if r.status_code not in (200, 201, 202):
                return {
                    "ok": False,
                    "status_code": r.status_code,
                    "error": r.text[:500],
                }

        return {
            "ok": True,
            "status_code": r.status_code,
            "to": recipients,
            "template_id": template_id,
            "message_id": r.headers.get("X-Message-Id", ""),
        }

    async def health(self) -> dict[str, Any]:
        """Report configuration + optional authenticated scopes probe."""
        if not self.configured:
            return {"ok": False, "configured": False, "reason": "missing_api_key"}

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{SENDGRID_API}/scopes",
                    headers=self._headers(),
                )
            return {
                "ok": r.status_code == 200,
                "configured": True,
                "from_email": self.from_email,
                "status_code": r.status_code,
            }
        except Exception as exc:
            return {
                "ok": False,
                "configured": True,
                "error": str(exc),
            }


# Module-level helpers for agents / MCP-style calls
_client: SendGridClient | None = None


def get_sendgrid() -> SendGridClient:
    global _client
    if _client is None:
        _client = SendGridClient()
    return _client


async def send_email(**kwargs: Any) -> dict[str, Any]:
    """MCP tool: send_email"""
    return await get_sendgrid().send_email(**kwargs)


async def send_template_email(**kwargs: Any) -> dict[str, Any]:
    """MCP tool: send_template_email"""
    return await get_sendgrid().send_template_email(**kwargs)


async def health() -> dict[str, Any]:
    """MCP tool: sendgrid_health"""
    return await get_sendgrid().health()
