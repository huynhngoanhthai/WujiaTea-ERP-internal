# -*- encoding: utf-8 -*-
##############################################################################
#
# ERP Heritage
# Copyright (C) 2026 (https://www.erpheritage.com.au/)
#
##############################################################################
"""
Compatibility shim: ensure required upstream fields on res.partner pick
up their declared defaults when the partner is auto-created via cascade
(e.g. res.users / res.company creation paths). Some Enterprise modules
override the low-level _create such that field defaults declared on
inherited modules are not always applied to cascade-created partners,
producing NOT NULL violations on columns the upstream module marked
required.

Known offenders:
* group_rfq  (purchase_stock) - default 'default'
* group_on   (purchase_stock) - default 'default'

The Python-level setdefault covers direct calls. A versioned migration applies
the optional table defaults once for databases affected by older upstream
overrides; registry initialization itself stays read-only.

Both layers are no-ops when the offending field/column is absent.
"""

from odoo import api, models


# Required upstream fields that ship with `default='default'` and that
# Enterprise's _create override sometimes strips. New entries can be
# added here as the matrix grows; the shim handles each generically.
_REQUIRED_PARTNER_DEFAULTS = (
    ('group_rfq', 'default'),
    ('group_on', 'default'),
)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # EH_LEGACY_CONTACT_STATISTICS_COMPAT_START
    @api.depends_context('uid', 'allowed_company_ids', 'company')
    def _compute_application_statistics(self):
        """Partition Odoo 19's native statistics cache by actor and company."""
        return super()._compute_application_statistics()
    # EH_LEGACY_CONTACT_STATISTICS_COMPAT_END

    @api.model_create_multi
    def create(self, vals_list):
        for column, default in _REQUIRED_PARTNER_DEFAULTS:
            if column in self._fields:
                for vals in vals_list:
                    vals.setdefault(column, default)
        return super().create(vals_list)
