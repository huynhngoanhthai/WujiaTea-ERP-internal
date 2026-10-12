"""J-V7 — câu gốc của màn Hỗ trợ là tiếng Anh; user vi_VN phải thấy y chữ trước phiên.

Bảng VN dưới đây chép nguyên từ source TRƯỚC J-V7 (HEAD 8a0d5df6) — chốt chặn khi ai đó đổi
câu EN mà quên glossary/.po. Kèm WJ-SUPPORT-003: mức độ trên PC và mobile cùng một nhãn đã dịch.
"""

import re

from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase

from odoo.addons.wujia_portal_base.controllers.utils import status_badge
from odoo.addons.wujia_portal_base.tests.common import legacy_vn_badge
from odoo.addons.wujia_support.tests.common import load_vi
from odoo.addons.wujia_support.tests.test_support import SupportCommon

SUPPORT_MODULES = ('wujia_portal_layout', 'wujia_portal_base', 'wujia_support', 'wujia_portal_support')

# controllers/portal.py trước J-V7: nhãn desktop (màu = status_badge_for(nhãn VN)).
STATE_VI = {
    'new': 'Mới', 'in_progress': 'Đang xử lý', 'waiting_customer': 'Chờ phản hồi',
    'resolved': 'Đã giải quyết', 'closed': 'Đã đóng', 'cancelled': 'Đã huỷ',
}
# Nhãn + biến thể màu mobile trước J-V7.
MOBILE_VI = {
    'new': ('Mới', 'info'), 'in_progress': ('Đang xử lý', 'processing'),
    'waiting_customer': ('Có phản hồi', 'feedback'), 'resolved': ('Đã giải quyết', 'success'),
    'closed': ('Đã đóng', 'neutral'), 'cancelled': ('Đã huỷ', 'danger'),
}
PRIORITY_VI = {
    'normal': ('Bình thường', 'wujia-badge-muted'),
    'urgent': ('Khẩn', 'wujia-badge-danger'),
}
PRIORITY_EN = {'normal': 'Normal', 'urgent': 'Urgent'}


def _text(html):
    """Chữ hiển thị thô: bỏ thẻ, gộp khoảng trắng."""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))


def _pc_severity(html):
    """Ô "Mức độ"/"Severity" của khối thông tin PC (dt → dd kế tiếp)."""
    m = re.search(r'<dt class="col-5">(?:Mức độ|Severity)</dt>\s*(?:<!--.*?-->\s*)?'
                  r'<dd class="col-7">([^<]*)</dd>', html, re.S)
    return m and m.group(1).strip()


def _mobile_priority(html):
    """Dòng "Ưu tiên"/"Priority" của thẻ thông tin mobile."""
    m = re.search(r'<span class="wujia-mdash-row-sub">(?:Ưu tiên|Priority)</span>\s*'
                  r'<span class="wujia-mdash-row-sub is-strong">([^<]*)</span>', html)
    return m and m.group(1).strip()


@tagged('post_install', '-at_install', 'wujia_support', 'wujia_jv7')
class TestJv7Labels(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env_vi = load_vi(cls.env, SUPPORT_MODULES)
        cls.env_en = cls.env(context=dict(cls.env.context, lang='en_US'))

    def test_state_labels_vi_unchanged_and_same_colour(self):
        from odoo.addons.wujia_portal_support.controllers.portal import STATE_LABELS
        self.assertEqual(set(STATE_LABELS), set(STATE_VI))
        for key, old in STATE_VI.items():
            with self.subTest(key=key):
                lazy, css = STATE_LABELS[key]
                self.assertEqual(self.env_vi._(lazy), old)
                self.assertEqual(self.env_en._(lazy), lazy._source)
                self.assertNotEqual(lazy._source, old)
                # Màu y như khi nhãn còn là câu VN.
                self.assertEqual(css, legacy_vn_badge(old))

    def test_mobile_badges_vi_unchanged_and_same_colour(self):
        from odoo.addons.wujia_portal_support.controllers.portal import MOBILE_TICKET_BADGES
        self.assertEqual(set(MOBILE_TICKET_BADGES), set(MOBILE_VI))
        for key, (old, variant) in MOBILE_VI.items():
            with self.subTest(key=key):
                lazy, css = MOBILE_TICKET_BADGES[key]
                self.assertEqual(self.env_vi._(lazy), old)
                self.assertEqual(css, status_badge(variant))

    def test_priority_labels(self):
        from odoo.addons.wujia_portal_support.controllers.portal import PRIORITY_LABELS
        self.assertEqual(set(PRIORITY_LABELS), set(PRIORITY_VI))
        for key, (old, css) in PRIORITY_VI.items():
            with self.subTest(key=key):
                lazy, new_css = PRIORITY_LABELS[key]
                self.assertEqual(self.env_vi._(lazy), old)
                self.assertEqual(self.env_en._(lazy), PRIORITY_EN[key])
                self.assertEqual(new_css, css)
        # Khoá của bảng nhãn = khoá selection của model (lệch ⇒ PC/mobile rơi về mã thô).
        sel = dict(self.env['wujia.support.ticket']._fields['priority'].selection)
        self.assertEqual(set(sel), set(PRIORITY_LABELS))

    def test_pager_label(self):
        from odoo.addons.wujia_portal_support.controllers import portal as ctrl
        src = open(ctrl.__file__, encoding='utf-8').read()
        self.assertIn("item_label=_lt('requests')", src)
        self.assertEqual(self.env_vi._(ctrl._lt('requests')), 'yêu cầu')

    def test_pc_detail_reads_translated_priority(self):
        """WJ-SUPPORT-003: PC không còn đọc selection thô của field."""
        view = self.env.ref('wujia_portal_support.portal_support_detail')
        arch = view.with_context(lang='en_US').arch
        self.assertNotIn("_fields['priority'].selection", arch)
        self.assertEqual(arch.count("priority_labels.get(ticket.priority"), 2)

    def test_view_labels_in_arch(self):
        cases = {
            'wujia_portal_support.portal_support_list': (
                'Trạng thái', 'Tất cả trạng thái', 'Tìm mã / tiêu đề ticket', 'Xem ticket'),
            'wujia_portal_support.portal_support_detail': ('Mức độ', 'Phân loại', 'phản hồi'),
        }
        for xmlid, words in cases.items():
            view = self.env.ref(xmlid)
            arch_vi = re.sub(r'<!--.*?-->', '', view.with_env(self.env_vi).arch, flags=re.S)
            arch_en = re.sub(r'<!--.*?-->', '', view.with_env(self.env_en).arch, flags=re.S)
            for word in words:
                with self.subTest(view=xmlid, word=word):
                    self.assertIn(word, arch_vi)
                    self.assertNotIn(word, arch_en)


@tagged('post_install', '-at_install', 'wujia_support', 'wujia_jv7')
class TestJv7PortalByLang(SupportCommon, HttpCase):
    """User vi_VN thấy chữ cũ, en_US thấy câu gốc EN — cùng dữ liệu, cùng route."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_support()
        load_vi(cls.env, SUPPORT_MODULES)
        cls.owner.lang = 'vi_VN'
        cls.owner_en = cls.env['res.users'].create({
            'name': 'jv7 en', 'login': 'jv7.en', 'password': 'jv7.en', 'lang': 'en_US',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        cls.env['wujia.franchise.member'].create({
            'user_id': cls.owner_en.id, 'franchise_id': cls.franchise.id, 'role': 'owner'})
        # Mỗi user đúng MỘT ticket ⇒ kiểm số ít EN ("1 ticket").
        cls.t_vi = cls._ticket(title='JV7 vi', priority='normal')
        cls.t_en = cls._ticket(user=cls.owner_en, title='JV7 en', priority='urgent')
        for t in (cls.t_vi, cls.t_en):
            t._portal_reply(t.created_by_id, 'JV7 reply')

    def _get(self, login, url):
        self.authenticate(login, login)
        res = self.url_open(url, timeout=30)
        self.assertEqual(res.status_code, 200)
        return res.text

    def test_list_vi_and_en(self):
        vi = self._get('f10.owner', '/portal/support')
        en = self._get('jv7.en', '/portal/support')
        self.assertIn('JV7 vi', vi)
        self.assertIn('JV7 en', en)
        for word in ('Tất cả trạng thái', 'Tìm mã / tiêu đề ticket', 'Xem ticket', 'Bình thường'):
            self.assertIn(word, vi)
            self.assertNotIn(word, en)
        for word in ('All statuses', 'Search ticket code / title', 'View ticket', 'Urgent'):
            self.assertIn(word, en)
        self.assertRegex(_text(en), r'\b1 ticket\b')
        self.assertNotRegex(_text(en), r'\b1 tickets\b')
        self.assertIn('1 ticket', _text(vi))

    def test_detail_priority_same_on_pc_and_mobile(self):
        """WJ-SUPPORT-003 — cùng giá trị mức độ ⇒ PC = mobile, theo đúng ngôn ngữ người xem."""
        cases = (
            ('f10.owner', self.t_vi, 'Bình thường'),
            ('jv7.en', self.t_en, 'Urgent'),
        )
        for login, ticket, label in cases:
            with self.subTest(login=login):
                html = self._get(login, '/portal/support/%s' % ticket.id)
                self.assertEqual(_pc_severity(html), label)
                self.assertEqual(_mobile_priority(html), label)
        # Đổi locale cùng một ticket ⇒ nhãn đổi nhất quán ở cả hai breakpoint.
        self.owner.lang = 'en_US'
        html = self._get('f10.owner', '/portal/support/%s' % self.t_vi.id)
        self.assertEqual(_pc_severity(html), 'Normal')
        self.assertEqual(_mobile_priority(html), 'Normal')

    def test_detail_reply_count_singular(self):
        vi = _text(self._get('f10.owner', '/portal/support/%s' % self.t_vi.id))
        en = _text(self._get('jv7.en', '/portal/support/%s' % self.t_en.id))
        self.assertIn('1 phản hồi', vi)
        self.assertRegex(en, r'\b1 reply\b')
        self.assertNotRegex(en, r'\b1 replies\b')
