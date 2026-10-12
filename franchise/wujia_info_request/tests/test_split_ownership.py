"""F8 tách một phần: module portal chỉ còn QWeb của nó; module mới sở hữu đúng phần hook suy ra."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.wujia_core.tools.module_split import imd_names
from odoo.addons.wujia_info_request.hooks import EXTRA, MODELS, NEW_MODULE, OLD_MODULE

PORTAL_TEMPLATES = {'portal_info_request_list', 'portal_info_request_form', 'portal_info_request_detail'}


@tagged('post_install', '-at_install', 'wujia_info_request')
class TestSplitOwnership(TransactionCase):

    def test_old_module_keeps_only_portal_templates(self):
        cr = self.env.cr
        cr.execute("SELECT name FROM ir_model_data WHERE module = %s", (OLD_MODULE,))
        self.assertLessEqual({r[0] for r in cr.fetchall()}, PORTAL_TEMPLATES)
        cr.execute("""SELECT DISTINCT m.name FROM ir_model_constraint c
                        JOIN ir_module_module m ON m.id = c.module
                        JOIN ir_model im ON im.id = c.model WHERE im.model = %s""", (MODELS[0],))
        self.assertEqual([r[0] for r in cr.fetchall()], [NEW_MODULE])
        for xmlid in ('model_wujia_info_update_request', 'action_wujia_info_update_request',
                      'view_wujia_info_update_request_list', 'view_wujia_info_update_request_form',
                      'menu_wujia_info_update_request_root', 'seq_wujia_info_update_request',
                      'rule_info_request_portal_read', 'access_wujia_info_update_request_portal'):
            self.assertTrue(self.env.ref(f'{NEW_MODULE}.{xmlid}', raise_if_not_found=False), xmlid)

    def test_hook_names_cover_the_whole_module(self):
        cr = self.env.cr
        cr.execute("SELECT name FROM ir_model_data WHERE module = %s ORDER BY name", (NEW_MODULE,))
        owned = [r[0] for r in cr.fetchall()]
        self.assertEqual(len(owned), 72)
        self.assertEqual(imd_names(cr, NEW_MODULE, MODELS, extra=EXTRA), owned)
