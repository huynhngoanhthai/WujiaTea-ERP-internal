{
    'name': 'Wujia Knowledge Library',
    'version': '19.0.1.1.0',
    'category': 'Wujia',
    'summary': 'Knowledge / SOP / training library for franchise stores — HQ writes, publishes, schedules, expires.',
    'description': """
Knowledge library business logic. Split from wujia_portal_knowledge (F9, ADR-027).

- Models wujia.knowledge.article (KNW- code, slug, draft → publish → archive, scheduling, expiry,
  attachments, chatter), wujia.knowledge.category (category tree), wujia.knowledge.tag.
- Daily cron clears the portal flag of expired articles.
- _portal_visible_domain / _portal_search_domain / _portal_get_attachment: rules shared by every channel.
""",
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': ['wujia_franchise', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'views/wujia_knowledge_backend_views.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
