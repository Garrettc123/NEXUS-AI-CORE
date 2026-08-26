"""DocuSign integration — contract creation, envelope sending, status polling."""
import os
import base64
from docusign_esign import ApiClient, EnvelopesApi, EnvelopeDefinition, Document, Signer, \
    SignHere, Tabs, Recipients

INTEGRATION_KEY = os.getenv("DOCUSIGN_INTEGRATION_KEY", "")
USER_ID = os.getenv("DOCUSIGN_USER_ID", "")
ACCOUNT_ID = os.getenv("DOCUSIGN_ACCOUNT_ID", "")
BASE_URL = os.getenv("DOCUSIGN_BASE_URL", "https://demo.docusign.net/restapi")
PRIVATE_KEY_PATH = os.getenv("DOCUSIGN_PRIVATE_KEY_PATH", "./secrets/docusign_rsa.key")


def _get_api_client() -> ApiClient:
    api_client = ApiClient()
    api_client.host = BASE_URL
    try:
        with open(PRIVATE_KEY_PATH, "r") as f:
            private_key = f.read()
        token = api_client.request_jwt_user_token(
            client_id=INTEGRATION_KEY,
            user_id=USER_ID,
            oauth_host_name="account-d.docusign.com",
            private_key_bytes=private_key.encode(),
            expires_in=3600,
            scopes=["signature", "impersonation"],
        )
        api_client.set_default_header("Authorization", f"Bearer {token.access_token}")
    except Exception:
        pass  # Will fail gracefully when keys not configured
    return api_client


async def send_contract(signer_name: str, signer_email: str,
                         document_b64: str, document_name: str,
                         subject: str = "Please sign this document") -> dict:
    """Send a DocuSign envelope for e-signature. Returns envelope_id."""
    api_client = _get_api_client()
    envelopes_api = EnvelopesApi(api_client)

    doc = Document(
        document_base64=document_b64,
        name=document_name,
        file_extension="pdf",
        document_id="1",
    )
    sign_here = SignHere(
        document_id="1", page_number="1",
        recipient_id="1", tab_label="SignHereTab",
        x_position="200", y_position="400",
    )
    signer = Signer(
        email=signer_email, name=signer_name,
        recipient_id="1", routing_order="1",
        tabs=Tabs(sign_here_tabs=[sign_here]),
    )
    envelope_definition = EnvelopeDefinition(
        email_subject=subject,
        documents=[doc],
        recipients=Recipients(signers=[signer]),
        status="sent",
    )
    results = envelopes_api.create_envelope(ACCOUNT_ID, envelope_definition=envelope_definition)
    return {"envelope_id": results.envelope_id, "status": results.status,
            "signer": signer_email}


async def get_envelope_status(envelope_id: str) -> dict:
    api_client = _get_api_client()
    envelopes_api = EnvelopesApi(api_client)
    envelope = envelopes_api.get_envelope(ACCOUNT_ID, envelope_id)
    return {"envelope_id": envelope_id, "status": envelope.status,
            "sent_date": str(envelope.sent_date_time),
            "completed_date": str(envelope.completed_date_time)}
