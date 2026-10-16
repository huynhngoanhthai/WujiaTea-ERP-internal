"""KT #73/#83: `-u` giữ bản dịch cũ ⇒ chỉ đổi hai term "order/orders" sang "đơn hàng"."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if not env['res.lang']._lang_get('vi_VN'):
        return
    view = env.ref('wujia_portal_purchase_history.portal_history_results_part', raise_if_not_found=False)
    if view:
        view.update_field_translations('arch_db', {'vi_VN': {'order': 'đơn hàng', 'orders': 'đơn hàng'}})
