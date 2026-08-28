"""Acquisition channel utilities for non-paid lead capture.

Channels:
  - GitHub README CTAs   → UTM-tagged outbound link params
  - LinkedIn Lead Gen    → normalize webhook payload → LeadRecord
  - Inbound email        → parse RFC 2822 From header → LeadRecord
"""
from __future__ import annotations

import email as _email_lib
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode


@dataclass
class LeadRecord:
    email: str
    source: str
    utm_source: str = ""
    utm_medium: str = ""
    first_name: str = ""
    last_name: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


# ── GitHub CTA ───────────────────────────────────────────────────────────────

def track_github_cta_click(
    base_url: str,
    campaign: str = "readme",
    content: str = "cta",
) -> dict[str, str]:
    """Return UTM-tagged query parameters for a GitHub README CTA link.

    Usage:
        params = track_github_cta_click("https://garcar.io/start")
        full_url = f"{params['url']}?{params['query_string']}"
    """
    params = {
        "utm_source": "github",
        "utm_medium": "readme",
        "utm_campaign": campaign,
        "utm_content": content,
    }
    return {
        "url": base_url,
        "query_string": urlencode(params),
        "full_url": f"{base_url}?{urlencode(params)}",
        **params,
    }


# ── LinkedIn ─────────────────────────────────────────────────────────────────

def receive_linkedin_webhook(payload: dict[str, Any]) -> LeadRecord:
    """Normalize a LinkedIn Lead Gen Form webhook payload into a LeadRecord.

    LinkedIn sends an array of field data objects; we extract email and name.
    """
    field_data: list[dict] = payload.get("fieldData", [])
    fields: dict[str, str] = {}
    for item in field_data:
        name = item.get("name", "").lower()
        values = item.get("values", [])
        fields[name] = values[0] if values else ""

    email = fields.get("email_address") or fields.get("email", "")
    first = fields.get("first_name", "")
    last = fields.get("last_name", "")

    return LeadRecord(
        email=email,
        source="referral",
        utm_source="linkedin",
        utm_medium="organic",
        first_name=first,
        last_name=last,
        raw=payload,
    )


# ── Inbound email ────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def parse_inbound_email(raw_from_header: str) -> LeadRecord:
    """Parse an RFC 2822 From header string into a LeadRecord.

    Accepts formats like:
      "John Doe <john@example.com>"
      "john@example.com"
    """
    # Use stdlib email to parse display-name + address
    name, addr = _email_lib.utils.parseaddr(raw_from_header)
    if not addr:
        # fallback: regex extraction
        match = _EMAIL_RE.search(raw_from_header)
        addr = match.group(0) if match else ""
        name = ""

    parts = name.strip().split(" ", 1) if name else []
    first = parts[0] if parts else ""
    last = parts[1] if len(parts) > 1 else ""

    return LeadRecord(
        email=addr,
        source="direct",
        utm_source="email",
        utm_medium="inbound",
        first_name=first,
        last_name=last,
        raw={"from": raw_from_header},
    )
