{
    'name': 'Wujia Translations',
    'version': '19.0.1.3.0',
    'category': 'Wujia',
    'summary': 'Translation catalog: scan, edit, apply instantly, keep edits across module upgrades',
    'description': """
Backend translation tool (cluster J, sessions J-T1+T2):
- Scan module strings (same source as Odoo's .pot export) into a term x language catalog
- Edit translations in place; filter untranslated / edited / waiting to apply; coverage per module
- Apply instantly to labels, menus, views and QWeb templates (no restart); edits are re-applied after every -u
- Import / export: glossary CSV (key,option,VN,CN,TH) and a zip of .po + .pot per module (J-T4)
- Machine translation (DeepL, J-T5): pick a language, translate untranslated strings in the background,
  applied at once and marked "Machine translated" for review; glossary of fixed terms; edits are never replaced
- Python/JS strings edited (or machine translated) here take effect after .po export, commit and restart
""",
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'data': [
        'security/i18n_security.xml',
        'data/res_lang_data.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'data/glossary_data.xml',
        'wizard/scan_wizard_views.xml',
        'wizard/transfer_wizard_views.xml',
        'wizard/mt_wizard_views.xml',
        'views/i18n_glossary_views.xml',
        'views/res_config_settings_views.xml',
        'views/i18n_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
