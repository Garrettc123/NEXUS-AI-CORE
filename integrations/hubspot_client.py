"""HubSpot integration — CRM contacts, deals, pipeline."""
import os
from hubspot import HubSpot
from hubspot.crm.contacts import SimplePublicObjectInputForCreate
from hubspot.crm.deals import SimplePublicObjectInputForCreate as DealCreate

_client: HubSpot | None = None


def get_client() -> HubSpot:
    global _client
    if _client is None:
        _client = HubSpot(access_token=os.getenv("HUBSPOT_ACCESS_TOKEN", ""))
    return _client


async def upsert_contact(email: str, props: dict) -> dict:
    hs = get_client()
    props["email"] = email
    try:
        contact = hs.crm.contacts.basic_api.get_by_id(
            email, id_property="email", properties=list(props.keys())
        )
        updated = hs.crm.contacts.basic_api.update(
            contact.id, {"properties": props}
        )
        return {"action": "updated", "id": updated.id}
    except Exception:
        created = hs.crm.contacts.basic_api.create(
            SimplePublicObjectInputForCreate(properties=props)
        )
        return {"action": "created", "id": created.id}


async def create_deal(name: str, amount: float, stage: str = "appointmentscheduled",
                      contact_id: str | None = None) -> dict:
    hs = get_client()
    props = {"dealname": name, "amount": str(amount), "dealstage": stage,
             "pipeline": "default"}
    deal = hs.crm.deals.basic_api.create(
        DealCreate(properties=props)
    )
    if contact_id:
        hs.crm.deals.associations_api.create(
            deal.id, "contacts", contact_id, "deal_to_contact"
        )
    return {"deal_id": deal.id, "name": name, "stage": stage}


async def get_pipeline_summary() -> list:
    hs = get_client()
    deals = hs.crm.deals.get_all(properties=["dealname", "amount", "dealstage"])
    return [
        {"id": d.id, "name": d.properties.get("dealname"),
         "amount": d.properties.get("amount"),
         "stage": d.properties.get("dealstage")}
        for d in deals
    ]
