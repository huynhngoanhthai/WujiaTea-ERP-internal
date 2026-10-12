"""WJ-EXAM-008: modal Thêm người PC mở ở trạng thái "chưa chọn ảnh" — không kèm nhãn "đã chọn".

Hành vi JS (chọn ⇒ đã chọn, xoá ⇒ chưa chọn, validation giữ trạng thái) đo bằng Playwright (`i8_measure.py`).
Chạy: `--test-tags wujia_exam_i8`.
"""
from lxml import html as lhtml

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_exam.tests.test_portal_rules import ExamCommon
from odoo.addons.wujia_portal_base.controllers.portal import ACTIVE_FRANCHISE_COOKIE

VI_MODULES = ('wujia_portal_layout', 'wujia_portal_base', 'wujia_exam', 'wujia_portal_exam')


@tagged('post_install', '-at_install', 'wujia_exam_i8')
class TestExamPhotoState(ExamCommon, HttpCase):

    _vi_modules = VI_MODULES

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_exam(login='i8.exam')

    def _box(self):
        self.authenticate('i8.exam', 'i8.exam')
        self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(self.store_a.id))
        res = self.url_open('/portal/exam/register', timeout=30, allow_redirects=False)
        self.assertEqual(res.status_code, 200)
        doc = lhtml.fromstring(res.text)
        boxes = doc.xpath('//div[contains(concat(" ", @class, " "), " wj-exam-pc-photobox ")]')
        self.assertEqual(len(boxes), 1)
        return doc, boxes[0]

    def test_default_is_empty_state_only(self):
        _doc, box = self._box()
        self.assertIn('is-empty', box.get('class').split())
        title = box.xpath('.//p[contains(@class, "wj-exam-pc-photobox__title")]')[0]
        self.assertEqual(title.text_content().strip(), 'Chưa chọn ảnh')
        text = box.text_content()
        self.assertNotIn('Ảnh đã được chọn', text)
        self.assertNotIn('Photo selected', text)
        # không còn tên tệp mẫu viết cứng
        self.assertNotIn('anh-nguyen-van-an', text)
        file_line = box.xpath('.//p[contains(@class, "wj-exam-pc-photobox__file")]')[0]
        self.assertIsNotNone(file_line.get('hidden'))
        self.assertEqual(file_line.text_content().strip(), '')

    def test_empty_state_actions(self):
        _doc, box = self._box()
        pick = box.xpath('.//button[contains(@class, "wj-exam-pc-photobtn") '
                         'and not(contains(@class, "wj-exam-pc-photobtn--del"))]')[0]
        self.assertEqual(pick.text_content().strip(), 'Chọn ảnh')
        delete = box.xpath('.//button[contains(@class, "wj-exam-pc-photobtn--del")]')[0]
        self.assertIsNotNone(delete.get('hidden'))

    def test_js_state_labels_translated(self):
        doc, _box = self._box()
        root = doc.xpath('//*[@data-wj-msg-photo-selected]')[0]
        self.assertEqual(root.get('data-wj-msg-photo-selected'), 'Ảnh đã được chọn')
        self.assertEqual(root.get('data-wj-msg-photo-none'), 'Chưa chọn ảnh')
        self.assertEqual(root.get('data-wj-msg-photo-choose'), 'Chọn ảnh')
        self.assertEqual(root.get('data-wj-msg-photo-change'), 'Thay ảnh')
