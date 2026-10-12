"""J-V3 — màn Thi có câu gốc tiếng Anh: user vi_VN thấy y như trước (chữ + màu badge), en_US thấy EN.

Neo đối chứng là nhãn tiếng Việt viết cứng TRƯỚC J-V3 (bảng `_BEFORE`): đổi nhãn/màu mà quên .po
hoặc `_STATUS_TERMS_BY_VARIANT` thì đỏ ở đây, không đợi probe text.
"""
import os
import re

from odoo.tests import TransactionCase, tagged

from odoo.addons.wujia_exam.tests.common import load_vi
from odoo.addons.wujia_portal_base.controllers.utils import status_badge_for
from odoo.addons.wujia_portal_base.tests.common import legacy_vn_badge
from odoo.addons.wujia_portal_base.tests.css_probe import CUSTOM
from odoo.addons.wujia_portal_exam.controllers.portal import (
    PC_PUBLISH_STATES, REG_STATES, SLOT_STATUS_LABELS, _WEEKDAYS, _course_meta,
)

VI_MODULES = ('wujia_portal_layout', 'wujia_portal_base', 'wujia_exam', 'wujia_portal_exam')

# Nhãn tiếng Việt viết cứng trong controller trước J-V3 (git 7e1d5abf).
_BEFORE = {
    'REG_STATES': {'submitted': 'Chờ xác nhận', 'confirmed': 'Đã đăng ký',
                   'rejected': 'Từ chối', 'cancelled': 'Đã hủy'},
    'PC_PUBLISH_STATES': {'published': 'Đã công bố', 'unpublished': 'Chưa công bố',
                          'none': 'Chưa có', 'na': 'Không áp dụng'},
}
# Trước J-V3 ba nhãn này đã là badge trung tính (không có trong bảng màu) — giữ nguyên.
_NEUTRAL = ('unpublished', 'none', 'na')
_TABLES = {'REG_STATES': REG_STATES,
           'PC_PUBLISH_STATES': PC_PUBLISH_STATES}

JS_DIR = os.path.join(CUSTOM, 'wujia_portal_exam', 'static', 'src', 'js')
XML = os.path.join(CUSTOM, 'wujia_portal_exam', 'views', 'portal_exam.xml')


@tagged('post_install', '-at_install', 'wujia_exam')
class TestExamI18nJV3(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env_vi = load_vi(cls.env, VI_MODULES)
        cls.env_en = cls.env(context=dict(cls.env.context, lang='en_US'))

    def test_badge_same_text_and_colour_as_before(self):
        for table, before in _BEFORE.items():
            for key, vn in before.items():
                with self.subTest(table=table, key=key):
                    label, badge = _TABLES[table][key]
                    self.assertEqual(self.env_vi._(label), vn, 'vi_VN đổi chữ')
                    self.assertEqual(badge, legacy_vn_badge(vn), 'đổi màu badge')
                    if key not in _NEUTRAL:
                        self.assertNotEqual(badge, status_badge_for('__unknown__'),
                                            'nhãn EN chưa có trong _STATUS_TERMS_BY_VARIANT')
                    self.assertEqual(self.env_en._(label), label._source)

    def test_slot_and_weekday_labels_follow_lang(self):
        self.assertEqual([self.env_vi._(SLOT_STATUS_LABELS[k]) for k in ('closed', 'expired', 'full')],
                         ['Đã đóng', 'Hết hạn', 'Hết chỗ'])
        self.assertEqual([self.env_en._(SLOT_STATUS_LABELS[k]) for k in ('closed', 'expired', 'full')],
                         ['Closed', 'Expired', 'Fully booked'])
        self.assertEqual([self.env_vi._(w) for w in _WEEKDAYS],
                         ['Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7', 'Chủ nhật'])
        self.assertEqual(self.env_en._(_WEEKDAYS[0]), 'Monday')

    def test_js_messages_declared_on_both_roots(self):
        """JS đọc câu qua `m("key", ...)` ⇒ mọi key phải có `data-wj-msg-key` dịch được ở QWeb."""
        keys = set()
        for name in ('portal_exam_pc.js', 'portal_exam_wizard.js'):
            with open(os.path.join(JS_DIR, name), encoding='utf-8') as fh:
                found = set(re.findall(r'\bm\(["\']([a-z0-9-]+)["\']', fh.read()))
            self.assertTrue(found, '%s không còn gọi m(...)' % name)
            keys |= found
        with open(XML, encoding='utf-8') as fh:
            xml = fh.read()
        msgs = re.search(r'<t t-set="_ex_msgs" t-value="(\{[^"]*\})"', xml)
        self.assertTrue(msgs, 'mất khối _ex_msgs')
        declared = set(re.findall(r"'data-wj-msg-([a-z0-9-]+)'", msgs.group(1)))
        self.assertEqual(keys - declared, set(), 'JS dùng key chưa khai ở _ex_msgs')
        self.assertEqual(xml.count('t-att="_ex_msgs"'), 2, 'root PC + wizard mobile phải gắn _ex_msgs')
        # Câu của khối được dịch: t-set thân chữ ⇒ arch vi_VN chứa tiếng Việt.
        arch_vi = self.env_vi.ref('wujia_portal_exam.portal_exam_register').arch
        self.assertIn('Không tải được khung giờ', arch_vi)

    def test_course_meta_singular_plural(self):
        """EN "1 sessions" sai ngữ pháp ⇒ msgid số ít riêng; vi_VN cả hai về cùng câu cũ."""
        class _Course:
            registration_horizon_days = 60

            def __init__(self, env, n):
                self.env, self._n = env, n

            def _portal_booking_meta(self):
                return {'upcoming_count': self._n, 'closed': False, 'full': False}

        self.assertEqual(_course_meta(_Course(self.env_en, 1))['meta'], '1 session • In the next 60 days')
        self.assertEqual(_course_meta(_Course(self.env_en, 3))['meta'], '3 sessions • In the next 60 days')
        self.assertEqual(_course_meta(_Course(self.env_vi, 1))['meta'], '1 kỳ thi • Trong 60 ngày tới')
        self.assertEqual(_course_meta(_Course(self.env_vi, 3))['meta'], '3 kỳ thi • Trong 60 ngày tới')
