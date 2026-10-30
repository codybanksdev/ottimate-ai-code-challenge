import React, { useCallback, useEffect, useState } from 'react';
import SortableHeader from './SortableHeader';
import VendorLedger from './VendorLedger';
import { getJson } from './api';
import { formatDate, formatDateTime, formatMoney } from './format';
import { COLUMNS, sortVendors } from './vendorSort';

function VendorList() {
    // null until the first response, so "loading" and "no vendors" are distinct.
    const [vendors, setVendors] = useState(null);
    const [error, setError] = useState(null);
    const [ledgerVendor, setLedgerVendor] = useState(null);
    const [sort, setSort] = useState({ key: 'name', direction: 'asc' });
    // Blank means today. Otherwise balances are as of the close of this day.
    const [asOf, setAsOf] = useState('');
    const closeLedger = useCallback(() => setLedgerVendor(null), []);

    useEffect(() => {
        let ignore = false;
        getJson(`/api/vendors/${asOf ? `?as_of=${asOf}` : ''}`)
            // The date is kept with the rows so the heading always describes
            // the balances on screen.
            .then(data => {
                if (!ignore) {
                    setVendors(data.map(vendor => ({ ...vendor, asOf })));
                    setError(null);
                }
            })
            .catch(error => {
                console.error('Error fetching vendors:', error);
                if (!ignore) setError(error);
            });
        return () => { ignore = true; };
    }, [asOf]);

    // Nothing loaded yet: there is no list to keep showing.
    if (vendors === null) {
        return error
            ? <div role="alert">Error loading vendors: {error.message}</div>
            : <div>Loading vendors...</div>;
    }

    const visibleVendors = sortVendors(vendors, sort);
    // ISO timestamps sort as text; the newest is when the ERP was last read.
    const lastSynced = vendors.map(vendor => vendor.ledger_synced_at).filter(Boolean).sort().pop();
    const shownAsOf = vendors.length > 0 ? vendors[0].asOf : '';
    const totalOwed = vendors.reduce((sum, vendor) => sum + Number(vendor.balance || 0), 0);

    return (
        <div className="vendor-list">
            <p className="sync-status">
                {lastSynced
                    ? `Last synced from the ERP: ${formatDateTime(lastSynced)}.`
                    : 'Ledgers have not been synced from the ERP yet. Run the import (see the README).'}
            </p>
            {vendors.length === 0 ? (
                <p>No vendors found.</p>
            ) : (
                <>
                    <div className="toolbar">
                        <label>
                            Balances as of
                            <input type="date" value={asOf} onChange={event => setAsOf(event.target.value)} />
                        </label>
                        <span>
                            Total owed: <strong className="money">{formatMoney(totalOwed.toFixed(2))}</strong>
                        </span>
                    </div>
                    {/* A later request failed: keep the last list and the date
                        picker on screen so the user can try another date. */}
                    {error && <p role="alert">Error loading vendors: {error.message}</p>}
                    {shownAsOf && (
                        <p className="as-of-note" role="note">
                            Balances are as of {formatDate(shownAsOf)}, not today.
                        </p>
                    )}
                    <table>
                        <caption className="visually-hidden">Vendors and the balance owed to each</caption>
                        <thead>
                            <tr>
                                {COLUMNS.map(column => (
                                    <SortableHeader key={column.key} column={column} sort={sort} onSort={setSort} />
                                ))}
                                <th scope="col">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {visibleVendors.map(vendor => (
                                <tr key={vendor.id}>
                                    <td>{vendor.erp_vendor_id ?? <span title="Not in the ERP">—</span>}</td>
                                    <td>{vendor.name}</td>
                                    <td>{vendor.payment_terms_days === null ? '' : `Net ${vendor.payment_terms_days}`}</td>
                                    <td className="money">
                                        {vendor.balance === null
                                            ? <span title="Not in the ERP and no ledger entries">—</span>
                                            : formatMoney(vendor.balance)}
                                    </td>
                                    <td>
                                        <button
                                            aria-label={`View ledger for ${vendor.name}`}
                                            onClick={() => setLedgerVendor(vendor)}
                                        >
                                            View Ledger
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </>
            )}
            {ledgerVendor && <VendorLedger vendor={ledgerVendor} onClose={closeLedger} />}
        </div>
    );
}

export default VendorList;
