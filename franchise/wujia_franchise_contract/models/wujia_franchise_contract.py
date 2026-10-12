from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class WujiaFranchiseContract(models.Model):
    _name = 'wujia.franchise.contract'
    _description = 'Franchise Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, id desc'

    name = fields.Char(
        string='Contract Number',
        required=True,
        tracking=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('wujia.franchise.contract') or '/',
        help='Franchise contract number (e.g. FC/2026/0001).',
    )
    franchise_id = fields.Many2one(
        'wujia.franchise.management',
        string='Franchise Store',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    start_date = fields.Date(
        string='Start Date',
        required=True,
        index=True,
        tracking=True,
        default=fields.Date.context_today,
    )
    end_date = fields.Date(
        string='End Date',
        required=True,
        index=True,
        tracking=True,
    )
    is_cancelled = fields.Boolean(
        string='Cancelled',
        default=False,
        tracking=True,
        help='Only manual lever on the contract lifecycle; every other state follows the dates.',
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('effective', 'Effective'),
            ('expired', 'Expired'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        compute='_compute_state',
        store=True,
        index=True,
        readonly=True,
        tracking=True,
    )
    note = fields.Text(string='Internal Note', tracking=True)
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Contract Attachments',
        help='Scanned contract files or addendums.',
    )

    active = fields.Boolean(default=True)

    @api.depends('is_cancelled', 'start_date', 'end_date')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.is_cancelled:
                rec.state = 'cancelled'
            elif not rec.start_date or not rec.end_date:
                rec.state = 'draft'
            elif today < rec.start_date:
                rec.state = 'draft'
            elif today > rec.end_date:
                rec.state = 'expired'
            else:
                rec.state = 'effective'

    def action_cancel(self):
        self.is_cancelled = True

    def action_restore(self):
        self.is_cancelled = False

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date < rec.start_date:
                raise ValidationError(_("End date must be greater than or equal to start date."))

    @api.constrains('franchise_id', 'start_date', 'end_date', 'is_cancelled', 'active')
    def _check_no_overlap(self):
        # Two closed ranges overlap iff start_old <= end_new AND end_old >= start_new.
        for rec in self:
            if not rec.franchise_id or not rec.start_date or not rec.end_date:
                continue
            if rec.is_cancelled or not rec.active:
                continue
            clash = self.search(
                [
                    ('id', '!=', rec.id),
                    ('franchise_id', '=', rec.franchise_id.id),
                    ('is_cancelled', '=', False),
                    ('active', '=', True),
                    ('start_date', '<=', rec.end_date),
                    ('end_date', '>=', rec.start_date),
                ],
                limit=1,
            )
            if clash:
                raise ValidationError(_(
                    "Contract date range (%(start)s to %(end)s) overlaps with contract %(other)s "
                    "of store '%(store)s'.",
                    start=rec.start_date, end=rec.end_date,
                    other=clash.name, store=rec.franchise_id.display_name,
                ))

    def unlink(self):
        for rec in self:
            if rec.state in ('effective', 'expired'):
                raise UserError(_(
                    "Active or historical contracts (%s) cannot be deleted. Please cancel or archive them instead."
                ) % rec.name)
        return super().unlink()

    @api.model
    def _cron_refresh_state(self):
        """Daily: only contracts whose date boundary has just been crossed need a recompute."""
        today = fields.Date.context_today(self)
        stale = self.with_context(active_test=False).search([
            ('is_cancelled', '=', False),
            '|',
            '&', ('state', '=', 'draft'), ('start_date', '<=', today),
            '&', ('state', '=', 'effective'), ('end_date', '<', today),
        ])
        if stale:
            self.env.add_to_compute(self._fields['state'], stale)
            stale.flush_recordset(['state'])
        return len(stale)
