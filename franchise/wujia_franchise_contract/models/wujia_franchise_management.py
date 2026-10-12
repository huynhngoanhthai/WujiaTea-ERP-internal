import logging
from datetime import timedelta
from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class WujiaFranchiseManagement(models.Model):
    _inherit = 'wujia.franchise.management'

    contract_ids = fields.One2many(
        'wujia.franchise.contract',
        'franchise_id',
        string='Franchise Contracts',
    )
    contract_count = fields.Integer(
        string='Contract Count',
        compute='_compute_contract_count',
    )
    current_contract_id = fields.Many2one(
        'wujia.franchise.contract',
        string='Current Contract',
        compute='_compute_current_contract',
        store=True,
    )
    franchise_start_date = fields.Date(
        string='Franchise Start Date',
        compute='_compute_contract_dates',
        store=True,
        readonly=True,
        required=False,
        tracking=True,
    )
    franchise_end_date = fields.Date(
        string='Franchise End Date',
        compute='_compute_contract_dates',
        store=True,
        readonly=True,
        required=False,
        tracking=True,
    )

    @api.depends('contract_ids', 'contract_ids.active')
    def _compute_contract_count(self):
        for rec in self:
            rec.contract_count = len(rec.contract_ids)

    @api.depends('contract_ids.start_date', 'contract_ids.end_date',
                 'contract_ids.state', 'contract_ids.active')
    def _compute_current_contract(self):
        for rec in self:
            live = rec.contract_ids.filtered(lambda c: c.state != 'cancelled')
            effective = live.filtered(lambda c: c.state == 'effective')
            pool = effective or live
            rec.current_contract_id = pool.sorted(
                key=lambda c: (c.start_date or fields.Date.today(), c.id), reverse=True,
            )[:1]

    @api.depends('current_contract_id.start_date', 'current_contract_id.end_date')
    def _compute_contract_dates(self):
        for rec in self:
            rec.franchise_start_date = rec.current_contract_id.start_date or False
            rec.franchise_end_date = rec.current_contract_id.end_date or False

    def action_view_contracts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contracts of %s', self.display_name),
            'res_model': 'wujia.franchise.contract',
            'view_mode': 'list,form',
            'domain': [('franchise_id', '=', self.id)],
            'context': {'default_franchise_id': self.id},
        }

    def _wj_ensure_contract(self, start_date, end_date, note=None):
        """Single entry point for every flow that used to write the two legacy date fields."""
        self.ensure_one()
        if not start_date and not end_date:
            return self.env['wujia.franchise.contract']
        if self.contract_ids:
            return self.env['wujia.franchise.contract']
        start_date = fields.Date.to_date(start_date)
        end_date = fields.Date.to_date(end_date)
        start = start_date or fields.Date.context_today(self)
        end = end_date or (start + timedelta(days=365))
        if end < start:
            end = start + timedelta(days=365)
        return self.env['wujia.franchise.contract'].sudo().create({
            'franchise_id': self.id,
            'start_date': start,
            'end_date': end,
            'note': note,
        })

    @api.model
    def _migrate_legacy_franchise_contracts(self):
        """Turn each store's legacy date pair into at most one contract; safe to re-run."""
        # Read the raw columns FIRST: installing this module turns both dates into stored
        # computed fields, and any ORM call may flush that compute over the legacy values.
        self.env.cr.execute("""
            SELECT id, franchise_start_date, franchise_end_date
              FROM wujia_franchise_management
             WHERE franchise_start_date IS NOT NULL OR franchise_end_date IS NOT NULL
        """)
        legacy = self.env.cr.fetchall()
        Param = self.env['ir.config_parameter'].sudo()
        if Param.get_param('wujia_franchise_contract.legacy_migrated'):
            return 0
        created = 0
        note = _('Migrated from store master data.')
        for store_id, legacy_start, legacy_end in legacy:
            store = self.browse(store_id).with_context(active_test=False)
            if not store.exists():
                continue
            if store._wj_ensure_contract(legacy_start, legacy_end, note=note):
                created += 1
        Param.set_param('wujia_franchise_contract.legacy_migrated', 'True')
        _logger.info("Franchise contract migration created %s contracts.", created)
        return created
