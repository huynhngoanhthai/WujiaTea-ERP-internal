{
    'name': 'Wujia Returns',
    'version': '19.0.2.1.0',
    'category': 'Wujia',
    'summary': 'Returns / compensation — 1 product per request, HQ approval, 0-value compensation SO, compensation delivery tracking.',
    'description': """
Return / compensation business logic. Split from wujia_portal_return (F13, ADR-027).

- wujia.return.request (code RTN/), wujia.return.issue.type, wujia.compensation.allocation (code CA/).
- Compensation wizard: groups approved requests into 0-value SOs per store (FIFO).
- Extends sale.order (cancelling a compensation SO closes the entitlement), stock.picking (actual delivery → compensated qty),
  product.product (compensation policy setup).
- _portal_* / create_from_portal: shared rules for every channel.
""",
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': ['mail', 'wujia_sale', 'wujia_franchise'],
    'data': [
        'security/wujia_return_groups.xml',
        'security/ir.model.access.csv',
        'security/wujia_return_rules.xml',
        'data/ir_sequence_data.xml',
        'data/return_issue_type_data.xml',
        'views/backend_return_request_views.xml',
        'wizards/compensation_process_wizard_views.xml',
        'views/backend_return_issue_type_views.xml',
        'views/backend_product_views.xml',
        'views/backend_menu.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
