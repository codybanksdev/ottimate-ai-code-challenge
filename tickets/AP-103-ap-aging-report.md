# AP-103 · AP aging report

**Type:** Story · **Priority:** High · **Estimate:** M

## Context

At month end the AP team reviews what is past due so they can plan payment
runs and chase disputes.

## Story

As an AP manager, I want an aging report as of a date I choose, so that I can
see how overdue our open invoices are by vendor.

## Acceptance criteria

- For each vendor, the report shows open invoice amounts in these buckets,
  based on days past the invoice due date: current, 1–30, 31–60, 61–90 and
  91+.
- The as-of date can be chosen.
- It is available from the API and in the UI, with totals.
- Tests cover the new behaviour.
