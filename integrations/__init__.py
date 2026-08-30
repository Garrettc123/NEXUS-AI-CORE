"""
integrations/__init__.py

Master integration loader for NEXUS-AI-CORE.
All clients pull credentials from core.secrets (Vault → env → .env).

Usage:
    from integrations import github, slack, base, shopify, notion, linear, supabase, hf
"""

from integrations.github_client import GitHubClient
from integrations.slack_client import SlackClient
from integrations.base_coinbase_client import BaseCoinbaseClient
from integrations.shopify_client import ShopifyClient
from integrations.notion_client import NotionClient
from integrations.linear_client import LinearClient
from integrations.supabase_client import SupabaseClient
from integrations.huggingface_client import HuggingFaceClient
from integrations.stripe_client import StripeClient
from integrations.hubspot_client import HubSpotClient

__all__ = [
    "GitHubClient",
    "SlackClient",
    "BaseCoinbaseClient",
    "ShopifyClient",
    "NotionClient",
    "LinearClient",
    "SupabaseClient",
    "HuggingFaceClient",
    "StripeClient",
    "HubSpotClient",
]
