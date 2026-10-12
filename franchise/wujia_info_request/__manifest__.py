{
    'name': 'Wujia Info Update Request',
    'version': '19.0.1.1.0',
    'category': 'Wujia',
    'summary': 'Franchise store information update requests (address, phone, representative...) — reviewed by HQ in the chatter.',
    'description': """
Information update request business rules. Split out of wujia_portal_info_request (F8, ADR-027).

- Model wujia.info.update.request: INF- code, states draft → submitted → reviewing → approved/rejected, attachments, chatter.
- Access: portal users see their store's requests and edit only their own; internal users see everything.
- create_from_portal / _portal_can_request / _portal_scope_domain: shared rules for every channel.
""",
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': ['wujia_franchise', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/wujia_info_request_rules.xml',
        'data/ir_sequence_data.xml',
        'views/info_request_backend.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
