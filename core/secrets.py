"""
nexus-ai-core · core/secrets.py

Unified secrets resolver with dual-backend support:
  1. HashiCorp Vault (KV v2) — primary for production
  2. GitHub Actions Secrets (via env injection) — fallback / CI
  3. .env file — local development only

Usage:
    from core.secrets import get_secret, SecretKey

    stripe_key = get_secret(SecretKey.STRIPE_SECRET_KEY)
    slack_token = get_secret(SecretKey.SLACK_BOT_TOKEN)
"""

import os
import logging
from enum import Enum
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)


# ── Secret Key Registry ───────────────────────────────────────────────────────

class SecretKey(str, Enum):
    # GitHub
    GITHUB_TOKEN             = "GITHUB_TOKEN"
    GITHUB_WEBHOOK_SECRET    = "GITHUB_WEBHOOK_SECRET"

    # Slack
    SLACK_BOT_TOKEN          = "SLACK_BOT_TOKEN"
    SLACK_SIGNING_SECRET     = "SLACK_SIGNING_SECRET"
    SLACK_WEBHOOK_URL        = "SLACK_WEBHOOK_URL"
    SLACK_CHANNEL_ALERTS     = "SLACK_CHANNEL_ALERTS"
    SLACK_CHANNEL_REVENUE    = "SLACK_CHANNEL_REVENUE"

    # Base / Coinbase
    BASE_API_KEY             = "BASE_API_KEY"
    BASE_PRIVATE_KEY         = "BASE_PRIVATE_KEY"
    BASE_WALLET_ADDRESS      = "BASE_WALLET_ADDRESS"
    CDP_API_KEY_NAME         = "CDP_API_KEY_NAME"
    CDP_API_KEY_PRIVATE_KEY  = "CDP_API_KEY_PRIVATE_KEY"

    # Shopify
    SHOPIFY_SHOP_DOMAIN      = "SHOPIFY_SHOP_DOMAIN"
    SHOPIFY_ACCESS_TOKEN     = "SHOPIFY_ACCESS_TOKEN"
    SHOPIFY_WEBHOOK_SECRET   = "SHOPIFY_WEBHOOK_SECRET"
    SHOPIFY_STOREFRONT_TOKEN = "SHOPIFY_STOREFRONT_TOKEN"

    # Notion
    NOTION_API_KEY           = "NOTION_API_KEY"
    NOTION_AUDIT_DB_ID       = "NOTION_AUDIT_DB_ID"
    NOTION_MEMORY_DB_ID      = "NOTION_MEMORY_DB_ID"
    NOTION_DOCS_PAGE_ID      = "NOTION_DOCS_PAGE_ID"
    NOTION_REVENUE_DB_ID     = "NOTION_REVENUE_DB_ID"
    NOTION_LEADS_DB_ID       = "NOTION_LEADS_DB_ID"

    # Linear
    LINEAR_API_KEY           = "LINEAR_API_KEY"
    LINEAR_TEAM_ID           = "LINEAR_TEAM_ID"
    LINEAR_PROJECT_ID        = "LINEAR_PROJECT_ID"
    LINEAR_WEBHOOK_SECRET    = "LINEAR_WEBHOOK_SECRET"

    # Supabase
    SUPABASE_URL             = "SUPABASE_URL"
    SUPABASE_ANON_KEY        = "SUPABASE_ANON_KEY"
    SUPABASE_SERVICE_ROLE_KEY = "SUPABASE_SERVICE_ROLE_KEY"
    SUPABASE_JWT_SECRET      = "SUPABASE_JWT_SECRET"

    # Hugging Face
    HUGGINGFACE_API_TOKEN    = "HUGGINGFACE_API_TOKEN"
    HF_EMBED_MODEL           = "HF_EMBED_MODEL"
    HF_SCORE_MODEL           = "HF_SCORE_MODEL"
    HF_SPACE_ID              = "HF_SPACE_ID"

    # Stripe
    STRIPE_SECRET_KEY        = "STRIPE_SECRET_KEY"
    STRIPE_WEBHOOK_SECRET    = "STRIPE_WEBHOOK_SECRET"
    STRIPE_PRICE_ID_STARTER  = "STRIPE_PRICE_ID_STARTER"
    STRIPE_PRICE_ID_GROWTH   = "STRIPE_PRICE_ID_GROWTH"
    STRIPE_PRICE_ID_ENTERPRISE = "STRIPE_PRICE_ID_ENTERPRISE"

    # OpenAI
    OPENAI_API_KEY           = "OPENAI_API_KEY"
    OPENAI_ORG_ID            = "OPENAI_ORG_ID"

    # HubSpot
    HUBSPOT_ACCESS_TOKEN     = "HUBSPOT_ACCESS_TOKEN"
    HUBSPOT_PORTAL_ID        = "HUBSPOT_PORTAL_ID"

    # SendGrid
    SENDGRID_API_KEY         = "SENDGRID_API_KEY"

    # DocuSign
    DOCUSIGN_INTEGRATION_KEY = "DOCUSIGN_INTEGRATION_KEY"
    DOCUSIGN_USER_ID         = "DOCUSIGN_USER_ID"
    DOCUSIGN_ACCOUNT_ID      = "DOCUSIGN_ACCOUNT_ID"
    DOCUSIGN_PRIVATE_KEY     = "DOCUSIGN_PRIVATE_KEY"

    # Internal
    NEXUS_SECRET             = "NEXUS_SECRET"


# ── Vault path mapping: SecretKey → (vault_path, vault_field) ─────────────────

VAULT_MAP: dict[str, tuple[str, str]] = {
    # GitHub
    "GITHUB_TOKEN":             ("secret/data/garcar/github", "GITHUB_TOKEN"),
    "GITHUB_WEBHOOK_SECRET":    ("secret/data/garcar/github", "GITHUB_WEBHOOK_SECRET"),
    # Slack
    "SLACK_BOT_TOKEN":          ("secret/data/garcar/slack", "SLACK_BOT_TOKEN"),
    "SLACK_SIGNING_SECRET":     ("secret/data/garcar/slack", "SLACK_SIGNING_SECRET"),
    "SLACK_WEBHOOK_URL":        ("secret/data/garcar/slack", "SLACK_WEBHOOK_URL"),
    "SLACK_CHANNEL_ALERTS":     ("secret/data/garcar/slack", "SLACK_CHANNEL_ALERTS"),
    "SLACK_CHANNEL_REVENUE":    ("secret/data/garcar/slack", "SLACK_CHANNEL_REVENUE"),
    # Base
    "BASE_API_KEY":             ("secret/data/garcar/base", "BASE_API_KEY"),
    "BASE_PRIVATE_KEY":         ("secret/data/garcar/base", "BASE_PRIVATE_KEY"),
    "BASE_WALLET_ADDRESS":      ("secret/data/garcar/base", "BASE_WALLET_ADDRESS"),
    "CDP_API_KEY_NAME":         ("secret/data/garcar/base", "CDP_API_KEY_NAME"),
    "CDP_API_KEY_PRIVATE_KEY":  ("secret/data/garcar/base", "CDP_API_KEY_PRIVATE_KEY"),
    # Shopify
    "SHOPIFY_SHOP_DOMAIN":      ("secret/data/garcar/shopify", "SHOPIFY_SHOP_DOMAIN"),
    "SHOPIFY_ACCESS_TOKEN":     ("secret/data/garcar/shopify", "SHOPIFY_ACCESS_TOKEN"),
    "SHOPIFY_WEBHOOK_SECRET":   ("secret/data/garcar/shopify", "SHOPIFY_WEBHOOK_SECRET"),
    "SHOPIFY_STOREFRONT_TOKEN": ("secret/data/garcar/shopify", "SHOPIFY_STOREFRONT_TOKEN"),
    # Notion
    "NOTION_API_KEY":           ("secret/data/garcar/notion", "NOTION_API_KEY"),
    "NOTION_AUDIT_DB_ID":       ("secret/data/garcar/notion", "NOTION_AUDIT_DB_ID"),
    "NOTION_MEMORY_DB_ID":      ("secret/data/garcar/notion", "NOTION_MEMORY_DB_ID"),
    "NOTION_DOCS_PAGE_ID":      ("secret/data/garcar/notion", "NOTION_DOCS_PAGE_ID"),
    "NOTION_REVENUE_DB_ID":     ("secret/data/garcar/notion", "NOTION_REVENUE_DB_ID"),
    "NOTION_LEADS_DB_ID":       ("secret/data/garcar/notion", "NOTION_LEADS_DB_ID"),
    # Linear
    "LINEAR_API_KEY":           ("secret/data/garcar/linear", "LINEAR_API_KEY"),
    "LINEAR_TEAM_ID":           ("secret/data/garcar/linear", "LINEAR_TEAM_ID"),
    "LINEAR_PROJECT_ID":        ("secret/data/garcar/linear", "LINEAR_PROJECT_ID"),
    "LINEAR_WEBHOOK_SECRET":    ("secret/data/garcar/linear", "LINEAR_WEBHOOK_SECRET"),
    # Supabase
    "SUPABASE_URL":             ("secret/data/garcar/supabase", "SUPABASE_URL"),
    "SUPABASE_ANON_KEY":        ("secret/data/garcar/supabase", "SUPABASE_ANON_KEY"),
    "SUPABASE_SERVICE_ROLE_KEY":("secret/data/garcar/supabase", "SUPABASE_SERVICE_ROLE_KEY"),
    "SUPABASE_JWT_SECRET":      ("secret/data/garcar/supabase", "SUPABASE_JWT_SECRET"),
    # HuggingFace
    "HUGGINGFACE_API_TOKEN":    ("secret/data/garcar/huggingface", "HUGGINGFACE_API_TOKEN"),
    "HF_EMBED_MODEL":           ("secret/data/garcar/huggingface", "HF_EMBED_MODEL"),
    "HF_SCORE_MODEL":           ("secret/data/garcar/huggingface", "HF_SCORE_MODEL"),
    "HF_SPACE_ID":              ("secret/data/garcar/huggingface", "HF_SPACE_ID"),
    # Stripe
    "STRIPE_SECRET_KEY":        ("secret/data/garcar/stripe", "STRIPE_SECRET_KEY"),
    "STRIPE_WEBHOOK_SECRET":    ("secret/data/garcar/stripe", "STRIPE_WEBHOOK_SECRET"),
    "STRIPE_PRICE_ID_STARTER":  ("secret/data/garcar/stripe", "STRIPE_PRICE_ID_STARTER"),
    "STRIPE_PRICE_ID_GROWTH":   ("secret/data/garcar/stripe", "STRIPE_PRICE_ID_GROWTH"),
    "STRIPE_PRICE_ID_ENTERPRISE":("secret/data/garcar/stripe", "STRIPE_PRICE_ID_ENTERPRISE"),
    # OpenAI
    "OPENAI_API_KEY":           ("secret/data/garcar/openai", "OPENAI_API_KEY"),
    "OPENAI_ORG_ID":            ("secret/data/garcar/openai", "OPENAI_ORG_ID"),
    # HubSpot
    "HUBSPOT_ACCESS_TOKEN":     ("secret/data/garcar/hubspot", "HUBSPOT_ACCESS_TOKEN"),
    "HUBSPOT_PORTAL_ID":        ("secret/data/garcar/hubspot", "HUBSPOT_PORTAL_ID"),
    # SendGrid
    "SENDGRID_API_KEY":         ("secret/data/garcar/sendgrid", "SENDGRID_API_KEY"),
    # DocuSign
    "DOCUSIGN_INTEGRATION_KEY": ("secret/data/garcar/docusign", "DOCUSIGN_INTEGRATION_KEY"),
    "DOCUSIGN_USER_ID":         ("secret/data/garcar/docusign", "DOCUSIGN_USER_ID"),
    "DOCUSIGN_ACCOUNT_ID":      ("secret/data/garcar/docusign", "DOCUSIGN_ACCOUNT_ID"),
    "DOCUSIGN_PRIVATE_KEY":     ("secret/data/garcar/docusign", "DOCUSIGN_PRIVATE_KEY"),
    # Internal
    "NEXUS_SECRET":             ("secret/data/garcar/internal", "NEXUS_SECRET"),
}


# ── Vault Client ──────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_vault_client():
    """Return a configured hvac Vault client, or None if Vault is not configured."""
    vault_addr = os.getenv("VAULT_ADDR")
    vault_token = os.getenv("VAULT_TOKEN")
    vault_role_id = os.getenv("VAULT_ROLE_ID")
    vault_secret_id = os.getenv("VAULT_SECRET_ID")

    if not vault_addr:
        return None

    try:
        import hvac  # type: ignore
        client = hvac.Client(url=vault_addr)

        if vault_token:
            client.token = vault_token
        elif vault_role_id and vault_secret_id:
            # AppRole auth — preferred for production deployments
            client.auth.approle.login(
                role_id=vault_role_id,
                secret_id=vault_secret_id,
            )
        else:
            logger.warning("[secrets] Vault configured but no auth method found.")
            return None

        if not client.is_authenticated():
            logger.error("[secrets] Vault auth failed.")
            return None

        logger.info("[secrets] Vault client authenticated at %s", vault_addr)
        return client

    except ImportError:
        logger.warning("[secrets] hvac not installed. pip install hvac to use Vault.")
        return None
    except Exception as exc:
        logger.error("[secrets] Vault client init failed: %s", exc)
        return None


def _read_vault(key: str) -> Optional[str]:
    """Read a single secret value from Vault KV v2."""
    client = _get_vault_client()
    if not client:
        return None

    vault_entry = VAULT_MAP.get(key)
    if not vault_entry:
        return None

    path, field = vault_entry
    try:
        # KV v2: path is "secret/data/..."
        mount, *parts = path.split("/", 2)
        kv_path = parts[-1] if parts else path
        response = client.secrets.kv.v2.read_secret_version(
            path=kv_path.replace("data/", "", 1),
            mount_point=mount,
        )
        return response["data"]["data"].get(field)
    except Exception as exc:
        logger.debug("[secrets] Vault read failed for %s: %s", key, exc)
        return None


# ── Primary API ───────────────────────────────────────────────────────────────

def get_secret(key: SecretKey | str, default: Optional[str] = None) -> Optional[str]:
    """
    Resolve a secret using the priority chain:
      1. HashiCorp Vault (if VAULT_ADDR is set)
      2. Environment variable (GitHub Actions secrets inject here)
      3. default value

    Args:
        key: A SecretKey enum member or raw env var name string.
        default: Fallback value if all backends miss.

    Returns:
        The secret value, or default.
    """
    key_str = key.value if isinstance(key, SecretKey) else key

    # 1. Try Vault first
    value = _read_vault(key_str)
    if value is not None:
        logger.debug("[secrets] %s resolved from Vault", key_str)
        return value

    # 2. Environment variable (GitHub Actions / Railway / .env)
    value = os.getenv(key_str)
    if value is not None:
        logger.debug("[secrets] %s resolved from environment", key_str)
        return value

    # 3. Default
    if default is not None:
        logger.warning("[secrets] %s not found — using default", key_str)
        return default

    logger.error("[secrets] MISSING SECRET: %s", key_str)
    return None


def require_secret(key: SecretKey | str) -> str:
    """Like get_secret, but raises RuntimeError if the secret is missing."""
    value = get_secret(key)
    if value is None:
        key_str = key.value if isinstance(key, SecretKey) else key
        raise RuntimeError(
            f"[secrets] Required secret '{key_str}' is not configured. "
            f"Set it in Vault at secret/garcar/ or as a GitHub Actions secret / env var."
        )
    return value


def list_missing_secrets() -> list[str]:
    """Returns a list of all SecretKeys that are currently unresolvable."""
    missing = []
    for key in SecretKey:
        if get_secret(key) is None:
            missing.append(key.value)
    return missing
