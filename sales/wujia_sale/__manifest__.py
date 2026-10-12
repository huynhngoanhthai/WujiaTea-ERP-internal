{
    'name': 'Wujia Sale',
    'version': '19.0.4.8.0',
    'category': 'Wujia',
    'summary': 'Sale order extension for franchise stores + weight calculation',
    'author': 'WujiaTea',
    'description': """
Extends sale.order for the portal ordering flow (BA spec):
- is_portal_order: tells portal orders apart from orders created manually by admins.
- franchise_partner_id (M2o res.partner is_franchise=True).
- franchise_id (M2o wujia.franchise.management) — required when is_portal_order.
- portal_requester_user_id, portal_member_id (audit trail).
- area_id (related franchise_id.area_id, store).
- portal_delivery_street/phone/note: per-order delivery address override.

Weight calculation (BA spec section 3):
- sale.order.line.weight_per_unit (snapshot of product.weight, readonly).
- sale.order.line.planned_weight (compute = qty * weight_per_unit, store).
- sale.order.total_planned_weight (compute store).
- stock.move.weight_per_unit/planned_weight/done_weight.
- stock.picking.planned_weight/done_weight (aggregate).
- stock.picking.batch.planned_weight/done_weight (aggregate).

product.product adds: is_public_portal, min_qty, max_qty, wujia_packaging,
name_chinese, public_categ_id (portal catalog — BA sheet sections H + L).
wujia.product.category: portal categories (replaces product.public.category without pulling in website_sale).
""",
    'license': 'LGPL-3',
    'depends': [
        'sale',
        'sale_stock',
        'stock',
        'stock_picking_batch',
        'wujia_franchise',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/wujia_sale_rules.xml',
        'views/sale_order_views.xml',
        'views/product_template_views.xml',
        'views/wujia_sale_order_gift_wizard_views.xml',
        'views/stock_location_views.xml',
        'views/wujia_sale_supply_demand_report_views.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}
