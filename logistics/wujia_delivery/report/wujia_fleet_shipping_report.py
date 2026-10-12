from odoo import fields, models, tools


class WujiaFleetShippingReport(models.Model):
    _name = 'wujia.fleet.shipping.report'
    _description = 'Cost report by carrier (per batch)'
    _auto = False
    _order = 'report_date desc, batch_id'

    report_date = fields.Date(string='Report date', readonly=True)
    batch_id = fields.Many2one('stock.picking.batch', string='Batch', readonly=True)
    vehicle_id = fields.Many2one('wujia.fleet.management', string='Vehicle', readonly=True)
    provider_id = fields.Many2one('wujia.fleet.provider', string='Carrier', readonly=True)
    fleet_type_id = fields.Many2one('wujia.fleet.type', string='Vehicle type', readonly=True)
    picking_count = fields.Integer(string='Delivery order count', readonly=True)
    franchise_count = fields.Integer(string='Store count', readonly=True)
    planned_weight = fields.Float(string='Planned weight (report)', readonly=True, digits='Stock Weight')
    done_weight = fields.Float(string='Actual shipped weight', readonly=True, digits='Stock Weight')
    capacity_usage_percent = fields.Float(string='Payload usage %', readonly=True, digits=(8, 2))
    shipping_cost = fields.Monetary(string='Base rate', currency_field='currency_id', readonly=True)
    drop_fee_total = fields.Monetary(string='Total drop fee', currency_field='currency_id', readonly=True)
    total_shipping_cost = fields.Monetary(string='Total cost', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    b.id AS id,
                    COALESCE(b.scheduled_date::date, b.create_date::date) AS report_date,
                    b.id AS batch_id,
                    b.vehicle_id AS vehicle_id,
                    b.provider_id AS provider_id,
                    b.fleet_type_id AS fleet_type_id,
                    (
                        SELECT COUNT(p.id)
                        FROM stock_picking p
                        WHERE p.batch_id = b.id
                    ) AS picking_count,
                    b.franchise_count AS franchise_count,
                    b.planned_weight AS planned_weight,
                    b.done_weight AS done_weight,
                    b.capacity_usage_percent AS capacity_usage_percent,
                    b.shipping_cost AS shipping_cost,
                    b.drop_fee_total AS drop_fee_total,
                    b.total_shipping_cost AS total_shipping_cost,
                    b.currency_id AS currency_id
                FROM stock_picking_batch b
                WHERE b.vehicle_id IS NOT NULL
            )
        """ % self._table)
