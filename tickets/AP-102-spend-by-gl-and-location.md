# AP-102 · Spend by GL account and location

**Type:** Story · **Priority:** Medium · **Estimate:** S

## Context

The controller reviews food and operating costs each month, broken down by GL
account (the expense account an invoice is coded to) and by restaurant
location.

## Story

As the controller, I want to see spend by GL account and location for a
period I choose, so that I can compare locations and spot unusual costs.

## Acceptance criteria

- A report shows spend for each GL account and location, with totals, for a
  chosen start and end date.
- It is available from the API and in the UI.
- Tests cover the new behaviour.

## Notes

The ERP's accounting rules are in `backend/simulated_erp/API_SPEC.md`.
