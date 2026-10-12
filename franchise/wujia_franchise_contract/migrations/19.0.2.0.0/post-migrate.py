from odoo import SUPERUSER_ID, api

FIELDS = ('current_contract_id', 'franchise_start_date', 'franchise_end_date')


def migrate(cr, version):
    """Stores cache the current contract and its dates; the new state rules can change which one wins."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    stores = env['wujia.franchise.management'].with_context(active_test=False).search([])
    for fname in FIELDS:
        env.add_to_compute(stores._fields[fname], stores)
        stores.flush_recordset([fname])
