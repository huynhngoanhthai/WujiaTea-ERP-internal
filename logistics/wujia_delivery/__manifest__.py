{
    'name': 'Wujia Delivery',
    'version': '19.0.1.2.0',
    'category': 'Wujia',
    'summary': 'Delivery dispatch: assign vehicles to batches, compute costs, fleet / store reports',
    'author': 'WujiaTea',
    'description': """
Delivery dispatch (BA spec section B):

- Extends sale.order: copies franchise_id down to stock.picking on confirm.
- Extends stock.picking: franchise_id, area_id (related), vehicle_id (related from batch),
  delivery_status, shipping_cost, drop_fee allocated by planned_weight.
- Extends stock.picking.batch: vehicle_id, capacity meter (is_over_capacity),
  pricelist_id (auto-suggest), shipping_cost / drop_fee_total / total_shipping_cost,
  planned/actual_departure, delivery_batch_status (parallel to the native state).

Reports (SQL view):
- wujia.fleet.shipping.report: 1 row / batch — cost per fleet + load details.
- wujia.franchise.shipping.report: 1 row / picking — cost allocated per store.
""",
    'license': 'LGPL-3',
    'depends': [
        'wujia_fleet',
        'wujia_sale',
        'stock_picking_batch',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_picking_views.xml',
        'views/stock_picking_batch_views.xml',
        'views/wujia_fleet_management_views.xml',
        'report/wujia_fleet_shipping_report_views.xml',
        'report/wujia_franchise_shipping_report_views.xml',
        'views/wujia_delivery_menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
