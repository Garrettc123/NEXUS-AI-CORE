"""pytest conftest — mock out heavy third-party dependencies so agent modules
can be imported without installing every integration library."""
import sys
from unittest.mock import MagicMock

# Build lightweight mock objects for every heavy dep the agent/integration
# modules import at module level.  This must happen BEFORE any agent module
# is collected by pytest.

_MOCK_MODULES = [
    "structlog",
    "notion_client",
    "hubspot",
    "hubspot.crm",
    "hubspot.crm.contacts",
    "hubspot.crm.deals",
    "hubspot.crm.contacts.api",
    "docusign_esign",
    "stripe",
    "orjson",
    "ShopifyAPI",
    "pyactiveresource",
    "huggingface_hub",
    "transformers",
    "torch",
    "sentence_transformers",
    "gql",
    "supabase",
    "apscheduler",
    "apscheduler.schedulers",
    "apscheduler.schedulers.asyncio",
]

for _mod in _MOCK_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# Ensure structlog.get_logger() returns a mock with all log methods
_structlog = sys.modules["structlog"]
_logger = MagicMock()
_structlog.get_logger = MagicMock(return_value=_logger)
