"""E4c — màn Đăng ký thi: ô ngày phải LỌC THẬT và ngày ngược phải nói ra.

Lỗi BA nêu (`UI-FILTER-001`): thanh lọc mobile là khối dựng tay, hai ô ngày
không có `name` và nằm ngoài form nên bấm tìm không gửi gì — controller thì đã
nhận `date_from`/`date_to` từ lâu.

Chạy: `--test-tags wujia_filter_e4c`.
"""
import re
from datetime import datetime, timedelta

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_base.controllers.utils import ERR_DATE_RANGE


@tagged('post_install', '-at_install', 'wujia_filter_e4c')
class TestExamFilterDatesE4c(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.slot = env['wujia.exam.time.slot'].create({
            'name': 'E4C 08:00-10:00', 'code': 'E4C-0810',
            'time_from': 8.0, 'time_to': 10.0,
        })
        cls.course = env['wujia.exam.course'].create({
            'name': 'E4C course', 'time_slot_ids': [(6, 0, cls.slot.ids)],
        })
        cls.course.action_publish()
        # KHÔNG đặt tên `cls.session`: HttpCase đã có `self.session` (phiên HTTP),
        # đè vào là đăng nhập nổ 'object has no attribute sid'.
        cls.exam_session = env['wujia.exam.session'].create({
            'course_id': cls.course.id, 'time_slot_id': cls.slot.id,
            'exam_date': '2026-12-01', 'capacity': 50,
        })
        cls.exam_session.action_open()
        cls.franchise = env['wujia.franchise.management'].create({
            'code': 'E4C1', 'name': 'E4C store',
            'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'E4C partner'}).id,
        })
        cls.user = env['res.users'].create({
            'name': 'e4c_exam', 'login': 'e4c_exam', 'password': 'e4c_exam',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])],
        })
        env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.franchise.id,
            'role': 'owner',
        })
        # Hai phiếu cách nhau 60 ngày để mọi khoảng lọc hẹp chỉ trúng một phiếu.
        cls.old = cls._reg(datetime(2026, 1, 15, 3, 0))
        cls.recent = cls._reg(datetime(2026, 3, 16, 3, 0))

    @classmethod
    def _reg(cls, when):
        reg = cls.env['wujia.exam.registration'].create({
            'session_id': cls.exam_session.id, 'franchise_id': cls.franchise.id,
            'requester_user_id': cls.user.id,
            'line_ids': [(0, 0, {'employee_name': 'NV %s' % when.day,
                                 'phone': '0900000%03d' % when.day})],
        })
        reg.request_date = when
        return reg

    @property
    def err_date_range(self):
        """J-V2: ERR_DATE_RANGE là `_lt` ⇒ so đúng câu user thấy theo ngôn ngữ của user."""
        return self.env(context=dict(self.env.context, lang=self.user.lang))._(ERR_DATE_RANGE)

    def _get(self, url):
        self.authenticate('e4c_exam', 'e4c_exam')
        res = self.url_open(url, timeout=30)
        self.assertEqual(res.status_code, 200)
        return res.text

    def test_khoang_ngay_hep_chi_ra_phieu_trong_khoang(self):
        html = self._get('/portal/exam?date_from=2026-01-01&date_to=2026-01-31')
        self.assertIn(self.old.name, html)
        self.assertNotIn(self.recent.name, html)

    def test_khong_loc_thi_ra_ca_hai_phieu(self):
        html = self._get('/portal/exam')
        self.assertIn(self.old.name, html)
        self.assertIn(self.recent.name, html)

    def test_ngay_nguoc_bao_loi_va_khong_chay_query(self):
        html = self._get('/portal/exam?date_from=2026-09-30&date_to=2026-09-01')
        self.assertIn(self.err_date_range, html)
        self.assertNotIn(self.old.name, html)
        self.assertNotIn(self.recent.name, html)
        # Giữ nguyên chữ đã gõ, đừng bắt người dùng nhập lại.
        self.assertIn('value="2026-09-30"', html)
        self.assertIn('value="2026-09-01"', html)

    def test_o_bao_loi_luon_ton_tai_va_an_khi_khong_loi(self):
        """Mất phần tử là JS thay khối hụt id ⇒ cả màn rơi về tải lại trang."""
        html = self._get('/portal/exam')
        for eid in ('wj-exam-pcerr', 'wj-exam-merr'):
            tag = re.search(r'<p id="%s"[^>]*>' % eid, html)
            self.assertTrue(tag, 'thiếu ô báo lỗi %s' % eid)
            self.assertIn('hidden', tag.group(0))

    def test_thanh_loc_mobile_gui_duoc_hai_o_ngay(self):
        """Khối dựng tay cũ thiếu `name` — gửi đi là mất hút, không lọc gì."""
        html = self._get('/portal/exam')
        forms = re.findall(r'<form[^>]*wj-filter-card.*?</form>', html, re.S)
        self.assertEqual(len(forms), 1, 'thanh lọc mobile không còn là một form')
        self.assertIn('name="date_from"', forms[0])
        self.assertIn('name="date_to"', forms[0])
        self.assertIn('action="/portal/exam"', forms[0])
