// Sorting for the vendor table, kept out of the component so the rules can
// be tested without rendering anything.

export const COLUMNS = [
    { key: 'erp_vendor_id', label: 'ERP ID', numeric: true },
    { key: 'name', label: 'Vendor' },
    { key: 'payment_terms_days', label: 'Terms', numeric: true },
    { key: 'balance', label: 'Balance owed', numeric: true, money: true },
];

// Click a new column: ascending. Click the same column again: flip it.
export function nextSort(sort, key) {
    if (sort.key !== key) return { key, direction: 'asc' };
    return { key, direction: sort.direction === 'asc' ? 'desc' : 'asc' };
}

// Missing values (no ERP id, no balance) always sort last, in either
// direction, so they never crowd the top of the table.
export function sortVendors(vendors, { key, direction }) {
    const column = COLUMNS.find(c => c.key === key);
    const factor = direction === 'asc' ? 1 : -1;
    return [...vendors].sort((a, b) => {
        const x = a[key];
        const y = b[key];
        if (x === null || x === undefined) return y === null || y === undefined ? 0 : 1;
        if (y === null || y === undefined) return -1;
        const order = column && column.numeric
            ? Number(x) - Number(y)
            : String(x).localeCompare(String(y), undefined, { sensitivity: 'base' });
        return order * factor || a.id - b.id;
    });
}
