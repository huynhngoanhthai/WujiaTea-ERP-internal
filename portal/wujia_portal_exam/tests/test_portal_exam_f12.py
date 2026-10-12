"""F12 — route Đăng ký thi gọi luật model: lịch/khung giờ, gửi phiếu (mã lỗi + câu báo giữ nguyên), phạm vi cửa hàng.
Chạy: `--test-tags wujia_exam`. Luật model test ở `wujia_exam`."""
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_exam.tests.test_portal_rules import ExamCommon, png_b64
from odoo.addons.wujia_portal_exam.controllers.portal import _max_hint

# J-V3: nhãn/câu báo portal nằm ở .po của khung + portal_base + 2 module Thi.
VI_MODULES = ('wujia_portal_layout', 'wujia_portal_base', 'wujia_exam', 'wujia_portal_exam')


@tagged('post_install', '-at_install', 'wujia_exam')
class TestPortalExamF12(ExamCommon, HttpCase):

    _vi_modules = VI_MODULES

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_exam(login='f12.portal')
        cls.Reg = cls.env['wujia.exam.registration'].sudo()

    def setUp(self):
        super().setUp()
        self.authenticate('f12.portal', 'f12.portal')

    def _submit(self, session_id, people, **kw):
        return self.make_jsonrpc_request('/portal/exam/register', {
            'session_id': session_id, 'participants': people, **kw})

    def test_max_hint(self):
        self.assertIn('2', _max_hint(2))
        self.assertNotIn('4', _max_hint(2))
        # Gọi trần (không request/env) ⇒ câu gốc tiếng Anh; vi_VN đọc qua env của user.
        hint = _max_hint(0)
        self.assertIn('Choose an exam course', hint)
        self.assertIn('Chọn khóa thi', self.env._(hint))

    def test_calendar_and_slots(self):
        cal = self.make_jsonrpc_request('/portal/exam/calendar', {
            'course_id': self.course.id, 'year': self.day.year, 'month': self.day.month})['calendar']
        cell = next(c for w in cal['weeks'] for c in w if c['in_month'] and c['day'] == self.day.day)
        self.assertEqual(cell['state'], 'available')
        slots = self.make_jsonrpc_request('/portal/exam/slots', {
            'course_id': self.course.id, 'exam_date': self.day.isoformat()})['slots']
        self.assertEqual([(s['status'], s['available'], s['max_per_reg']) for s in slots], [
            ('Còn 20 chỗ', True, 2), ('Hết chỗ', False, 2), ('Hết hạn', False, 2), ('Đã đóng', False, 2)])

    def test_submit_success_redirects_to_detail(self):
        res = self._submit(self.open.id, [self._person(1, photo='data:image/png;base64,' + png_b64())], note='F12')
        reg = self.Reg.search([('franchise_id', '=', self.store_a.id), ('note', '=', 'F12')])
        self.assertEqual(res, {'success': True, 'redirect': '/portal/exam/registration/%d' % reg.id})
        page = self.url_open(res['redirect'])
        self.assertIn(reg.name, page.text)
        photo = self.url_open('/portal/exam/line/%d/photo' % reg.line_ids.id)
        self.assertEqual((photo.status_code, photo.headers['Content-Type']), (200, 'image/png'))

    def test_submit_error_codes(self):
        before = self.Reg.search_count([])
        self.assertEqual(self._submit(0, [self._person(1)]), {
            'error': 'not_found', 'message': 'Khung giờ đã thay đổi hoặc không còn. Vui lòng chọn lại lịch thi.'})
        self.assertEqual(self._submit(self.open.id, []), {'error': 'validation', 'message': 'Cần ít nhất 1 người dự thi.'})
        self.assertEqual(self._submit(self.open.id, [self._person(i) for i in range(3)]),
                         {'error': 'validation', 'message': 'Tối đa 2 người mỗi phiếu.'})
        self.assertEqual(self._submit(self.open.id, [self._person(1, phone='12')]), {
            'error': 'validation', 'message': "Số điện thoại '12' không hợp lệ (vd 0901234567)."})
        full = self._submit(self.full.id, [self._person(1)])
        self.assertEqual(full['error'], 'business')
        self.assertIn('giữ chỗ', full['message'])  # constraint sức chứa của kỳ thi, rollback sạch
        self.assertEqual(self._submit(self.expired.id, [self._person(1)])['error'], 'business')
        self.assertEqual(self.Reg.search_count([]), before)

    def test_other_store_is_out_of_scope(self):
        # Dòng có ảnh ⇒ 404 là do phạm vi cửa hàng, không phải do thiếu ảnh.
        other = self._reg(self.open, [self._person(7, image_1920=png_b64())], store=self.store_b)
        page = self.url_open('/portal/exam/registration/%d' % other.id, allow_redirects=False)
        self.assertEqual((page.status_code, page.headers['Location'].endswith('/portal/exam')), (303, True))
        self.assertEqual(self.url_open('/portal/exam/line/%d/photo' % other.line_ids.id).status_code, 404)
        self.assertNotIn(other.name, self.url_open('/portal/exam').text)
