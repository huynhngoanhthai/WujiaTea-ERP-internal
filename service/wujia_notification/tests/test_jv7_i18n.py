"""J-V7 — câu gốc của nghiệp vụ thông báo là tiếng Anh; vi_VN thấy y chữ cũ.

Bảng VN chép từ source TRƯỚC J-V7 (HEAD 8a0d5df6). Seed loại thông báo (`noupdate`) đổi câu gốc qua
migration 19.0.2.0.0 — chỉ bản ghi HQ chưa sửa tay.
"""
import json
import os

from lxml import etree

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.translate import code_translations

from odoo.addons.wujia_notification.legacy_seed import (
    NOTIFICATION_TYPE_SEED,
    notification_types_source_to_en,
)

from .common import load_vi

# Hằng MSG_* (models/wujia_notification.py) trước J-V7: câu gốc EN → chữ VN cũ.
MESSAGES_VI = {
    'MSG_PUBLISH_VALIDATION': 'Vui lòng nhập đầy đủ tiêu đề, nội dung, loại và mức độ thông báo; '
                              'ngày hết hiệu lực không được nhỏ hơn ngày gửi.',
    'MSG_TARGET_NO_CRITERIA': 'Chọn "Theo tiêu chí" thì phải có ít nhất một tiêu chí: khu vực, tỉnh/thành '
                              'hoặc cửa hàng loại trừ.',
    'MSG_TARGET_EMPTY': 'Tiêu chí hiện không khớp cửa hàng nào. Vui lòng chỉnh lại trước khi gửi.',
    'MSG_TARGET_MANUAL_EMPTY': 'Vui lòng chọn ít nhất một cửa hàng nhận.',
    'MSG_TARGET_ALL_HAS_STORES': 'Gửi cho "Tất cả cửa hàng" thì không được chọn cửa hàng nhận.',
}
# models.Constraint / UniqueIndex (ir.model.constraint.message) trước J-V7.
CONSTRAINTS_VI = {
    'wujia_notification_uniq_code': 'Mã thông báo phải duy nhất.',
    'wujia_notification_published_date_required': 'Thông báo đã gửi phải có ngày gửi.',
    'wujia_notification_expired_after_published': 'Ngày hết hiệu lực không được nhỏ hơn ngày gửi.',
    'wujia_notification_read_uniq_noti_user_store': 'Mỗi user chỉ ghi nhận đọc 1 lần / thông báo / cửa hàng.',
    'wujia_notification_read_uniq_noti_user_no_store':
        'Mỗi user chỉ ghi nhận đọc 1 lần / thông báo khi chưa chọn cửa hàng.',
    'wujia_notification_type_uniq_code': 'Mã loại thông báo phải duy nhất.',
}
# Nhãn mức độ portal (spec F §5) — selection gốc EN, vi_VN là chữ BA.
PRIORITY_VI = {'normal': 'Thông thường', 'important': 'Quan trọng', 'urgent': 'Cần làm'}

MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@tagged('post_install', '-at_install', 'wujia_notification', 'wujia_jv7')
class TestJv7Messages(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env_vi = load_vi(cls.env)

    def test_python_messages_vi_unchanged(self):
        from odoo.addons.wujia_notification.models import wujia_notification as mod
        vi = code_translations.get_python_translations('wujia_notification', 'vi_VN')
        for const, old in MESSAGES_VI.items():
            with self.subTest(const=const):
                lazy = getattr(mod, const)
                self.assertEqual(vi.get(lazy._source), old)
                self.assertEqual(self.env_vi._(lazy), old)
                self.assertNotEqual(lazy._source, old)

    def test_message_raised_in_user_language(self):
        ntype = self.env.ref('wujia_notification.ntype_other')
        noti = self.env['wujia.notification'].create({'name': 'JV7', 'type_id': ntype.id})
        with self.assertRaises(UserError) as cm:
            noti.with_env(self.env_vi).action_publish()
        self.assertEqual(str(cm.exception), MESSAGES_VI['MSG_PUBLISH_VALIDATION'])
        with self.assertRaises(UserError) as cm:
            noti.with_context(lang='en_US').action_publish()
        self.assertNotIn('Vui lòng', str(cm.exception))

    def test_constraint_messages(self):
        Cons = self.env['ir.model.constraint']
        for name, old in CONSTRAINTS_VI.items():
            with self.subTest(constraint=name):
                cons = Cons.search([('name', '=', name)])
                self.assertEqual(len(cons), 1)
                self.assertEqual(cons.with_env(self.env_vi).message, old)
                self.assertNotEqual(cons.with_context(lang='en_US').message, old)

    def test_priority_label_follows_user_language(self):
        ntype = self.env.ref('wujia_notification.ntype_other')
        for key, old in PRIORITY_VI.items():
            with self.subTest(priority=key):
                noti = self.env['wujia.notification'].create({
                    'name': 'JV7 %s' % key, 'type_id': ntype.id, 'priority': key})
                self.assertEqual(noti.with_env(self.env_vi).priority_label, old)
                self.assertNotEqual(noti.with_context(lang='en_US').priority_label, old)


@tagged('post_install', '-at_install', 'wujia_notification', 'wujia_jv7')
class TestJv7NotificationTypeSeed(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env_vi = load_vi(cls.env)

    def test_seed_table_matches_xml(self):
        """NOTIFICATION_TYPE_SEED (câu EN) phải khớp XML — lệch thì migration ghi câu khác bản cài mới."""
        tree = etree.parse(os.path.join(MODULE_DIR, 'data', 'notification_type_data.xml'))
        ids = {rec.get('id') for rec in tree.iterfind('.//record')}
        self.assertEqual(ids, set(NOTIFICATION_TYPE_SEED))
        for xmlid, (_vn, en) in NOTIFICATION_TYPE_SEED.items():
            with self.subTest(xmlid=xmlid):
                rec = tree.find(".//record[@id='%s']" % xmlid)
                self.assertEqual(rec.find("field[@name='name']").text.strip(), en)

    def test_seed_records_en_and_vi(self):
        for xmlid, (vn, en) in NOTIFICATION_TYPE_SEED.items():
            rec = self.env.ref('wujia_notification.%s' % xmlid)
            with self.subTest(xmlid=xmlid):
                self.assertEqual(rec.with_context(lang='en_US').name, en)
                self.assertEqual(rec.with_env(self.env_vi).name, vn)

    def _set_raw(self, rec, value):
        self.env.cr.execute(
            "UPDATE wujia_notification_type SET name = %s::jsonb WHERE id = %s",
            (json.dumps(value), rec.id))

    def _raw(self, rec):
        self.env.cr.execute("SELECT name FROM wujia_notification_type WHERE id = %s", (rec.id,))
        return self.env.cr.fetchone()[0]

    def test_migration_only_touches_untouched_seed(self):
        urgent = self.env.ref('wujia_notification.ntype_urgent')
        promo = self.env.ref('wujia_notification.ntype_promo')
        other = self.env.ref('wujia_notification.ntype_other')
        vn_urg, en_urg = NOTIFICATION_TYPE_SEED['ntype_urgent']
        vn_oth, en_oth = NOTIFICATION_TYPE_SEED['ntype_other']
        # 1) DB cũ: câu VN nằm ở en_US, chưa có vi_VN.
        self._set_raw(urgent, {'en_US': vn_urg})
        # 2) HQ đã sửa tay ⇒ giữ nguyên.
        self._set_raw(promo, {'en_US': 'HQ custom', 'vi_VN': 'HQ tự đặt'})
        # 3) Câu seed cũ nhưng vi_VN đã có bản khác ⇒ đổi en_US, giữ vi_VN.
        self._set_raw(other, {'en_US': vn_oth, 'vi_VN': 'Khác (HQ)'})
        self.env.invalidate_all()

        changed = notification_types_source_to_en(self.env.cr)
        self.assertGreaterEqual(changed, 2)
        self.assertEqual(self._raw(urgent), {'en_US': en_urg, 'vi_VN': vn_urg})
        self.assertEqual(self._raw(promo), {'en_US': 'HQ custom', 'vi_VN': 'HQ tự đặt'})
        self.assertEqual(self._raw(other), {'en_US': en_oth, 'vi_VN': 'Khác (HQ)'})

        # Chạy lại là no-op (idempotent).
        self.assertEqual(notification_types_source_to_en(self.env.cr), 0)
        self.env.invalidate_all()
        self.assertEqual(urgent.with_env(self.env_vi).name, vn_urg)
        self.assertEqual(urgent.with_context(lang='en_US').name, en_urg)
