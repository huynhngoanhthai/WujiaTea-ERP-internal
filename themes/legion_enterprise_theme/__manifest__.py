{
    'name': 'Odoo Enterprise Theme',
    'version': '19.0.1.0.1',
    'sequence': 7,
    'summary': 'Odoo Enterprise Theme',
    "author": "Byte Legions",
    'license': 'AGPL-3',
    'maintainer': 'Byte Legions',
    "company": "Byte Legions",
    'website': 'https://bytelegions.com',
    'depends': [
        'web'
    ],
    'category':'Branding',
    'description': """
           Odoo Enterprise Theme
    """,
    'assets': {
        'web.assets_backend': [
            ('prepend', '/legion_enterprise_theme/static/src/scss/primary_variables_custom.scss'),
            '/legion_enterprise_theme/static/src/scss/secondary_variables.scss',
            '/legion_enterprise_theme/static/src/scss/fields_extra_custom.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'images': ['static/description/banner.gif'], 
    
}
