from odoo import api, fields, models, tools


class StockLocation(models.Model):
    _inherit = 'stock.location'

    is_export = fields.Boolean(
        string='Export Location',
        default=False,
        help='Check this box if this location is used for export/franchise delivery fulfillment.',
    )

    def _auto_init(self):
        super()._auto_init()
        tools.create_index(
            self._cr,
            'idx_stock_location_is_export',
            self._table,
            ['is_export'],
        )
