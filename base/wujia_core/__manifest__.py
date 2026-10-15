{
    'name': 'Wujia Core',
    'version': '19.0.2.2.0',
    'category': 'Wujia',
    'summary': 'Shared core master data: areas, wards, mixins, helpers',
    'description': """
Base module for all Wujia customisations. Contains:
- res.area: business area / delivery zone (Many2many ward_ids)
- res.ward: ward, linked to res.country.state
- Branding (res.company + Settings): name, primary colour, PC/mobile logo, favicon, login background; backend favicon + tab title follow the brand

Other modules (wujia_franchise, wujia_franchise_management, wujia_sale)
depend on wujia_core only for this master data, without knowing about franchises.
""",
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'mail', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_ward_views.xml',
        'views/res_area_views.xml',
        'views/res_config_settings_views.xml',
        'views/webclient_templates.xml',
        'views/wujia_core_menus.xml',
        'views/res_users_views.xml',
        'views/wujia_user_menu_tree_wizard_views.xml',
        'data/brand_defaults.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'wujia_core/static/src/js/brand_title.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
