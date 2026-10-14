"""K2 — đăng ký thi: modal PC + bước người thi mobile dùng ô lỗi + hộp tổng lỗi chung."""
from lxml import html as lhtml

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_exam.tests.test_portal_rules import ExamCommon
from odoo.addons.wujia_portal_base.controllers.portal import ACTIVE_FRANCHISE_COOKIE

from .test_i8_photo_state import VI_MODULES


@tagged('post_install', '-at_install', 'wujia_exam_k2')
class TestK2ExamFormValidation(ExamCommon, HttpCase):

    _vi_modules = VI_MODULES

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_exam(login='k2.exam')

    def _doc(self):
        self.authenticate('k2.exam', 'k2.exam')
        self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(self.store_a.id))
        res = self.url_open('/portal/exam/register', timeout=30, allow_redirects=False)
        self.assertEqual(res.status_code, 200)
        return lhtml.fromstring(res.text)

    def test_pc_modal_fields_linked_to_errors(self):
        modal = self._doc().xpath('//div[@data-wj-exam-modal="participant"]')[0]
        self.assertEqual(len(modal.xpath('.//*[@data-wj-error-summary]')), 1)
        for ctrl_id in ('wj_exam_p_name', 'wj_exam_p_phone'):
            err = modal.xpath('.//p[@id="%s-err"]' % ctrl_id)
            self.assertEqual(len(err), 1, ctrl_id)
            self.assertIsNotNone(err[0].get('hidden'))
            self.assertIsNotNone(modal.xpath('.//input[@id="%s"]' % ctrl_id)[0].get('required'))
        self.assertEqual(modal.xpath('.//input[@id="wj_exam_p_phone"]/@pattern'), [r'(0|\+84)[0-9]{8,10}'])

    def test_mobile_person_has_field_errors(self):
        doc = self._doc()
        step = doc.xpath('//section[@data-exam-step="3"]')[0]
        self.assertEqual(len(step.xpath('.//*[@data-wj-error-summary]')), 1)
        person = step.xpath('.//*[@data-exam-person]')[0]
        self.assertEqual(sorted(person.xpath('.//input[@data-exam-pfield]/@data-exam-pfield')), ['name', 'phone'])
        self.assertEqual(sorted(person.xpath('.//p[@data-exam-perr]/@data-exam-perr')), ['name', 'phone'])
        wizard = doc.xpath('//div[contains(@class, "wujia-mexam-wizard")]')[0]
        self.assertEqual(wizard.get('data-wj-msg-lbl-phone'), 'Số điện thoại')
