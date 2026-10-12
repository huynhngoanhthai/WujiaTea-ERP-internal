"""Đăng ký thi: nhắc chọn cửa hàng, "Chờ xác nhận" PC = mobile, "Có kết quả" tách khỏi trạng thái phiếu.

Chạy: `--test-tags wujia_scope_i4b`.
"""
import re
from datetime import timedelta

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_exam.tests.test_portal_rules import ExamCommon
from odoo.addons.wujia_portal_base.controllers.portal import ACTIVE_FRANCHISE_COOKIE

VI_MODULES = ('wujia_portal_layout', 'wujia_portal_base', 'wujia_exam', 'wujia_portal_exam')
PROMPT_NEED_PICK = 'data-store-scope="need_pick"'
PC_STATE = re.compile(r'wj-exam-pc-td--badge">\s*<span class="wj-status-badge [\w-]+">([^<]+)</span>')
M_STATE = re.compile(r'<span class="wj-status-badge wj-status-badge--compact [\w-]+">([^<]+)</span>')
CHIP = 'wj-exam-result-chip'


@tagged('post_install', '-at_install', 'wujia_scope_i4b')
class TestExamI4b(ExamCommon, HttpCase):

    _vi_modules = VI_MODULES

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_exam(login='i4b.exam')
        cls.env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.store_b.id, 'role': 'owner'})
        p = [cls._person(9)]
        cls.wait_session = cls._session(cls.open.time_slot_id, exam_date=cls.day + timedelta(days=1))
        cls.wait_session.action_open()
        cls.r_wait = cls._reg(cls.wait_session, p)
        cls.r_ok, cls.r_rej, cls.r_cancel = (cls._reg(cls.open, p) for _ in range(3))
        cls.r_ok.write({'state': 'confirmed'})
        cls.r_rej.write({'state': 'rejected', 'reject_reason': 'I4B'})
        cls.r_cancel.write({'state': 'cancelled', 'cancellation_reason': 'I4B'})
        cls.r_b = cls._reg(cls.open, p, store=cls.store_b)
        cls.open.write({'results_published': True})

    def _open(self, url, store=None):
        self.authenticate('i4b.exam', 'i4b.exam')
        if store is not None:
            self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(store.id))
        return self.url_open(url, timeout=30, allow_redirects=False)

    def test_not_selected_prompt_not_empty_state(self):
        html = self._open('/portal/exam').text
        self.assertIn(PROMPT_NEED_PICK, html)
        self.assertNotIn('Chưa có đăng ký thi', html)
        for reg in (self.r_wait, self.r_ok, self.r_b):
            self.assertNotIn(reg.name, html)

    def test_same_state_labels_pc_and_mobile(self):
        html = self._open('/portal/exam', self.store_a).text
        pc, mobile = PC_STATE.findall(html), M_STATE.findall(html)
        self.assertEqual(pc, mobile)
        # + 1 phiếu chờ của kỳ `full` dựng sẵn trong ExamCommon.
        self.assertCountEqual(pc, ['Chờ xác nhận', 'Chờ xác nhận', 'Đã đăng ký', 'Từ chối', 'Đã hủy'])
        self.assertNotIn('Chờ duyệt', html)
        self.assertNotIn(self.r_b.name, html)

    def test_result_is_separate_from_state(self):
        html = self._open('/portal/exam', self.store_a).text
        self.assertEqual(html.count(CHIP), 1, 'chỉ phiếu Đã đăng ký của kỳ đã công bố')
        detail = self._open('/portal/exam/registration/%d' % self.r_ok.id, self.store_a).text
        self.assertIn(CHIP, detail)
        self.assertIn('Đã đăng ký', detail)
        for reg, label in ((self.r_rej, 'Từ chối'), (self.r_cancel, 'Đã hủy')):
            detail = self._open('/portal/exam/registration/%d' % reg.id, self.store_a).text
            self.assertNotIn(CHIP, detail)
            self.assertIn(label, detail)

    def test_filters_and_store_b(self):
        html = self._open('/portal/exam?state=submitted', self.store_a).text
        self.assertEqual(PC_STATE.findall(html), ['Chờ xác nhận', 'Chờ xác nhận'])
        html = self._open('/portal/exam?result=published', self.store_a).text
        self.assertEqual(len(PC_STATE.findall(html)), 3)
        html = self._open('/portal/exam', self.store_b).text
        self.assertIn(self.r_b.name, html)
        self.assertNotIn(self.r_ok.name, html)
