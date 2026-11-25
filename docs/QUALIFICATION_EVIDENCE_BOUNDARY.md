# Qualification and payment evidence boundary

Previous NEXUS acquisition code automatically created Stripe Products, Prices,
and Payment Links for scored leads, then inserted a `conversions` row with
`converted_at` before a paid Stripe event was observed. Those rows were not
evidence of revenue.

This change:
- Marks qualified leads as `qualified` without making an external charge/checkout.
- Logs `qualified_pending_approval` with no checkout or outbound assertion.
- Does not create `conversions` rows or count unpaid leads as customers.
- Leaves verification of provider-paid events and fulfillment to the existing
  approval-bound revenue infrastructure, not this scoring path.

## Outstanding work

The SendGrid adapter still has a direct mail-send path without a checked
`policy_decision_id`. Keep this branch draft and do not enable unattended
outbound until an authoritative approval-verification gate is integrated
and regression tested at both plain-message and template-message boundaries.

Existing historical `conversions` rows require separate provider reconciliation.
Do not delete or relabel customer data without evidence.
