{
    'name': 'Wujia Portal — Sale (Catalog + Cart)',
    'version': '19.0.5.5.0',
    'category': 'Wujia',
    'summary': 'Portal ordering page — catalog + shared cart per store (BA controller mapping)',
    'author': 'WujiaTea',
    'license': 'LGPL-3',
    # wujia_portal_purchase_history: dùng chung nhãn trạng thái SO (_state_meta)
    # cho màn kết quả gửi đơn + CTA "Xem chi tiết đơn hàng" trỏ sang trang đó.
    'depends': [
        'wujia_sale', 'wujia_portal_base', 'wujia_order_window',
        'wujia_portal_purchase_history',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/sidenav_inherit.xml',
        'views/mheader_inherit.xml',
        'views/bottomnav_inherit.xml',
        'views/header_cart_inherit.xml',
        'views/order_confirm_modal.xml',
        'views/pc_cart_panel.xml',
        'views/portal_order_catalog.xml',
        'views/portal_order_product_detail.xml',
        'views/portal_order_cart.xml',
        'views/portal_order_result.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'wujia_portal_sale/static/src/css/portal_order.css',
            'wujia_portal_sale/static/src/js/portal_order.js',
            'wujia_portal_sale/static/src/js/portal_cart_sync.js',
            'wujia_portal_sale/static/src/js/header_cart_badge.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
