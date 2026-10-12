{
    'name': 'Wujia Order Window',
    'version': '19.0.2.0.0',
    'category': 'Wujia',
    'summary': 'Ordering windows by area (BA Section B.5 + Model Field Section I)',
    'description': """
Time windows in which portal orders may be created, configured per area. Split from wujia_portal_order_window (F7, ADR-027).

- Model wujia.order.window: a window applies to several res.area; an area may have several windows (morning + evening).
- Store timezone = partner_id.tz of the franchise (field tz on the store form); windows are checked in that local time.
- res.config.settings: 3 fallback parameters wujia_portal.* when no window matches the store's area.
- _is_within_order_window(franchise): matching windows OR'ed, else global fallback; store without timezone is blocked.
- _next_order_window(franchise): the next window to open (time + date) for the "outside ordering hours" screen.
- sale.order.create blocks portal orders outside the window, raises OrderWindowClosed.
""",
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': ['wujia_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/wujia_order_window_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
