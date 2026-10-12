from odoo import api, fields, models


class WujiaFleetManagement(models.Model):
    _inherit = 'wujia.fleet.management'

    current_batch_id = fields.Many2one(
        'stock.picking.batch',
        string='Current batch',
        compute='_compute_current_batch',
        store=False,
        help='Batch currently assigned to this vehicle (state not done/cancel). Computed live, not stored.',
    )
    current_batch_name = fields.Char(
        related='current_batch_id.name',
        readonly=True,
    )

    @api.depends('vehicle_status')
    def _compute_current_batch(self):
        Batch = self.env['stock.picking.batch']
        for rec in self:
            if not rec.id:
                rec.current_batch_id = False
                continue
            rec.current_batch_id = Batch.search([
                ('vehicle_id', '=', rec.id),
                ('state', 'not in', ('done', 'cancel')),
            ], order='scheduled_date desc, id desc', limit=1)

    def action_view_current_batch(self):
        self.ensure_one()
        if not self.current_batch_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking.batch',
            'res_id': self.current_batch_id.id,
            'view_mode': 'form',
        }
