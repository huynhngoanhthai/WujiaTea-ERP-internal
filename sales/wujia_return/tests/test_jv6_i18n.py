"""J-V6 — câu gốc của nghiệp vụ đổi trả là tiếng Anh; vi_VN thấy y chữ cũ.

Bảng VN chép từ source TRƯỚC J-V6 (HEAD 0d6464be). Seed loại lỗi (`noupdate`) đổi câu gốc qua
migration 19.0.2.0.0 — chỉ bản ghi HQ chưa sửa tay.
"""
import os

from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.translate import code_translations

from odoo.addons.wujia_return.legacy_seed import ISSUE_TYPE_SEED, issue_types_source_to_en

from .common import load_vi

# Thông báo `_()` chính trước J-V6: câu gốc EN → chữ VN cũ.
MESSAGES_VI = {
    'Request submitted.': 'Yêu cầu đã được gửi.',
    'Request approved.': 'Yêu cầu đã được phê duyệt.',
    'Request rejected: %s': 'Yêu cầu bị từ chối: %s',
    'Request cancelled.': 'Yêu cầu đã bị huỷ.',
    'Select a resolution before approving.': 'Chọn phương án xử lý trước khi duyệt.',
    'Enter a rejection reason before rejecting.': 'Nhập lý do từ chối trước khi từ chối.',
    'Please select an issue type.': 'Vui lòng chọn loại lỗi.',
    'The original order is invalid.': 'Đơn hàng gốc không hợp lệ.',
    'This order has not been fully delivered yet, so a request cannot be created.':
        'Đơn hàng chưa giao hoàn tất, chưa thể tạo yêu cầu.',
    'More than %(days)s days have passed since the order was fully delivered (%(date)s).':
        'Đã quá %(days)s ngày kể từ khi đơn hàng giao hoàn tất (%(date)s).',
    'Please upload %(min)s to %(max)s evidence photos.': 'Cần tải từ %(min)s đến %(max)s ảnh minh chứng.',
    'Compensation order cancelled — entitlement closed per request.':
        'Đơn bù bị huỷ — quyền lợi đóng theo yêu cầu.',
    'No groups to process.': 'Không có nhóm nào để xử lý.',
    # Đổi từ "Compensation SO" để không trùng nhãn field "SO bù".
    'Compensation sales order': 'SO bù hàng',
}
# models.Constraint trên wujia.compensation.allocation (ir.model.constraint.message).
CONSTRAINTS_VI = {
    'check_allocated_positive': 'SL phân bổ phải lớn hơn 0.',
    'check_delivered_nonneg': 'SL đã giao không được âm.',
    'check_released_nonneg': 'SL hoàn lại không được âm.',
}

MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@tagged('post_install', '-at_install', 'wujia_return', 'wujia_jv6')
class TestJv6Messages(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env_vi = load_vi(cls.env)

    def test_python_messages_vi_unchanged(self):
        vi = code_translations.get_python_translations('wujia_return', 'vi_VN')
        for en, old in MESSAGES_VI.items():
            with self.subTest(en=en):
                self.assertEqual(vi.get(en), old)

    def test_constraint_messages(self):
        Cons = self.env['ir.model.constraint']
        for suffix, old in CONSTRAINTS_VI.items():
            with self.subTest(constraint=suffix):
                cons = Cons.search([('name', '=', 'wujia_compensation_allocation_%s' % suffix)])
                self.assertEqual(len(cons), 1)
                self.assertEqual(cons.with_env(self.env_vi).message, old)
                self.assertNotEqual(cons.with_context(lang='en_US').message, old)


@tagged('post_install', '-at_install', 'wujia_return', 'wujia_jv6')
class TestJv6IssueTypeSeed(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env_vi = load_vi(cls.env)

    def test_seed_table_matches_xml(self):
        """ISSUE_TYPE_SEED (câu EN) phải khớp XML — lệch thì migration ghi câu khác bản cài mới."""
        tree = etree.parse(os.path.join(MODULE_DIR, 'data', 'return_issue_type_data.xml'))
        for xmlid, fields_ in ISSUE_TYPE_SEED.items():
            rec = tree.find(".//record[@id='%s']" % xmlid)
            self.assertIsNotNone(rec, xmlid)
            for fname, (_vn, en) in fields_.items():
                with self.subTest(xmlid=xmlid, field=fname):
                    self.assertEqual(rec.find("field[@name='%s']" % fname).text.strip(), en)

    def test_seed_records_en_and_vi(self):
        for xmlid, fields_ in ISSUE_TYPE_SEED.items():
            rec = self.env.ref('wujia_return.%s' % xmlid)
            for fname, (vn, en) in fields_.items():
                with self.subTest(xmlid=xmlid, field=fname):
                    self.assertEqual(rec.with_context(lang='en_US')[fname], en)
                    self.assertEqual(rec.with_env(self.env_vi)[fname], vn)

    def _set_raw(self, rec, fname, value):
        self.env.cr.execute(
            "UPDATE wujia_return_issue_type SET %s = %%s::jsonb WHERE id = %%s" % fname,
            (value, rec.id))

    def _raw(self, rec, fname):
        self.env.cr.execute("SELECT %s FROM wujia_return_issue_type WHERE id = %%s" % fname, (rec.id,))
        return self.env.cr.fetchone()[0]

    def test_migration_only_touches_untouched_seed(self):
        import json
        packaging = self.env.ref('wujia_return.issue_type_packaging')
        wrong = self.env.ref('wujia_return.issue_type_wrong_product')
        expired = self.env.ref('wujia_return.issue_type_expired')
        vn_pack, en_pack = ISSUE_TYPE_SEED['issue_type_packaging']['name']
        vn_exp, en_exp = ISSUE_TYPE_SEED['issue_type_expired']['name']
        # 1) DB cũ: câu VN nằm ở en_US, chưa có vi_VN.
        self._set_raw(packaging, 'name', json.dumps({'en_US': vn_pack}))
        # 2) HQ đã sửa tay ⇒ giữ nguyên.
        self._set_raw(wrong, 'name', json.dumps({'en_US': 'HQ custom', 'vi_VN': 'HQ tự đặt'}))
        # 3) Câu seed cũ nhưng vi_VN đã có bản khác ⇒ đổi en_US, giữ vi_VN.
        self._set_raw(expired, 'name', json.dumps({'en_US': vn_exp, 'vi_VN': 'Quá hạn (HQ)'}))
        self.env.invalidate_all()

        changed = issue_types_source_to_en(self.env.cr)
        self.assertGreaterEqual(changed, 2)
        self.assertEqual(self._raw(packaging, 'name'), {'en_US': en_pack, 'vi_VN': vn_pack})
        self.assertEqual(self._raw(wrong, 'name'), {'en_US': 'HQ custom', 'vi_VN': 'HQ tự đặt'})
        self.assertEqual(self._raw(expired, 'name'), {'en_US': en_exp, 'vi_VN': 'Quá hạn (HQ)'})

        # Chạy lại là no-op (idempotent).
        self.assertEqual(issue_types_source_to_en(self.env.cr), 0)
        self.env.invalidate_all()
        self.assertEqual(packaging.with_env(self.env_vi).name, vn_pack)
        self.assertEqual(packaging.with_context(lang='en_US').name, en_pack)
