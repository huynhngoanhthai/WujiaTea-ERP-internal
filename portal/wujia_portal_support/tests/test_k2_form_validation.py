"""K2 — lỗi phía server render lại form tạo Hỗ trợ: giữ giá trị, đánh dấu đúng ô, có hộp tổng lỗi."""
from lxml import html as lhtml

from odoo import http
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_base.controllers.portal import ACTIVE_FRANCHISE_COOKIE
from odoo.addons.wujia_support.tests.common import load_vi
from odoo.addons.wujia_support.tests.test_support import SupportCommon

from .test_k1_form_detail import M_FORM, PC_FORM, SUPPORT_MODULES


@tagged('post_install', '-at_install', 'wujia_support', 'wujia_support_k2')
class TestK2SupportFormValidation(SupportCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_support()
        load_vi(cls.env, SUPPORT_MODULES)
        cls.owner.lang = 'vi_VN'

    def _post(self, **data):
        self.authenticate('f10.owner', 'f10.owner')
        self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(self.franchise.id))
        payload = {'franchise_id': self.franchise.id, 'category_id': self.cat.id, 'title': 'K2 ticket',
                   'description': 'Máy pha bị rò nước', 'priority': 'urgent',
                   'csrf_token': http.Request.csrf_token(self)}
        payload.update(data)
        res = self.url_open('/portal/support/new', data=payload, timeout=30, allow_redirects=False)
        self.assertEqual(res.status_code, 200, 'lỗi phải render lại tại chỗ, không redirect')
        doc = lhtml.fromstring(res.text)
        return doc.xpath(PC_FORM)[0], doc.xpath(M_FORM)[0]

    @staticmethod
    def _shown_errors(form):
        return sorted(p.get('id') for p in form.xpath('.//p[contains(@class, "wj-field-error")][not(@hidden)]'))

    def test_missing_title_keeps_values_and_marks_only_title(self):
        before = self.Ticket.search_count([])
        for form, prefix in zip(self._post(title='  '), ('wj-sup-pc', 'wj-sup-m')):
            self.assertEqual(self._shown_errors(form), [f'{prefix}-title-err'])
            self.assertEqual(form.xpath('.//textarea[@name="description"]')[0].text_content(), 'Máy pha bị rò nước')
            cat = form.xpath('.//select[@name="category_id"]/option[@selected]')
            self.assertEqual([o.get('value') for o in cat], [str(self.cat.id)])
            prio = form.xpath('.//select[@name="priority"]/option[@selected]/@value'
                              ' | .//input[@name="priority"][@checked]/@value')
            self.assertEqual(prio, ['urgent'])
        self.assertEqual(self.Ticket.search_count([]), before)

    def test_summary_box_translated_on_both_forms(self):
        for form in self._post(title=''):
            self.assertIsNotNone(form.get('data-wj-validate'))
            box = form.xpath('.//*[@data-wj-error-summary]')
            self.assertEqual(len(box), 1)
            self.assertEqual(box[0].get('role'), 'alert')
            self.assertEqual(box[0].get('data-wj-msg-title'), 'Vui lòng sửa {n} trường bên dưới.')

    def test_file_input_carries_server_limits(self):
        for form in self._post(title=''):
            inp = form.xpath('.//input[@type="file"][@name="attachments"]')[0]
            self.assertEqual((inp.get('data-wj-max-files'), inp.get('data-wj-max-mb')), ('6', '5'))
            self.assertTrue(inp.get('accept'))
