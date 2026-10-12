{
    'name': 'Wujia Fleet',
    'version': '19.0.1.1.0',
    'category': 'Wujia',
    'summary': 'Fleet / carrier / vehicle type / vehicle / freight pricelist management',
    'author': 'WujiaTea',
    'description': """
Fleet master data (BA spec section B):

- wujia.fleet.provider: carrier / fleet (company / outsource).
- wujia.fleet.type: vehicle type (truck, pickup, refrigerated...) + standard payload.
- wujia.fleet.management: individual vehicle (license_plate, driver, status), linked to provider + type.
- wujia.fleet.pricelist: freight pricelist by vehicle type + carrier + scope (city/interprovince).
- wujia.fleet.pricelist.line: price line per area (res.area), drop_fee per stop.

This module does NOT touch stock.picking / stock.picking.batch — dispatching lives in
wujia_delivery to avoid a circular dependency with wujia_sale.
""",
    'license': 'LGPL-3',
    'depends': [
        'wujia_core',
        'wujia_franchise',
        'mail',
    ],
    'data': [
        'security/wujia_fleet_groups.xml',
        'security/ir.model.access.csv',
        'views/wujia_fleet_provider_views.xml',
        'views/wujia_fleet_type_views.xml',
        'views/wujia_fleet_management_views.xml',
        'views/wujia_fleet_pricelist_views.xml',
        'views/wujia_fleet_menu.xml',
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
