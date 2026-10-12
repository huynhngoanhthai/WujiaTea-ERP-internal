from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    planned_weight = fields.Float(
        string='Planned weight',
        compute='_compute_planned_weight',
        store=True,
        digits='Stock Weight',
        help="Total planned weight of the delivery order = sum(move_ids.planned_weight). This is the authoritative source for planning batches/trips.",
    )
    done_weight = fields.Float(
        string='Delivered weight',
        compute='_compute_done_weight',
        store=True,
        digits='Stock Weight',
    )

    @api.depends('move_ids.planned_weight')
    def _compute_planned_weight(self):
        for pick in self:
            pick.planned_weight = sum(pick.move_ids.mapped('planned_weight'))

    @api.depends('move_ids.done_weight')
    def _compute_done_weight(self):
        for pick in self:
            pick.done_weight = sum(pick.move_ids.mapped('done_weight'))
