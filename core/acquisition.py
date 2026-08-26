"""
core/acquisition.py
Stubs for Non-Paid Acquisition channels.

Channels:
  1. GitHub README CTAs  — outbound link tracker
  2. LinkedIn organic    — inbound webhook receiver
  3. Direct email        — inbound email parse
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. GitHub README CTAs — outbound link tracker
# ---------------------------------------------------------------------------

def track_github_cta_click(
    utm_source: str = "github",
    utm_medium: str = "readme",
    utm_campaign: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, str]:
    """
    Build a UTM-tagged URL for a GitHub README call-to-action link.

    In production this would also persist a click event to the analytics
    store. Here it returns the parameter dict that the caller can append
    to any destination URL.

    Parameters
    ----------
    utm_source:   Traffic source identifier (default 'github').
    utm_medium:   Medium identifier (default 'readme').
    utm_campaign: Optional campaign name.
    extra:        Additional key-value pairs to include.

    Returns
    -------
    Dict of UTM parameters suitable for URL query string construction.
    """
    params: dict[str, str] = {
        "utm_source": utm_source,
        "utm_medium": utm_medium,
    }
    if utm_campaign:
        params["utm_campaign"] = utm_campaign
    if extra:
        params.update({k: str(v) for k, v in extra.items()})

    logger.info("GitHub CTA click tracked: %s", params)
    return params


# ---------------------------------------------------------------------------
# 2. LinkedIn organic — webhook receiver
# ---------------------------------------------------------------------------

def receive_linkedin_webhook(payload: dict[str, Any]) -> dict[str, Any] | None:
    """
    Parse an inbound LinkedIn Lead Gen Form webhook payload and normalise it
    into the standard lead capture format expected by ``POST /leads``.

    Expected payload keys (LinkedIn Lead Gen Forms):
        - firstName, lastName, emailAddress
        - formName (maps to utm_campaign)
        - submittedAt (epoch ms)

    Returns None if the payload is missing required fields.
    """
    email = payload.get("emailAddress") or payload.get("email")
    if not email:
        logger.warning("LinkedIn webhook missing emailAddress: %s", payload)
        return None

    first = payload.get("firstName", "")
    last = payload.get("lastName", "")
    campaign = payload.get("formName") or payload.get("campaignName")

    lead_data: dict[str, Any] = {
        "email": email.strip().lower(),
        "name": f"{first} {last}".strip(),
        "source": "organic",
        "utm_source": "linkedin",
        "utm_medium": "organic",
    }
    if campaign:
        lead_data["utm_campaign"] = campaign

    logger.info("LinkedIn lead parsed: %s", lead_data["email"])
    return lead_data


# ---------------------------------------------------------------------------
# 3. Direct email — inbound parse
# ---------------------------------------------------------------------------

def parse_inbound_email(
    sender: str,
    subject: str,
    body: str,
    headers: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """
    Parse an inbound email (e.g. from SendGrid Inbound Parse webhook) and
    normalise it into the standard lead capture format.

    Parameters
    ----------
    sender:  Raw ``From`` header value, e.g. ``John Doe <john@example.com>``.
    subject: Email subject line (used as a rough intent signal).
    body:    Plain-text body of the email.
    headers: Optional dict of raw email headers for additional signals.

    Returns
    -------
    Normalised lead dict, or None if email address cannot be extracted.
    """
    email = _extract_email_address(sender)
    if not email:
        logger.warning("Could not extract email from sender: %s", sender)
        return None

    lead_data: dict[str, Any] = {
        "email": email,
        "source": "direct",
        "utm_source": "email",
        "utm_medium": "inbound",
        "metadata": {
            "subject": subject,
            "body_snippet": body[:200] if body else "",
        },
    }
    logger.info("Inbound email lead parsed: %s", email)
    return lead_data


def _extract_email_address(raw: str) -> str | None:
    """Extract a bare email address from a raw RFC 2822 sender string."""
    if not raw:
        return None
    raw = raw.strip()
    if "<" in raw and ">" in raw:
        start = raw.index("<") + 1
        end = raw.index(">")
        return raw[start:end].strip().lower() or None
    if "@" in raw:
        return raw.lower()
    return None
