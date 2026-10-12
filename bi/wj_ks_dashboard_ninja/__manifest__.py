# -*- coding: utf-8 -*-
{
    'name': 'Wujia Dashboard Ninja',

    'summary': """Dashboard Ninja ported to Odoo 19 for Wujia BOD — interactive dashboards
with tiles, charts (amCharts 5), KPIs, list views, to-do and map views.
Based on Ksolves Dashboard Ninja v18 (AI features stripped).""",

    'description': """
Wujia internal port of Dashboard Ninja (Ksolves) v18 -> Odoo 19.
- AI features removed (no Ksolves API key): item/dashboard generation, chat wizard, TTS.
- TV mode not included.
- Model names kept as ks_dashboard_ninja.* for data compatibility.
""",

    'author': 'Ksolves India Ltd. (port: Wujia)',
    'maintainer': 'Wujia',
    'website': 'https://store.ksolves.com/',
    'license': 'OPL-1',
    'category': 'Services',
    'version': '19.0.1.0.4',

    'images': ['static/description/icon.png'],

    'depends': ['base', 'web', 'base_setup', 'bus', 'base_geolocalize', 'mail'],

    'external_dependencies': {
        'python': ['pandas', 'xlrd', 'openpyxl'],
    },

    'data': [
        'security/ir.model.access.csv',
        'security/ks_security_groups.xml',
        'data/ks_default_data.xml',
        'data/ks_mail_cron.xml',
        'data/dn_data.xml',
        'data/sequence.xml',
        'views/res_settings.xml',
        'views/wj_ks_dashboard_ninja_view.xml',
        'views/wj_ks_dashboard_ninja_item_view.xml',
        'views/ks_dashboard_group_by.xml',
        'views/ks_dashboard_csv_group_by.xml',
        'views/ks_dashboard_action.xml',
        'views/ks_import_dashboard_view.xml',
        'wizard/ks_create_dashboard_wiz_view.xml',
        'wizard/ks_duplicate_dashboard_wiz_view.xml',
        'views/webExtend.xml',
    ],

    'demo': ['demo/wj_ks_dashboard_ninja_demo.xml'],

    'assets': {
        'web.assets_backend': [
            # libs
            'wj_ks_dashboard_ninja/static/lib/css/gridstack.min.css',
            'wj_ks_dashboard_ninja/static/lib/css/awesomplete.css',
            'wj_ks_dashboard_ninja/static/lib/js/gridstack-h5.js',
            'wj_ks_dashboard_ninja/static/lib/js/awesomplete.js',
            'wj_ks_dashboard_ninja/static/lib/js/pdfmake.min.js',
            'wj_ks_dashboard_ninja/static/lib/js/pdf.min.js',
            'wj_ks_dashboard_ninja/static/lib/js/print.min.js',
            # amCharts 5 (loaded eagerly: form-preview widgets use am5 outside the dashboard action)
            'wj_ks_dashboard_ninja/static/lib/js/index.js',
            'wj_ks_dashboard_ninja/static/lib/js/percent.js',
            'wj_ks_dashboard_ninja/static/lib/js/xy.js',
            'wj_ks_dashboard_ninja/static/lib/js/radar.js',
            'wj_ks_dashboard_ninja/static/lib/js/map.js',
            'wj_ks_dashboard_ninja/static/lib/js/worldLow.js',
            'wj_ks_dashboard_ninja/static/lib/js/Animated.js',
            'wj_ks_dashboard_ninja/static/lib/js/Dataviz.js',
            'wj_ks_dashboard_ninja/static/lib/js/Material.js',
            'wj_ks_dashboard_ninja/static/lib/js/Moonrise.js',
            'wj_ks_dashboard_ninja/static/lib/js/exporting.js',
            # css
            'wj_ks_dashboard_ninja/static/src/css/wj_ks_dashboard_ninja.scss',
            'wj_ks_dashboard_ninja/static/src/css/wj_ks_dashboard_ninja_item.css',
            'wj_ks_dashboard_ninja/static/src/css/wj_ks_dashboard_ninja_pro.css',
            'wj_ks_dashboard_ninja/static/src/css/ks_icon_container_modal.css',
            'wj_ks_dashboard_ninja/static/src/css/ks_dashboard_item_theme.css',
            'wj_ks_dashboard_ninja/static/src/css/ks_input_bar.css',
            'wj_ks_dashboard_ninja/static/src/css/ks_dn_filter.css',
            'wj_ks_dashboard_ninja/static/src/css/ks_toggle_icon.css',
            'wj_ks_dashboard_ninja/static/src/css/ks_flower_view.css',
            'wj_ks_dashboard_ninja/static/src/css/ks_map_view.css',
            'wj_ks_dashboard_ninja/static/src/css/ks_funnel_view.css',
            'wj_ks_dashboard_ninja/static/src/css/ks_dashboard_options.css',
            'wj_ks_dashboard_ninja/static/src/css/ks_radial_chart.css',
            'wj_ks_dashboard_ninja/static/src/css/ks_to_do_item.css',
            'wj_ks_dashboard_ninja/static/src/css/style.css',
            # scss design system
            'wj_ks_dashboard_ninja/static/src/scss/variable.scss',
            'wj_ks_dashboard_ninja/static/src/scss/common.scss',
            'wj_ks_dashboard_ninja/static/src/scss/create_dashboard.scss',
            'wj_ks_dashboard_ninja/static/src/scss/header.scss',
            'wj_ks_dashboard_ninja/static/src/scss/overview.scss',
            'wj_ks_dashboard_ninja/static/src/scss/screen.scss',
            'wj_ks_dashboard_ninja/static/src/scss/modal.scss',
            'wj_ks_dashboard_ninja/static/src/scss/ks_dn_gridstack.scss',
            'wj_ks_dashboard_ninja/static/src/scss/recentSearches.scss',
            'wj_ks_dashboard_ninja/static/src/scss/chartScreen.scss',
            'wj_ks_dashboard_ninja/static/src/scss/form_view.scss',
            # js
            'wj_ks_dashboard_ninja/static/src/js/wj_ks_dashboard_ninja_new.js',
            'wj_ks_dashboard_ninja/static/src/js/ks_global_functions.js',
            'wj_ks_dashboard_ninja/static/src/js/ks_filter_props_new.js',
            'wj_ks_dashboard_ninja/static/src/js/domainfix.js',
            'wj_ks_dashboard_ninja/static/src/js/file_uploader_extend.js',
            'wj_ks_dashboard_ninja/static/src/js/formView&NotificationExtend.js',
            'wj_ks_dashboard_ninja/static/src/js/modalsExtend.js',
            'wj_ks_dashboard_ninja/static/src/js/loader_screen.js',
            'wj_ks_dashboard_ninja/static/src/js/dashboards_overview.js',
            'wj_ks_dashboard_ninja/static/src/js/dnNavBarExtend.js',
            'wj_ks_dashboard_ninja/static/src/js/custom_filter.js',
            'wj_ks_dashboard_ninja/static/src/js/ks_dropdown.js',
            # templates + components + widgets
            'wj_ks_dashboard_ninja/static/src/xml/**/*',
            'wj_ks_dashboard_ninja/static/src/components/**/*',
            'wj_ks_dashboard_ninja/static/src/widgets/**/*',
        ],
    },

    'installable': True,
    'application': True,
    'uninstall_hook': 'uninstall_hook',
}
