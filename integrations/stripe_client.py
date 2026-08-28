"""Stripe integration — payments, subscriptions, webhook verification."""
import os
import stripe
from orchestrator.events import NexusEvent

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


def verify_and_parse_stripe_webhook(payload: bytes, sig_header: str) -> NexusEvent:
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError as e:
        raise ValueError(f"Stripe signature verification failed: {e}")
    return NexusEvent(
        source="stripe",
        type=event["type"],
        intent=_classify_stripe(event["type"]),
        payload=event["data"]["object"],
    )


def _classify_stripe(event_type: str) -> str:
    if "payment_intent" in event_type or "charge" in event_type:
        return "revenue"
    if "customer.subscription" in event_type:
        return "revenue"
    if "invoice" in event_type:
        return "revenue"
    return "default"


async def create_payment_link(amount_cents: int, currency: str = "usd",
                               description: str = "Garcar Service") -> str:
    """Create a one-time Stripe Payment Link and return the URL."""
    product = stripe.Product.create(name=description)
    price = stripe.Price.create(
        product=product["id"],
        unit_amount=amount_cents,
        currency=currency,
    )
    link = stripe.PaymentLink.create(line_items=[{"price": price["id"], "quantity": 1}])
    return link["url"]


async def create_subscription(customer_email: str, price_id: str) -> dict:
    # Find or create customer
    customers = stripe.Customer.list(email=customer_email, limit=1)
    if customers.data:
        customer = customers.data[0]
    else:
        customer = stripe.Customer.create(email=customer_email)
    sub = stripe.Subscription.create(
        customer=customer["id"],
        items=[{"price": price_id}],
        payment_behavior="default_incomplete",
        expand=["latest_invoice.payment_intent"],
    )
    return {"subscription_id": sub["id"], "status": sub["status"],
            "client_secret": sub["latest_invoice"]["payment_intent"]["client_secret"]}


async def get_revenue_summary(days: int = 30) -> dict:
    import time
    since = int(time.time()) - days * 86400
    charges = stripe.Charge.list(created={"gte": since}, limit=100)
    total = sum(c["amount"] for c in charges.auto_paging_iter() if c["paid"])
    return {"total_cents": total, "total_usd": total / 100, "days": days}
