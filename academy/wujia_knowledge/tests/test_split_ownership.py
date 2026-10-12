"""F9 tách một phần: module portal chỉ còn QWeb + nav của nó; module mới sở hữu đúng phần hook suy ra."""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.wujia_core.tools.module_split import imd_names
from odoo.addons.wujia_knowledge.hooks import EXTRA, MODELS, NEW_MODULE, OLD_MODULE

PORTAL_VIEWS = {
    'portal_knowledge_notice', 'portal_knowledge_list', 'portal_knowledge_detail',
    'layout_sidenav_knowledge', 'mobile_bottomnav_knowledge',
}


@tagged('post_install', '-at_install', 'wujia_knowledge')
class TestSplitOwnership(TransactionCase):

    def test_old_module_keeps_only_portal_views(self):
        cr = self.env.cr
        cr.execute("SELECT name FROM ir_model_data WHERE module = %s", (OLD_MODULE,))
        self.assertLessEqual({r[0] for r in cr.fetchall()}, PORTAL_VIEWS)
        for table in ('ir_model_constraint', 'ir_model_relation'):
            cr.execute(f"""SELECT DISTINCT m.name FROM {table} c
                             JOIN ir_module_module m ON m.id = c.module
                             JOIN ir_model im ON im.id = c.model WHERE im.model IN %s""", (tuple(MODELS),))
            self.assertEqual([r[0] for r in cr.fetchall()], [NEW_MODULE], table)
        for xmlid in ('model_wujia_knowledge_article', 'model_wujia_knowledge_category',
                      'model_wujia_knowledge_tag', 'action_knowledge_article',
                      'view_knowledge_article_form', 'menu_wujia_knowledge_root',
                      'menu_wujia_knowledge_tags', 'seq_wujia_knowledge_article',
                      'cron_recompute_is_published', 'access_wujia_knowledge_article_portal'):
            self.assertTrue(self.env.ref(f'{NEW_MODULE}.{xmlid}', raise_if_not_found=False), xmlid)

    def test_hook_names_cover_the_whole_module(self):
        cr = self.env.cr
        cr.execute("SELECT name FROM ir_model_data WHERE module = %s ORDER BY name", (NEW_MODULE,))
        owned = [r[0] for r in cr.fetchall()]
        self.assertEqual(len(owned), 107)
        self.assertEqual(imd_names(cr, NEW_MODULE, MODELS, extra=EXTRA), owned)
