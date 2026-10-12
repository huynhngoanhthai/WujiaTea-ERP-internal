from odoo import fields, models


class WujiaFleetPricelistLine(models.Model):
    _name = 'wujia.fleet.pricelist.line'
    _description = 'Wujia Fleet Pricelist Line'
    _order = 'pricelist_id, sequence, id'

    pricelist_id = fields.Many2one(
        'wujia.fleet.pricelist',
        string='Pricelist',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)

    area_ids = fields.Many2many(
        'res.area',
        'wujia_fleet_pricelist_line_area_rel',
        'line_id',
        'area_id',
        string='Applicable areas',
        required=True,
        help="A price line can cover several areas — it matches when the area of the picking is in this list.",
    )
    price = fields.Monetary(
        string='Shipping price',
        required=True,
        currency_field='currency_id',
        default=0.0,
    )
    drop_fee = fields.Monetary(
        string='Drop fee',
        currency_field='currency_id',
        default=0.0,
    )
    currency_id = fields.Many2one(
        related='pricelist_id.currency_id',
        store=True,
        readonly=True,
    )
    active = fields.Boolean(default=True)
    note = fields.Char(string='Notes')
