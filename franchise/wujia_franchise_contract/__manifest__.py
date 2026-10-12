{
    'name': 'Wujia Franchise Contract',
    'version': '19.0.2.0.0',
    'category': 'Wujia',
    'summary': 'Quản lý hợp đồng nhượng quyền theo Store',
    'author': 'WujiaTea',
    'description': """
Module mở rộng độc lập cho phân hệ nhượng quyền Wujia:
1. Model wujia.franchise.contract quản lý hợp đồng nhượng quyền độc lập theo Store.
2. Kiểm soát không chồng lấn thời gian (No date overlap) giữa các hợp đồng của cùng Store.
3. Tự động xác định Hợp đồng hiện hành (current_contract_id) và phản ánh thông tin lên Store Master.
4. Smart Button "Hợp đồng" và Tab "Hợp đồng nhượng quyền" trên Form View Store.
5. Migration tự động dữ liệu ngày hợp đồng hiện có từ Store.
""",
    'license': 'LGPL-3',
    'depends': [
        'wujia_franchise',
        'mail',
    ],
    'data': [
        'security/wujia_franchise_contract_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'views/wujia_franchise_contract_views.xml',
        'views/wujia_franchise_management_views.xml',
        'views/wujia_franchise_contract_menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
