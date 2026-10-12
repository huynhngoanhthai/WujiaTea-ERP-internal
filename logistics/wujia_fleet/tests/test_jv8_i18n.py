"""J-V8a — câu gốc của Đội xe là tiếng Anh; user vi_VN phải thấy y chữ trước phiên.

Bảng VN chép nguyên từ source TRƯỚC J-V8a (HEAD 5dc1c1a0).
"""

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# constraint xmlid → (câu EN mới, câu VN trước phiên)
CONSTRAINTS = {
    'wujia_fleet.constraint_wujia_fleet_management_code_uniq': ('Vehicle code must be unique.', 'Mã xe phải duy nhất.'),
    'wujia_fleet.constraint_wujia_fleet_pricelist_code_uniq': ('Pricelist code must be unique.', 'Mã bảng giá phải duy nhất.'),
    'wujia_fleet.constraint_wujia_fleet_provider_code_uniq': ('Fleet code must be unique.', 'Mã đội xe phải duy nhất.'),
    'wujia_fleet.constraint_wujia_fleet_type_code_uniq': ('Vehicle type code must be unique.', 'Mã loại xe phải duy nhất.'),
}


@tagged('post_install', '-at_install', 'wujia_fleet', 'wujia_jv8')
class TestJv8FleetI18n(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang('vi_VN')
        cls.env['ir.module.module'].search([('name', '=', 'wujia_fleet')])._update_translations(['vi_VN'])
        cls.env_vi = cls.env(context=dict(cls.env.context, lang='vi_VN'))
        cls.env_en = cls.env(context=dict(cls.env.context, lang='en_US'))

    def test_constraint_messages(self):
        for xmlid, (en, vi) in CONSTRAINTS.items():
            with self.subTest(xmlid=xmlid):
                cons = self.env.ref(xmlid)
                self.assertEqual(cons.with_env(self.env_en).message, en)
                self.assertEqual(cons.with_env(self.env_vi).message, vi)

    def _raise_msg(self, env, model, vals):
        with self.assertRaises(ValidationError) as cm:
            env[model].create(vals)
        return str(cm.exception)

    def test_validation_messages_follow_lang(self):
        cases = (
            ('wujia.fleet.type', {'name': 'T', 'payload_capacity_ton': -1},
             'Capacity must be >= 0.', 'Tải trọng phải >= 0.'),
            ('wujia.fleet.provider', {'name': 'P', 'email': 'not-an-email'},
             "Email 'not-an-email' has an invalid format.", "Email 'not-an-email' không đúng định dạng."),
        )
        for model, vals, en, vi in cases:
            with self.subTest(model=model):
                self.assertEqual(self._raise_msg(self.env_en, model, vals), en)
                self.assertEqual(self._raise_msg(self.env_vi, model, vals), vi)
        ftype = self.env['wujia.fleet.type'].create({'name': 'T2'})
        vals = {'name': 'PL', 'fleet_type_id': ftype.id, 'date_from': '2026-10-10', 'date_to': '2026-10-01'}
        self.assertEqual(self._raise_msg(self.env_en, 'wujia.fleet.pricelist', vals), 'Valid to must be >= valid from.')
        self.assertEqual(self._raise_msg(self.env_vi, 'wujia.fleet.pricelist', vals), 'Hiệu lực đến phải >= hiệu lực từ.')

    def test_vehicles_action_name(self):
        provider = self.env['wujia.fleet.provider'].create({'name': 'NDUNG'})
        self.assertEqual(provider.with_env(self.env_en).action_view_vehicles()['name'], 'Vehicles of NDUNG')
        self.assertEqual(provider.with_env(self.env_vi).action_view_vehicles()['name'], 'Xe của NDUNG')
