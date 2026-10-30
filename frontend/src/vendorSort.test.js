import { nextSort, sortVendors } from './vendorSort';

const vendors = [
    { id: 1, name: 'beta', erp_vendor_id: 2, balance: '10.00' },
    { id: 2, name: 'Alpha', erp_vendor_id: null, balance: null },
    { id: 3, name: 'gamma', erp_vendor_id: 1, balance: '-5.00' },
];

test('sorts names without regard to case', () => {
    expect(sortVendors(vendors, { key: 'name', direction: 'asc' }).map(v => v.id)).toEqual([2, 1, 3]);
});

test('sorts money as numbers and keeps missing values last in both directions', () => {
    expect(sortVendors(vendors, { key: 'balance', direction: 'asc' }).map(v => v.id)).toEqual([3, 1, 2]);
    expect(sortVendors(vendors, { key: 'balance', direction: 'desc' }).map(v => v.id)).toEqual([1, 3, 2]);
});

test('clicking the same column flips the direction', () => {
    expect(nextSort({ key: 'name', direction: 'asc' }, 'name')).toEqual({ key: 'name', direction: 'desc' });
    expect(nextSort({ key: 'name', direction: 'desc' }, 'balance')).toEqual({ key: 'balance', direction: 'asc' });
});
