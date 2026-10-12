{
    'name': 'Wujia Notifications',
    'version': '19.0.3.0.0',
    'category': 'Wujia',
    'summary': 'HQ → franchise store notifications — compose, target, send, withdraw, track reads.',
    'description': """
Notification business logic. Split from wujia_portal_notification (F11, ADR-027).

- Models wujia.notification (ANN/ code, chatter, recipient targeting, send/withdraw),
  wujia.notification.type (type), wujia.notification.read (read per user for all-store notifications, per user + store when targeted).
- _portal_history_domain / _portal_effective_domain / _portal_unread_count / _mark_read /
  _portal_get_attachment: rules shared by every channel.
""",
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': ['mail', 'wujia_franchise'],
    'data': [
        'security/wujia_notification_groups.xml',
        'security/ir.model.access.csv',
        'security/wujia_notification_rules.xml',
        'data/ir_sequence_data.xml',
        'data/notification_type_data.xml',
        'views/backend_notification_views.xml',
        'views/backend_menu.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
