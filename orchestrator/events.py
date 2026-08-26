"""Canonical NEXUS event envelope — every integration produces this."""
from pydantic import BaseModel, Field
from typing import Any, Optional
import uuid
from datetime import datetime, timezone


class NexusEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str                          # shopify | stripe | hubspot | linear | docusign | ...
    type: str                            # e.g. payment_intent.succeeded
    intent: str                          # revenue | crm_update | task_update | contract_update | ...
    actor: Optional[str] = None          # user id or system name
    routing_target: Optional[str] = None # agent to invoke
    priority: int = 5                    # 1=critical .. 10=low
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: dict[str, Any] = {}
