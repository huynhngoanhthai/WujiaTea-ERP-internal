from odoo import api, fields, models


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    planned_weight = fields.Float(
        string='Planned weight',
        compute='_compute_planned_weight',
        store=True,
        digits='Stock Weight',
        help="Total planned weight of the batch = sum(picking_ids.planned_weight). Used to pick a suitable vehicle.",
    )
    done_weight = fields.Float(
        string='Delivered weight',
        compute='_compute_done_weight',
        store=True,
        digits='Stock Weight',
    )

    @api.depends('picking_ids.planned_weight')
    def _compute_planned_weight(self):
        for batch in self:
            batch.planned_weight = sum(batch.picking_ids.mapped('planned_weight'))

    @api.depends('picking_ids.done_weight')
    def _compute_done_weight(self):
        for batch in self:
            batch.done_weight = sum(batch.picking_ids.mapped('done_weight'))
