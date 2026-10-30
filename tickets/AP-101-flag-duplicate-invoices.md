# AP-101 · Flag possible duplicate invoices

**Type:** Story · **Priority:** Medium · **Estimate:** S

## Context

AP clerks sometimes enter the same vendor invoice into the ERP twice. If
nobody notices, the second copy gets paid as well.

## Story

As an AP clerk, I want invoices that look like duplicates to be flagged, so
that I can check them before they are paid.

## Acceptance criteria

- An invoice is a possible duplicate when another invoice for the same vendor
  has the same invoice number.
- The vendor ledger API marks possible duplicates.
- The vendor ledger in the UI shows the flag on those invoices.
- Balances do not change; flagging is for review only.
- Tests cover the new behaviour.

## Out of scope

Automatically voiding or merging duplicates.
