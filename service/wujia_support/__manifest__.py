{
    'name': 'Wujia Support Tickets',
    'version': '19.0.1.2.0',
    'category': 'Wujia',
    'summary': 'Support requests from franchise stores — HQ receives, assigns, replies, closes.',
    'description': """
Support request business logic. Split from wujia_portal_support (F10, ADR-027).

- Models wujia.support.ticket (WJ-TK/ code, chatter, per-state dates, store/HQ reply
  analysis), wujia.support.category (category + default assignee/team).
- _portal_scope_domain / create_from_portal / _portal_reply / _portal_get_attachment: rules shared
  by every channel.
""",
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': [
        'mail',
        'wujia_franchise',
        'sale',
        'stock_picking_batch',
        'sales_team',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/wujia_support_rules.xml',
        'data/ir_sequence_data.xml',
        'data/wujia_support_category_data.xml',
        'views/wujia_support_backend_views.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
