# Simulated ERP integration API

A stand-in for the customer's ERP (accounting system). It is served by the
same Django server as the app, from the fixed file `data/vendors.json`, so
the exercise runs offline. Treat it as an external, read-only system.

Base URL: `http://127.0.0.1:8009/simulated-erp-api/` (the `ERP_API_URL` setting)

## Vendors

**Endpoint:** `GET /vendors/`

| Parameter | Description |
|-----------|-------------|
| includeLedgers | When `true`, each vendor includes its full `ledger`. Without it there is no `ledger` key. |

Returns an array of vendors. There is no pagination.

```json
[
  {
    "vendor_id": 1004,
    "name": "Valley Creamery",
    "payment_terms_days": 15,
    "ledger": [
      {"id": "E-00101", "type": "invoice", "date": "2026-01-05", "document_number": "VC-2361",
       "amount": 1882.43, "description": "Dairy order", "due_date": "2026-01-20",
       "gl_account": {"code": "5000", "name": "Food Cost"}, "location": "Mission"},
      {"id": "E-00140", "type": "payment", "date": "2026-01-21", "document_number": "CHK-30112",
       "amount": 1882.43, "description": "Check CHK-30112",
       "applies_to": [{"invoice_number": "VC-2361", "amount": 1882.43}]}
    ]
  }
]
```

### Vendor fields

| Field | Description |
|-------|-------------|
| vendor_id | The vendor's identifier in the ERP (integer). Unrelated to any local id. |
| name | Vendor name |
| payment_terms_days | Days from invoice date to due date (e.g. 30 for Net 30) |

### Ledger entry fields

| Field | Present on | Description |
|-------|-----------|-------------|
| id | all | Entry identifier (string), unique across the ERP |
| type | all | `invoice`, `credit_memo` or `payment` |
| date | all | Entry date, `YYYY-MM-DD` |
| document_number | all | Invoice number, credit memo number, or payment reference |
| amount | all | Dollar amount with cents, as a JSON number |
| description | all | Free text |
| due_date | invoice | `YYYY-MM-DD` |
| gl_account | invoice, credit_memo | `{"code", "name"}`: the expense account it is coded to |
| location | invoice, credit_memo | The restaurant location it is coded to |
| applies_to | payment, credit_memo | `[{"invoice_number", "amount"}]`: the invoices it settles. Empty when unapplied. |

## Accounting rules

- **The balance owed to a vendor is invoices − credit memos − payments.**
- `type` gives the direction. Amounts are normally positive.
- A **negative payment** is a void of an earlier payment and adds back to the
  balance. Its `applies_to` amounts are negative too.
- A **negative credit memo** reverses an earlier credit memo.
- Ledgers are complete histories, starting from a zero balance.
- Entries are mostly, but not guaranteed to be, in date order.
- All amounts are USD.
