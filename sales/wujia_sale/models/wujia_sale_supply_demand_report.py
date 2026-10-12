from odoo import fields, models, tools


class WujiaSaleSupplyDemandReport(models.Model):
    _name = 'wujia.sale.supply.demand.report'
    _description = 'Wujia Export Warehouse Supply and Demand Report'
    _auto = False
    _order = 'qty_shortage desc, qty_ordered desc'

    default_code = fields.Char(string='Product Code', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product Template', readonly=True)
    categ_id = fields.Many2one('product.category', string='Product Category', readonly=True)
    qty_ordered = fields.Float(string='Ordered Quantity', readonly=True)
    qty_available = fields.Float(string='Available Quantity', readonly=True)
    qty_shortage = fields.Float(string='Shortage Quantity', readonly=True)
    price_unit = fields.Float(string='Unit Price', readonly=True)
    amount_total = fields.Float(string='Total Amount', readonly=True)
    warning_status = fields.Selection([
        ('ok', 'Sufficient Stock'),
        ('warning', 'Stock Shortage Warning'),
    ], string='Warning Status', readonly=True)
    date_order = fields.Date(string='Order Date', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH sales_summary AS (
                    SELECT
                        sol.product_id AS product_id,
                        MAX(CAST(so.date_order AS DATE)) AS date_order,
                        SUM(GREATEST(0, sol.product_uom_qty - COALESCE(sol.qty_delivered, 0))) AS qty_ordered,
                        AVG(sol.price_unit) AS price_unit,
                        SUM(
                            CASE
                                WHEN sol.product_uom_qty > 0 THEN
                                    (GREATEST(0, sol.product_uom_qty - COALESCE(sol.qty_delivered, 0)) / sol.product_uom_qty) * sol.price_subtotal
                                ELSE 0.0
                            END
                        ) AS amount_total
                    FROM sale_order_line sol
                    JOIN sale_order so ON so.id = sol.order_id
                    LEFT JOIN stock_picking_batch spb ON spb.id = so.batch_id
                    WHERE so.state = 'sale'
                      AND COALESCE(so.delivery_status, 'pending') != 'full'
                      AND (spb.id IS NULL OR spb.state != 'done')
                      AND sol.display_type IS NULL
                      AND (sol.product_uom_qty - COALESCE(sol.qty_delivered, 0)) > 0
                    GROUP BY sol.product_id
                ),
                stock_summary AS (
                    SELECT
                        sq.product_id AS product_id,
                        SUM(sq.quantity - sq.reserved_quantity) AS qty_available
                    FROM stock_quant sq
                    JOIN stock_location sl ON sl.id = sq.location_id
                    WHERE sl.is_export = TRUE
                    GROUP BY sq.product_id
                )
                SELECT
                    p.id AS id,
                    p.id AS product_id,
                    p.product_tmpl_id AS product_tmpl_id,
                    p.default_code AS default_code,
                    pt.categ_id AS categ_id,
                    ss.date_order AS date_order,
                    COALESCE(ss.qty_ordered, 0.0) AS qty_ordered,
                    COALESCE(st.qty_available, 0.0) AS qty_available,
                    GREATEST(0.0, COALESCE(ss.qty_ordered, 0.0) - COALESCE(st.qty_available, 0.0)) AS qty_shortage,
                    COALESCE(ss.price_unit, pt.list_price, 0.0) AS price_unit,
                    COALESCE(ss.amount_total, 0.0) AS amount_total,
                    CASE
                        WHEN COALESCE(ss.qty_ordered, 0.0) > COALESCE(st.qty_available, 0.0) THEN 'warning'
                        ELSE 'ok'
                    END AS warning_status
                FROM product_product p
                JOIN product_template pt ON pt.id = p.product_tmpl_id
                LEFT JOIN sales_summary ss ON ss.product_id = p.id
                LEFT JOIN stock_summary st ON st.product_id = p.id
                WHERE p.active = TRUE
                  AND pt.active = TRUE
            )
        """ % self._table)
