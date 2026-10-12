"""F13 tách một phần: module portal chỉ còn QWeb + nav; module mới sở hữu đúng phần hook suy ra."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.wujia_core.tools.module_split import imd_names
from odoo.addons.wujia_return.hooks import EXTRA, MODELS, NEW_MODULE, OLD_MODULE

PORTAL_VIEWS = {
    'portal_return_list', 'portal_return_form', 'portal_return_detail',
    'layout_sidenav_return', 'mobile_bottomnav_return',
}


@tagged('post_install', '-at_install', 'wujia_return')
class TestSplitOwnership(TransactionCase):

    def test_old_module_keeps_only_portal_views(self):
        cr = self.env.cr
        cr.execute("SELECT name FROM ir_model_data WHERE module = %s", (OLD_MODULE,))
        self.assertLessEqual({r[0] for r in cr.fetchall()}, PORTAL_VIEWS)
        own = MODELS[:6]
        for table in ('ir_model_constraint', 'ir_model_relation'):
            cr.execute(f"""SELECT DISTINCT m.name FROM {table} c
                             JOIN ir_module_module m ON m.id = c.module
                             JOIN ir_model im ON im.id = c.model WHERE im.model IN %s""", (tuple(own),))
            self.assertEqual([r[0] for r in cr.fetchall()], [NEW_MODULE], table)
        for xmlid in ('model_wujia_return_request', 'model_wujia_compensation_allocation',
                      'action_wujia_return_request', 'action_wujia_return_order', 'view_wujia_return_order_list',
                      'view_product_product_form_return', 'action_open_compensation_wizard',
                      'menu_wujia_return_root', 'menu_wujia_return_issue_type', 'seq_wujia_return_request',
                      'seq_wujia_compensation_allocation', 'group_return_manager', 'res_groups_privilege_return',
                      'rule_wujia_return_request_portal', 'issue_type_other',
                      'field_product_product__compensation_enabled'):
            self.assertTrue(self.env.ref(f'{NEW_MODULE}.{xmlid}', raise_if_not_found=False), xmlid)

    def test_hook_names_cover_the_whole_module(self):
        cr = self.env.cr
        cr.execute("SELECT name FROM ir_model_data WHERE module = %s ORDER BY name", (NEW_MODULE,))
        owned = [r[0] for r in cr.fetchall()]
        self.assertEqual(imd_names(cr, NEW_MODULE, MODELS, extra=EXTRA), owned)

    def test_manager_buttons_visible_to_manager(self):
        """Bẫy F12: ``groups=`` trong arch thiếu tiền tố module thì nút ẩn cả với Administrator."""
        arch = self.env['wujia.return.request'].with_user(self.env.ref('base.user_admin')).get_view(
            self.env.ref(f'{NEW_MODULE}.view_wujia_return_request_form').id)['arch']
        for method in ('action_approve', 'action_reject'):
            self.assertIn(f'name="{method}"', arch)
