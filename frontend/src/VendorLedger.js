import React, { useEffect, useState } from 'react';
import { getJson } from './api';
import { formatDate, formatDateTime, formatMoney } from './format';
import { useDialog } from './useDialog';

const TYPE_LABELS = { invoice: 'Invoice', credit_memo: 'Credit memo', payment: 'Payment' };
const ALL_DATES = { start: '', end: '' };

// Nothing on file at all: no entries, no period that could be hiding them,
// and nothing that was removed from the ERP.
function isEmpty(ledger) {
    return ledger.lines.length === 0 && !ledger.start && !ledger.end
        && ledger.removed_entries.length === 0;
}

function balanceLabel(ledger) {
    if (ledger.end) return `Balance as of ${formatDate(ledger.end)}`;
    // An empty ledger is not "paid in full": nothing was ever billed, or the
    // vendor has no ERP record to import from.
    if (isEmpty(ledger)) return 'Balance (no activity)';
    const value = Number(ledger.balance);
    if (value > 0) return 'Balance owed';
    if (value < 0) return 'Vendor credit';
    return 'Paid in full';
}

function rangeQuery({ start, end }) {
    const params = new URLSearchParams();
    if (start) params.set('start', start);
    if (end) params.set('end', end);
    const query = params.toString();
    return query ? `?${query}` : '';
}

// Invoices increase what is owed; credit memos and payments reduce it. The
// amount keeps the ERP's sign, so a void shows as a negative payment.
function Amounts({ line }) {
    const increases = line.type === 'invoice';
    return (
        <>
            <td className="money">{increases ? formatMoney(line.amount) : ''}</td>
            <td className="money">{increases ? '' : formatMoney(line.amount)}</td>
        </>
    );
}

function VendorLedger({ vendor, onClose }) {
    const [ledger, setLedger] = useState(null);
    const [error, setError] = useState(null);
    // Opened from a list showing balances as of a past date, the ledger
    // starts at that same date so the two agree.
    const [range, setRange] = useState(vendor.asOf ? { start: '', end: vendor.asOf } : ALL_DATES);
    const { dialogRef, headingRef } = useDialog(onClose);
    const query = rangeQuery(range);

    useEffect(() => {
        let ignore = false;
        getJson(`/api/vendors/${vendor.id}/ledger/${query}`)
            .then(data => {
                if (!ignore) {
                    setLedger(data);
                    setError(null);
                }
            })
            .catch(error => {
                console.error('Error fetching ledger:', error);
                if (!ignore) setError(error);
            });
        // Ignore a response that arrives after the ledger was closed or the
        // range changed again.
        return () => { ignore = true; };
    }, [vendor.id, query]);

    const setRangeField = name => event => setRange({ ...range, [name]: event.target.value });
    // Labels follow the response on screen, not the range just asked for.
    const ranged = Boolean(ledger && (ledger.start || ledger.end));
    // Not in the ERP and nothing on file: the balance is unknown, as on the
    // vendor list, not $0.00.
    const unknownBalance = Boolean(ledger && isEmpty(ledger) && ledger.vendor.erp_vendor_id === null);

    return (
        <div className="ledger-backdrop" onClick={onClose}>
            <div
                className="ledger"
                ref={dialogRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby="ledger-title"
                onClick={event => event.stopPropagation()}
            >
                <div className="ledger-header">
                    <h2 id="ledger-title" tabIndex={-1} ref={headingRef}>Ledger: {vendor.name}</h2>
                    <button onClick={onClose}>Close</button>
                </div>
                <p className="ledger-meta">
                    {vendor.erp_vendor_id === null ? 'Not in the ERP' : `ERP vendor ID ${vendor.erp_vendor_id}`}
                    {vendor.payment_terms_days !== null && ` · Net ${vendor.payment_terms_days}`}
                    {ledger && ledger.vendor.ledger_synced_at
                        && ` · Synced ${formatDateTime(ledger.vendor.ledger_synced_at)}`}
                </p>

                {error && <p role="alert">Error loading ledger: {error.message}</p>}
                {!error && !ledger && <p>Loading ledger...</p>}
                {ledger && (
                    <>
                        <div className="toolbar">
                            <label>
                                From
                                <input type="date" value={range.start} max={range.end || undefined} onChange={setRangeField('start')} />
                            </label>
                            <label>
                                To
                                <input type="date" value={range.end} min={range.start || undefined} onChange={setRangeField('end')} />
                            </label>
                            <button onClick={() => setRange(ALL_DATES)} disabled={!query}>All dates</button>
                        </div>
                        <dl className="ledger-summary">
                            <div>
                                <dt>{ranged ? 'Invoiced in period' : 'Invoiced'}</dt>
                                <dd>{formatMoney(ledger.total_invoiced)}</dd>
                            </div>
                            <div>
                                <dt>{ranged ? 'Credits in period' : 'Credits'}</dt>
                                <dd>{formatMoney(ledger.total_credits)}</dd>
                            </div>
                            <div>
                                <dt>{ranged ? 'Paid in period' : 'Paid'}</dt>
                                <dd>{formatMoney(ledger.total_paid)}</dd>
                            </div>
                            <div className="ledger-balance">
                                <dt>{balanceLabel(ledger)}</dt>
                                <dd>{unknownBalance ? '—' : formatMoney(ledger.balance)}</dd>
                            </div>
                        </dl>
                        {isEmpty(ledger) ? (
                            <p>
                                No ledger entries for this vendor.
                                {ledger.vendor.erp_vendor_id === null && ' This vendor is not linked to an ERP record.'}
                            </p>
                        ) : (
                            <div className="ledger-table-scroll">
                                <table>
                                    <caption className="visually-hidden">
                                        Ledger entries for {vendor.name}, oldest first, with running balance
                                    </caption>
                                    <thead>
                                        <tr>
                                            <th scope="col">Date</th>
                                            <th scope="col">Type</th>
                                            <th scope="col">Document</th>
                                            <th scope="col">Description</th>
                                            <th scope="col">Due</th>
                                            <th scope="col" className="money">Invoiced</th>
                                            <th scope="col" className="money">Paid / credited</th>
                                            <th scope="col" className="money">Balance</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {ledger.start && (
                                            <tr className="opening-balance">
                                                <td>{formatDate(ledger.start)}</td>
                                                <td colSpan={6}>Opening balance</td>
                                                <td className="money">{formatMoney(ledger.opening_balance)}</td>
                                            </tr>
                                        )}
                                        {ledger.lines.map(line => (
                                            <tr key={line.id}>
                                                <td>{formatDate(line.date)}</td>
                                                <td>{TYPE_LABELS[line.type] || line.type}</td>
                                                <td>{line.document_number}</td>
                                                <td>
                                                    {line.description}
                                                    {line.gl_account_code && (
                                                        <span className="detail">
                                                            {line.gl_account_code} {line.gl_account_name} · {line.location}
                                                        </span>
                                                    )}
                                                </td>
                                                <td>{line.due_date ? formatDate(line.due_date) : ''}</td>
                                                <Amounts line={line} />
                                                <td className="money">{formatMoney(line.running_balance)}</td>
                                            </tr>
                                        ))}
                                        {ledger.lines.length === 0 && (
                                            <tr>
                                                <td colSpan={8}>No entries in this period.</td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        )}
                        {ledger.removed_entries.length > 0 && (
                            <details className="ledger-section">
                                <summary>Removed from the ERP ({ledger.removed_entries.length})</summary>
                                <p>These entries were imported and later disappeared from the ERP. They are not part of the balance.</p>
                                <ul>
                                    {ledger.removed_entries.map(entry => (
                                        <li key={entry.id}>
                                            {formatDate(entry.date)} {TYPE_LABELS[entry.type] || entry.type} {entry.document_number}{' '}
                                            {formatMoney(entry.amount)}, removed {formatDateTime(entry.removed_from_erp_at)}
                                        </li>
                                    ))}
                                </ul>
                            </details>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}

export default VendorLedger;
