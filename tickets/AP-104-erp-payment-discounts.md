# AP-104 · Support payment discounts from the ERP

**Type:** Story · **Priority:** High · **Estimate:** M

## Context

The ERP has started sending `discount_taken` on payments: an early-payment
discount the vendor allowed. A payment's `amount` is still the cash paid;
`discount_taken` also reduces what is owed to the vendor.

## Story

As an AP clerk, I want discounts taken to be reflected in vendor balances, so
that our balances match the ERP.

## Acceptance criteria

- `discount_taken` is imported, stored and shown on the vendor ledger.
- Vendor balances account for it everywhere a balance is shown.
- Payments without `discount_taken` behave as before.
- Tests cover the new behaviour.

## Notes

The ERP data file has not been updated yet. To try it, add
`"discount_taken": 25.00` to the first payment of Pacific Coast Produce
(vendor 1001) in `backend/simulated_erp/data/vendors.json`.
