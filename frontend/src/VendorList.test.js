import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import VendorList from './VendorList';

const SYNCED = '2026-10-02T15:30:00Z';
const vendors = [
    { id: 1, erp_vendor_id: null, name: 'Coastal Ice Co.', payment_terms_days: 15, balance: null, ledger_synced_at: null },
    { id: 2, erp_vendor_id: 1004, name: 'Valley Creamery', payment_terms_days: 15, balance: '350.00', ledger_synced_at: SYNCED },
    { id: 3, erp_vendor_id: 1011, name: 'Sunrise Bakery Wholesale', payment_terms_days: 7, balance: '-1800.00', ledger_synced_at: SYNCED },
];

const ledger = {
    vendor: vendors[1], start: null, end: null, opening_balance: '0.00',
    total_invoiced: '1000.00', total_credits: '50.00', total_paid: '600.00', balance: '350.00',
    removed_entries: [],
    lines: [
        { id: 1, erp_id: 'E-1', type: 'invoice', date: '2026-01-05', document_number: 'VC-1', description: 'Dairy order', amount: '1000.00', due_date: '2026-01-20', gl_account_code: '5000', gl_account_name: 'Food Cost', location: 'Mission', applies_to: [], running_balance: '1000.00' },
        { id: 2, erp_id: 'E-2', type: 'credit_memo', date: '2026-01-07', document_number: 'CM-1', description: 'Spoiled product credit', amount: '50.00', due_date: null, gl_account_code: '5000', gl_account_name: 'Food Cost', location: 'Mission', applies_to: [], running_balance: '950.00' },
        { id: 3, erp_id: 'E-3', type: 'payment', date: '2026-01-21', document_number: 'CHK-1', description: 'Check CHK-1', amount: '600.00', due_date: null, gl_account_code: '', gl_account_name: '', location: '', applies_to: [], running_balance: '350.00' },
    ],
};

function mockApi(routes) {
    jest.spyOn(global, 'fetch').mockImplementation(url => {
        const body = routes[url];
        return Promise.resolve(
            body === undefined
                ? { ok: false, status: 500, json: () => Promise.resolve({}) }
                : { ok: true, status: 200, json: () => Promise.resolve(body) }
        );
    });
}

function rowTexts(table) {
    return within(table).getAllByRole('row').slice(1).map(row =>
        within(row).getAllByRole('cell').map(cell => cell.textContent));
}

beforeEach(() => {
    global.fetch = global.fetch || (() => {});
    jest.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
    jest.restoreAllMocks();
});

test('lists vendors with their balance, and a dash for a vendor not in the ERP', async () => {
    mockApi({ '/api/vendors/': vendors });
    render(<VendorList />);

    const table = await screen.findByRole('table');

    expect(rowTexts(table).map(cells => cells.slice(0, 4))).toEqual([
        ['—', 'Coastal Ice Co.', 'Net 15', '—'],
        ['1011', 'Sunrise Bakery Wholesale', 'Net 7', '($1,800.00)'],
        ['1004', 'Valley Creamery', 'Net 15', '$350.00'],
    ]);
    expect(screen.getByText(/Total owed/)).toHaveTextContent('($1,450.00)');
});

test('sorting by balance puts vendors with no balance last', async () => {
    mockApi({ '/api/vendors/': vendors });
    render(<VendorList />);
    await screen.findByRole('table');

    userEvent.click(screen.getByRole('button', { name: /Balance owed/ }));
    userEvent.click(screen.getByRole('button', { name: /Balance owed/ }));

    expect(rowTexts(screen.getByRole('table')).map(cells => cells[1])).toEqual([
        'Valley Creamery', 'Sunrise Bakery Wholesale', 'Coastal Ice Co.',
    ]);
});

test('View Ledger opens the vendor ledger with a running balance', async () => {
    mockApi({ '/api/vendors/': vendors, '/api/vendors/2/ledger/': ledger });
    render(<VendorList />);
    await screen.findByRole('table');

    userEvent.click(screen.getByRole('button', { name: 'View ledger for Valley Creamery' }));

    const dialog = await screen.findByRole('dialog', { name: 'Ledger: Valley Creamery' });
    const table = await within(dialog).findByRole('table');
    expect(rowTexts(table).map(cells => [cells[1], cells[5], cells[6], cells[7]])).toEqual([
        ['Invoice', '$1,000.00', '', '$1,000.00'],
        ['Credit memo', '', '$50.00', '$950.00'],
        ['Payment', '', '$600.00', '$350.00'],
    ]);
    expect(within(dialog).getByText('Balance owed').nextSibling).toHaveTextContent('$350.00');
});

test('a date range asks the API for that period and shows the opening balance', async () => {
    const ranged = { ...ledger, start: '2026-01-06', opening_balance: '1000.00', lines: ledger.lines.slice(1) };
    mockApi({
        '/api/vendors/': vendors,
        '/api/vendors/2/ledger/': ledger,
        '/api/vendors/2/ledger/?start=2026-01-06': ranged,
    });
    render(<VendorList />);
    await screen.findByRole('table');
    userEvent.click(screen.getByRole('button', { name: 'View ledger for Valley Creamery' }));
    const dialog = await screen.findByRole('dialog');
    await within(dialog).findByRole('table');

    userEvent.type(within(dialog).getByLabelText('From'), '2026-01-06');

    await waitFor(() => expect(within(dialog).getByText('Opening balance')).toBeInTheDocument());
    expect(within(dialog).getByText('Invoiced in period')).toBeInTheDocument();
});

test('a ledger opened from balances as of a past date ends on that date', async () => {
    const asOf = { ...ledger, end: '2026-01-10', lines: ledger.lines.slice(0, 2), balance: '950.00' };
    mockApi({
        '/api/vendors/': vendors,
        '/api/vendors/?as_of=2026-01-10': vendors,
        '/api/vendors/2/ledger/?end=2026-01-10': asOf,
    });
    render(<VendorList />);
    await screen.findByRole('table');

    userEvent.type(screen.getByLabelText('Balances as of'), '2026-01-10');
    await screen.findByRole('note');
    userEvent.click(screen.getByRole('button', { name: 'View ledger for Valley Creamery' }));

    const dialog = await screen.findByRole('dialog');
    expect(await within(dialog).findByText('Balance as of 01/10/2026')).toBeInTheDocument();
    expect(within(dialog).getByLabelText('To')).toHaveValue('2026-01-10');
});

test('a vendor not in the ERP with no entries shows an unknown balance, not paid in full', async () => {
    const empty = {
        vendor: vendors[0], start: null, end: null, opening_balance: '0.00', total_invoiced: '0.00',
        total_credits: '0.00', total_paid: '0.00', balance: '0.00', lines: [], removed_entries: [],
    };
    mockApi({ '/api/vendors/': vendors, '/api/vendors/1/ledger/': empty });
    render(<VendorList />);
    await screen.findByRole('table');

    userEvent.click(screen.getByRole('button', { name: 'View ledger for Coastal Ice Co.' }));

    const dialog = await screen.findByRole('dialog');
    expect(await within(dialog).findByText('Balance (no activity)')).toBeInTheDocument();
    expect(within(dialog).getByText('Balance (no activity)').nextSibling).toHaveTextContent('—');
    expect(within(dialog).queryByText('Paid in full')).not.toBeInTheDocument();
});

test('shows an error when the vendors cannot be loaded', async () => {
    mockApi({});
    render(<VendorList />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Error loading vendors');
});
