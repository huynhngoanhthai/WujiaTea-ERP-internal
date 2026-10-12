"""J-V8b — câu gốc constraint/action của khu vực, phường là tiếng Anh; vi_VN giữ y chữ trước phiên.

Chỉ chạy trên DB trắng (`-i wujia_core --test-tags wujia_jv8b`), KHÔNG `-u wujia_core --test-enable` trên DB đủ module.
"""
import re

import psycopg2

from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

CONSTRAINT_VI = {
    'res_area_code_uniq': 'Mã khu vực phải duy nhất.',
    'res_ward_code_state_uniq': 'Mã phường/xã phải duy nhất trong từng tỉnh/thành.',
}
VN_CHARS = re.compile('[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', re.I)


@tagged('post_install', '-at_install', 'wujia_jv8b')
class TestJv8bCoreLabels(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang('vi_VN')
        cls.env['ir.module.module'].search([('name', '=', 'wujia_core')])._update_translations(['vi_VN'])
        cls.env_vi = cls.env(context=dict(cls.env.context, lang='vi_VN'))

    def test_constraint_messages_vi_unchanged(self):
        Constraint = self.env_vi['ir.model.constraint']
        for name, old in CONSTRAINT_VI.items():
            with self.subTest(name=name):
                rec = Constraint.search([('name', '=', name)])
                self.assertEqual(rec.message, old)
                self.assertFalse(VN_CHARS.search(rec.with_context(lang='en_US').message))

    def test_duplicate_area_code_message_vi(self):
        Area = self.env_vi['res.area']
        Area.create({'name': 'JV8B A', 'code': 'JV8B-A'})
        with self.assertRaises(psycopg2.IntegrityError) as cm, mute_logger('odoo.sql_db'), self.env.cr.savepoint():
            Area.create({'name': 'JV8B B', 'code': 'JV8B-A'})
            self.env.flush_all()
        self.assertEqual(Area._sql_error_to_message(cm.exception), CONSTRAINT_VI['res_area_code_uniq'])

    def test_wards_action_title(self):
        area = self.env['res.area'].create({'name': 'JV8B Area', 'code': 'JV8B-W'})
        self.assertEqual(area.with_env(self.env_vi).action_view_wards()['name'], 'Phường/Xã thuộc JV8B Area')
        self.assertEqual(area.with_context(lang='en_US').action_view_wards()['name'], 'Wards of JV8B Area')
