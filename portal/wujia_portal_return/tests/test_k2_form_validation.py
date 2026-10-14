"""K2 — lỗi phía server render lại form Đổi trả: giữ mọi giá trị đã nhập, đánh dấu đúng ô lỗi."""
from lxml import html as lhtml

from odoo import http
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_base.controllers.portal import ACTIVE_FRANCHISE_COOKIE
from odoo.addons.wujia_return.tests.common import JPEG, ReturnFixture

from .common import load_vi

FORMS = '//form[@action="/portal/return/new"]'


@tagged('post_install', '-at_install', 'wujia_return_k2')
class TestK2ReturnFormValidation(HttpCase, ReturnFixture):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_vi(cls.env)
        cls._setup_return_data()
        cls.user = cls.env['res.users'].create({
            'name': 'k2_ret', 'login': 'k2_ret', 'password': 'k2_ret', 'lang': 'vi_VN',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        cls.env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.franchise.id, 'role': 'owner'})
        cls.line = cls.order_ok.order_line[0]

    def _post(self, images=0, **data):
        self.authenticate('k2_ret', 'k2_ret')
        self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(self.franchise.id))
        payload = {'franchise_id': self.franchise.id, 'sale_order_id': self.order_ok.id,
                   'sale_order_line_id': self.line.id, 'issue_type_id': self.issue_type.id,
                   'request_qty': '3', 'opening_datetime': '2026-09-01T08:00',
                   'production_date': '2026-08-20', 'note': 'K2 giữ ghi chú',
                   'csrf_token': http.Request.csrf_token(self)}
        payload.update(data)
        files = [('images', (f'p{i}.jpg', JPEG, 'image/jpeg')) for i in range(images)]
        res = self.url_open('/portal/return/new', data=payload, files=files or None,
                            timeout=30, allow_redirects=False)
        self.assertEqual(res.status_code, 200, 'lỗi phải render lại tại chỗ, không redirect')
        forms = lhtml.fromstring(res.text).xpath(FORMS)
        self.assertEqual(len(forms), 2)
        return forms

    @staticmethod
    def _shown_errors(form):
        return {p.get('id'): ' '.join(p.text_content().split())
                for p in form.xpath('.//p[contains(@class, "wj-field-error")][not(@hidden)]')}

    @staticmethod
    def _value(form, name):
        el = form.xpath(f'.//*[@name="{name}"][not(@type="hidden")]')[0]
        if el.tag == 'select':
            return [o.get('value') for o in el.xpath('./option[@selected]')]
        if el.tag == 'textarea':
            return el.text_content()
        return el.get('value')

    def test_missing_photos_keeps_every_value(self):
        before = self.env['wujia.return.request'].search_count([])
        for form, prefix in zip(self._post(images=2), ('wj-ret-pc', 'wj-ret-m')):
            self.assertEqual(self._shown_errors(form),
                             {f'{prefix}-images-err': 'Cần tải từ 3 đến 5 ảnh minh chứng.'})
            self.assertEqual(self._value(form, 'issue_type_id'), [str(self.issue_type.id)])
            self.assertEqual(self._value(form, 'sale_order_id'), [str(self.order_ok.id)])
            line = form.xpath('.//select[@name="sale_order_line_id"]')[0]
            self.assertEqual(line.get('data-selected'), str(self.line.id))
            self.assertEqual(self._value(form, 'request_qty'), '3')
            self.assertEqual(self._value(form, 'opening_datetime'), '2026-09-01T08:00')
            self.assertEqual(self._value(form, 'production_date'), '2026-08-20')
            self.assertEqual(self._value(form, 'note'), 'K2 giữ ghi chú')
        self.assertEqual(self.env['wujia.return.request'].search_count([]), before)

    def test_field_error_marks_only_that_field(self):
        for form, prefix in zip(self._post(images=3, request_qty='0'), ('wj-ret-pc', 'wj-ret-m')):
            self.assertEqual(list(self._shown_errors(form)), [f'{prefix}-qty-err'])
            self.assertIsNotNone(form.get('data-wj-validate'))
            self.assertEqual(len(form.xpath('.//*[@data-wj-error-summary]')), 1)

    def test_blank_form_renders_every_box(self):
        self.authenticate('k2_ret', 'k2_ret')
        self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(self.franchise.id))
        res = self.url_open('/portal/return/new', timeout=30, allow_redirects=False)
        forms = lhtml.fromstring(res.text).xpath(FORMS)
        for form in forms:
            self.assertEqual(len(form.xpath('.//textarea[@name="note"]')), 1)
            self.assertFalse(self._shown_errors(form))

    def test_photo_input_carries_model_limits(self):
        for form in self._post(images=2):
            img = form.xpath('.//input[@type="file"][@name="images"]')[0]
            self.assertEqual((img.get('data-wj-min-files'), img.get('data-wj-max-files')), ('3', '5'))
            self.assertEqual(img.get('data-wj-total-group'), 'evidence')
            self.assertTrue(img.get('data-wj-max-mb') and img.get('data-wj-total-mb'))
            vid = form.xpath('.//input[@type="file"][@name="video"]')[0]
            self.assertEqual(vid.get('data-wj-max-files'), '1')
