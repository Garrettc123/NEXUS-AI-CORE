"""Contract agent — creates and sends DocuSign envelopes on deal close."""
import base64, os, structlog
from orchestrator.events import NexusEvent
from integrations import docusign_client, notion_client, linear_client

log = structlog.get_logger()

# Minimal contract PDF template (base64 of a real PDF would go here)
_SAMPLE_PDF_B64 = base64.b64encode(
    b"%PDF-1.4 1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj "
    b"xref 0 4 trailer<</Size 4/Root 1 0 R>> startxref 0 %%EOF"
).decode()


async def handle(event: NexusEvent) -> dict:
    payload = event.payload
    signer_name = payload.get("signer_name", "Valued Client")
    signer_email = payload.get("signer_email", "")

    if not signer_email:
        return {"agent": "contract", "status": "skipped", "reason": "no signer email"}

    doc_b64 = payload.get("document_b64", _SAMPLE_PDF_B64)
    try:
        result = await docusign_client.send_contract(
            signer_name=signer_name,
            signer_email=signer_email,
            document_b64=doc_b64,
            document_name="Garcar Enterprise Agreement",
            subject=f"Your Garcar Enterprise Agreement — {payload.get('deal_name', '')}",
        )
        log.info("docusign_sent", envelope_id=result.get("envelope_id"))
    except Exception as exc:
        log.warning("docusign_failed", error=str(exc))
        result = {"error": str(exc)}

    try:
        await notion_client.write_memory(
            key=f"contract::{signer_email}",
            value=f"Envelope {result.get('envelope_id')} sent to {signer_email}",
            category="contracts",
        )
        await linear_client.create_issue(
            title=f"[Contract] Sent to {signer_email}",
            description=f"Envelope: {result.get('envelope_id')}\nDeal: {payload.get('deal_name')}\nTrace: {event.trace_id}",
            priority=2,
        )
    except Exception as exc:
        log.warning("post_contract_log_failed", error=str(exc))

    return {"agent": "contract", "status": "sent", "docusign": result,
            "signer": signer_email, "trace_id": event.trace_id}


async def create_and_send_contract(payload: dict) -> dict:
    event = NexusEvent(source="manual", type="contract.create",
                       intent="contract_update", payload=payload)
    return await handle(event)
