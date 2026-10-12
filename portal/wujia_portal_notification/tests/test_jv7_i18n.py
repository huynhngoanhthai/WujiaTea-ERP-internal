"""J-V7 — câu gốc của màn Thông báo + chuông header là tiếng Anh; user vi_VN thấy y chữ trước phiên.

Bảng VN chép nguyên từ source TRƯỚC J-V7 (HEAD 8a0d5df6) — chốt chặn khi ai đó đổi câu EN mà quên
glossary/.po.
"""

import os
import re
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase

from odoo.addons.wujia_notification.tests.common import load_vi
from odoo.addons.wujia_notification.tests.test_portal_rules import NotificationCommon

NOTI_MODULES = ('wujia_portal_layout', 'wujia_portal_base', 'wujia_notification', 'wujia_portal_notification')

# controllers/portal.py trước J-V7.
ERRORS_VI = {
    'SESSION_EXPIRED': 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.',
    'STORE_NOT_SELECTED': 'Vui lòng chọn cửa hàng trước khi thao tác.',
    'STORE_ACCESS_DENIED': 'Bạn không có quyền thao tác với cửa hàng này.',
    'INVALID_FILTER': 'Bộ lọc không hợp lệ. Vui lòng kiểm tra lại.',
    'INVALID_PAGE_SIZE': 'Số lượng bản ghi mỗi trang không hợp lệ.',
    'ANNOUNCEMENT_NOT_AVAILABLE': 'Thông báo không tồn tại, đã bị thu hồi hoặc bạn không có quyền xem.',
    'MARK_READ_FAILED': 'Chưa thể cập nhật trạng thái đã đọc. Vui lòng thử lại.',
    'ATTACHMENT_NOT_AVAILABLE': 'Tài liệu không tồn tại hoặc bạn không có quyền tải xuống.',
}
PRIORITY_VI = {'normal': 'Thông thường', 'important': 'Quan trọng', 'urgent': 'Cần làm'}
PRIORITY_EN = {'normal': 'Regular', 'important': 'Important', 'urgent': 'Action required'}
PC_TAG_CSS = {'urgent': 'wj-pc-badge--done', 'important': 'wj-pc-badge--transit',
              'normal': 'wj-pc-badge--confirmed'}
# Câu JS trước J-V7 → key data-wj-msg-* (câu có số viết thành %s).
BELL_JS_VI = {
    'total-one': '%s thông báo', 'total-n': '%s thông báo', 'unread-n': '%s chưa đọc',
    'empty': 'Không có thông báo nào.', 'has-file': 'Có file',
    'load-failed': 'Không tải được thông báo.',
}
BULK_JS_VI = {
    'mark-failed': 'Chưa thể đánh dấu đã đọc. Vui lòng thử lại.',
    'marked-one': 'Đã đánh dấu %s thông báo là đã đọc.',
    'marked-n': 'Đã đánh dấu %s thông báo là đã đọc.',
}
BELL_JS_EN = {
    'total-one': '%s notification', 'total-n': '%s notifications', 'unread-n': '%s unread',
    'empty': 'No notifications.', 'has-file': 'Has file', 'load-failed': 'Could not load notifications.',
}
BULK_JS_EN = {
    'mark-failed': 'Could not mark as read. Please try again.',
    'marked-one': 'Marked %s notification as read.',
    'marked-n': 'Marked %s notifications as read.',
}

MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(MODULE_DIR, rel), encoding='utf-8') as fh:
        return fh.read()


def _js_code(rel):
    return re.sub(r'/\*.*?\*/|//[^\n]*', '', _read(rel), flags=re.S)


@tagged('post_install', '-at_install', 'wujia_notification', 'wujia_jv7')
class TestJv7Labels(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env_vi = load_vi(cls.env, NOTI_MODULES)
        cls.env_en = cls.env(context=dict(cls.env.context, lang='en_US'))

    def test_error_messages_vi_unchanged(self):
        from odoo.addons.wujia_portal_notification.controllers.portal import ERROR_MESSAGES
        self.assertEqual(set(ERROR_MESSAGES), set(ERRORS_VI))
        for code, old in ERRORS_VI.items():
            with self.subTest(code=code):
                lazy = ERROR_MESSAGES[code]
                self.assertEqual(self.env_vi._(lazy), old)
                self.assertEqual(self.env_en._(lazy), lazy._source)
                self.assertNotEqual(lazy._source, old)

    def test_priority_labels_and_colours(self):
        from odoo.addons.wujia_portal_notification.controllers.portal import (
            PC_PRIORITY_TAGS, PORTAL_PRIORITY_LABELS, VALID_PRIORITIES,
        )
        self.assertEqual(set(PORTAL_PRIORITY_LABELS), set(VALID_PRIORITIES))
        for key, old in PRIORITY_VI.items():
            with self.subTest(key=key):
                self.assertEqual(self.env_vi._(PORTAL_PRIORITY_LABELS[key]), old)
                self.assertEqual(self.env_en._(PORTAL_PRIORITY_LABELS[key]), PRIORITY_EN[key])
                label, css = PC_PRIORITY_TAGS[key]
                self.assertIs(label, PORTAL_PRIORITY_LABELS[key])
                self.assertEqual(css, PC_TAG_CSS[key])

    def test_pager_label(self):
        from odoo.addons.wujia_portal_notification.controllers import portal as ctrl
        src = open(ctrl.__file__, encoding='utf-8').read()
        self.assertEqual(src.count("item_label=_lt('notifications')"), 2)
        self.assertEqual(self.env_vi._(ctrl._lt('notifications')), 'thông báo')

    def test_view_labels_in_arch(self):
        cases = {
            'wujia_portal_notification.portal_notification_list': (
                'Nhập tiêu đề, mã thông báo...', 'Loại thông báo', 'Trạng thái', 'Chưa đọc',
                'Tìm mã / tiêu đề'),
            'wujia_portal_notification.portal_notification_results_part': (
                'Xem', *PRIORITY_VI.values(), *BULK_JS_VI.values()),
            'wujia_portal_notification.portal_notification_detail': (
                'Thông báo khẩn — cần xử lý ngay', 'Thông báo dành cho cửa hàng nhượng quyền',
                'Chương trình khuyến mãi &amp; ưu đãi', 'Thông báo hệ thống &amp; vận hành', 'Thông báo khác',
                *PRIORITY_VI.values()),
            'wujia_portal_notification.layout_top_navbar_bell_icon': tuple(set(BELL_JS_VI.values())),
        }
        for xmlid, words in cases.items():
            view = self.env.ref(xmlid)
            arch_vi = re.sub(r'<!--.*?-->', '', view.with_env(self.env_vi).arch, flags=re.S)
            arch_en = re.sub(r'<!--.*?-->', '', view.with_env(self.env_en).arch, flags=re.S)
            for word in words:
                with self.subTest(view=xmlid, word=word):
                    self.assertIn(word, arch_vi)
                    self.assertNotIn(word, arch_en)


@tagged('post_install', '-at_install', 'wujia_notification', 'wujia_jv7')
class TestJv7JsMessages(TransactionCase):
    """Mọi key `m("<key>"` trong JS có `data-wj-msg-<key>` trên đúng phần tử gốc; fallback là tiếng Anh."""

    def _check(self, js_rel, xml_rel, att_var, en):
        js = _js_code(js_rel)
        keys = set(re.findall(r'\bm\("([\w-]+)"', js))
        self.assertEqual(keys, set(en))
        xml = _read(xml_rel)
        self.assertEqual(xml.count('t-att="%s"' % att_var), 1)
        for key, text in en.items():
            with self.subTest(key=key):
                self.assertEqual(xml.count("'data-wj-msg-%s'" % key), 1)
                self.assertIn('m("%s", "%s"' % (key, text), js)
                self.assertIn('>%s</t>' % text, xml)

    def test_bell_popup(self):
        self._check('static/src/js/header_bell_badge.js', 'views/header_bell_inherit.xml',
                    '_nt_popup_msgs', BELL_JS_EN)

    def test_bulk_read_button(self):
        self._check('static/src/js/portal_notification_pc.js', 'views/portal_notification.xml',
                    '_nt_bulk_msgs', BULK_JS_EN)

    def test_no_vietnamese_left_in_js(self):
        for rel in ('static/src/js/header_bell_badge.js', 'static/src/js/portal_notification_pc.js'):
            code = _js_code(rel)
            with self.subTest(js=rel):
                self.assertIsNone(re.search('[À-ỹđĐ]', code))


@tagged('post_install', '-at_install', 'wujia_notification', 'wujia_jv7')
class TestJv7PortalByLang(NotificationCommon, HttpCase):
    """User vi_VN thấy chữ cũ, en_US thấy câu gốc EN — cùng dữ liệu, cùng route."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_notification(login='jv7.noti.vi')
        load_vi(cls.env, NOTI_MODULES)
        cls.user.lang = 'vi_VN'
        cls.user_en = cls.env['res.users'].create({
            'name': 'jv7 noti en', 'login': 'jv7.noti.en', 'password': 'jv7.noti.en', 'lang': 'en_US',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        cls.user_nostore = cls.env['res.users'].create({
            'name': 'jv7 noti nostore', 'login': 'jv7.noti.ns', 'password': 'jv7.noti.ns', 'lang': 'vi_VN',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        Member = cls.env['wujia.franchise.member']
        for user in (cls.user, cls.user_en):
            Member.create({'user_id': user.id, 'franchise_id': cls.store_a.id, 'role': 'owner'})
        cls.live.priority = 'urgent'
        # Loại thông báo URG ⇒ chi tiết mobile hiện mô tả loại.
        cls.urgent = cls.env['wujia.notification'].create({
            'name': 'JV7 khẩn', 'type_id': cls.env.ref('wujia_notification.ntype_urgent').id,
            'content': '<p>JV7</p>', 'state': 'published', 'priority': 'important',
            'published_date': fields.Datetime.now() - timedelta(minutes=1),
            'is_pinned': True, 'target_mode': 'all'})

    def _get(self, login, url):
        self.authenticate(login, login)
        res = self.url_open(url, timeout=30)
        self.assertEqual(res.status_code, 200)
        return res.text

    def test_list_vi_and_en(self):
        vi = self._get('jv7.noti.vi', '/portal/notification')
        en = self._get('jv7.noti.en', '/portal/notification')
        for word in ('Nhập tiêu đề, mã thông báo...', 'Loại thông báo', 'Tìm mã / tiêu đề',
                     PRIORITY_VI['urgent'], '>Xem</a>'):
            with self.subTest(word=word):
                self.assertIn(word, vi)
                self.assertNotIn(word, en)
        for word in ('Enter title, notification code...', 'Notification type', 'Search code / title',
                     PRIORITY_EN['urgent'], '>View</a>'):
            self.assertIn(word, en)
        for key in BULK_JS_VI:
            with self.subTest(key=key):
                self.assertIn('data-wj-msg-%s="%s"' % (key, BULK_JS_VI[key]), vi)
                self.assertIn('data-wj-msg-%s="%s"' % (key, BULK_JS_EN[key]), en)

    def test_bell_popup_messages_on_every_page(self):
        vi = self._get('jv7.noti.vi', '/portal')
        en = self._get('jv7.noti.en', '/portal')
        for key in BELL_JS_VI:
            with self.subTest(key=key):
                self.assertIn('data-wj-msg-%s="%s"' % (key, BELL_JS_VI[key]), vi)
                self.assertIn('data-wj-msg-%s="%s"' % (key, BELL_JS_EN[key]), en)

    def test_detail_vi_and_en(self):
        url = '/portal/notification/%s' % self.urgent.id
        vi = self._get('jv7.noti.vi', url)
        en = self._get('jv7.noti.en', url)
        self.assertIn('Thông báo khẩn — cần xử lý ngay', vi)
        self.assertIn('Urgent notice — action needed now', en)
        self.assertNotIn('Thông báo khẩn — cần xử lý ngay', en)
        self.assertIn(PRIORITY_VI['important'], vi)
        self.assertIn(PRIORITY_EN['important'], en)
        # Badge PC giữ màu theo mức độ ở cả hai ngôn ngữ.
        self.assertIn(PC_TAG_CSS['important'], vi)
        self.assertIn(PC_TAG_CSS['important'], en)

    def test_recent_json_priority_label(self):
        for login, labels in (('jv7.noti.vi', PRIORITY_VI), ('jv7.noti.en', PRIORITY_EN)):
            with self.subTest(login=login):
                self.authenticate(login, login)
                items = self.make_jsonrpc_request('/portal/notification/recent')['notifications']
                mine = {n['id']: n for n in items}
                self.assertIn(self.urgent.id, mine)
                for noti in (self.urgent, self.live):
                    if noti.id in mine:
                        self.assertEqual(mine[noti.id]['priority_label'], labels[noti.priority])

    def test_mark_all_without_store_not_an_error(self):
        # WJ-NOTI-001: chưa chọn cửa hàng vẫn đánh dấu được thông báo toàn hệ — không còn STORE_NOT_SELECTED.
        # Câu lỗi theo ngôn ngữ vẫn kiểm ở test_error_messages_vi_unchanged.
        self.authenticate('jv7.noti.ns', 'jv7.noti.ns')
        res = self.make_jsonrpc_request('/portal/notification/mark-all-read')
        self.assertTrue(res['success'])
        self.assertNotIn('error', res)
