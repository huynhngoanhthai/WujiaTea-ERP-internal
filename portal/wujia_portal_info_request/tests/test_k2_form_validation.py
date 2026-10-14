"""K2 — lỗi form tạo yêu cầu cập nhật thông tin: đánh dấu đúng ô, giữ giá trị, hộp tổng lỗi."""
from lxml import html as lhtml

from odoo import http
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import load_vi


@tagged('post_install', '-at_install', 'wujia_info_request_k2')
class TestK2InfoRequestFormValidation(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        load_vi(env)
        cls.franchise = env['wujia.franchise.management'].create({
            'code': 'K2IR', 'name': 'K2 ir store', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'K2 ir partner'}).id})
        cls.user = env['res.users'].create({
            'name': 'k2 ir', 'login': 'k2.ir', 'password': 'k2.ir', 'lang': 'vi_VN',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
        env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.franchise.id, 'role': 'owner'})
        cls.Model = env['wujia.info.update.request']

    def _post(self, **data):
        self.authenticate('k2.ir', 'k2.ir')
        payload = {'franchise_id': self.franchise.id, 'request_type': 'phone', 'new_value': '0901234567',
                   'note': 'Đổi số mới', 'priority': 'urgent', 'action': 'submit',
                   'csrf_token': http.Request.csrf_token(self)}
        payload.update(data)
        res = self.url_open('/portal/info-request/new', data=payload, timeout=30, allow_redirects=False)
        self.assertEqual(res.status_code, 200)
        return lhtml.fromstring(res.text).xpath('//form[@id="info-request-form"]')[0]

    @staticmethod
    def _shown(form):
        return sorted(p.get('id') for p in form.xpath('.//p[contains(@class, "wj-field-error")][not(@hidden)]'))

    def test_missing_new_value_marks_field_and_keeps_values(self):
        before = self.Model.search_count([])
        form = self._post(new_value='  ')
        self.assertEqual(self._shown(form), ['info-new-value-err'])
        ctrl = form.xpath('.//textarea[@name="new_value"]')[0]
        self.assertEqual((ctrl.get('aria-invalid'), ctrl.get('aria-describedby')), ('true', 'info-new-value-err'))
        self.assertEqual(form.xpath('.//textarea[@name="note"]')[0].text_content(), 'Đổi số mới')
        self.assertEqual(form.xpath('.//select[@name="request_type"]/option[@selected]/@value'), ['phone'])
        self.assertEqual(form.xpath('.//select[@name="priority"]/option[@selected]/@value'), ['urgent'])
        self.assertEqual(self.Model.search_count([]), before)

    def test_all_empty_fields_marked_at_once(self):
        form = self._post(franchise_id='', request_type='', new_value='')
        self.assertEqual(self._shown(form),
                         ['info-franchise-id-err', 'info-new-value-err', 'info-request-type-err'])

    def test_other_requires_field_target(self):
        form = self._post(request_type='other', field_target='')
        self.assertEqual(self._shown(form), ['info-field-target-err'])
        self.assertIsNotNone(form.xpath('.//input[@name="field_target"]')[0].get('required'))

    def test_summary_and_file_rules(self):
        form = self._post(new_value='')
        self.assertIsNotNone(form.get('data-wj-validate'))
        box = form.xpath('.//*[@data-wj-error-summary]')
        self.assertEqual(box[0].get('data-wj-msg-title'), 'Vui lòng sửa {n} trường bên dưới.')
        inp = form.xpath('.//input[@name="attachments"]')[0]
        self.assertEqual((inp.get('data-wj-max-files'), inp.get('data-wj-max-mb')), ('6', '5'))
