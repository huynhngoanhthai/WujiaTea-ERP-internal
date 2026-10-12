"""F8 — controller mỏng: gửi thật qua portal vẫn cho đúng kết quả cũ."""
from odoo import http
from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged('post_install', '-at_install', 'wujia_f8')
class TestInfoRequestPortalF8(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.franchise = env['wujia.franchise.management'].create({
            'code': 'F8PT', 'name': 'F8 portal store', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'F8 portal partner'}).id})
        for role in ('owner', 'staff'):
            user = env['res.users'].create({
                'name': f'f8p {role}', 'login': f'f8p.{role}', 'password': f'f8p.{role}',
                'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
            env['wujia.franchise.member'].create({
                'user_id': user.id, 'franchise_id': cls.franchise.id, 'role': role})
        cls.Model = env['wujia.info.update.request']

    def _post(self, login, files=None, **data):
        self.authenticate(login, login)
        data = dict({'franchise_id': self.franchise.id, 'request_type': 'phone', 'new_value': '0909',
                     'action': 'submit', 'csrf_token': http.Request.csrf_token(self)}, **data)
        return self.url_open('/portal/info-request/new', data=data, files=files, allow_redirects=False)

    def test_submit_with_attachment(self):
        res = self._post('f8p.owner', files={'attachments': ('cmnd.png', b'\x89PNG f8', 'image/png')})
        rec = self.Model.search([('franchise_id', '=', self.franchise.id)])
        self.assertEqual(res.headers['Location'].split('/portal')[-1], f'/info-request/{rec.id}?message=created')
        self.assertEqual((rec.state, rec.attachment_ids.mapped('name')), ('submitted', ['cmnd.png']))

    def test_bad_attachment_leaves_nothing(self):
        res = self._post('f8p.owner', files={'attachments': ('x.exe', b'MZ', 'application/x-msdownload')})
        self.assertEqual(res.status_code, 200)
        self.assertIn('không hỗ trợ', res.text)
        self.assertFalse(self.Model.search([('franchise_id', '=', self.franchise.id)]))

    def test_staff_is_forbidden(self):
        self.authenticate('f8p.staff', 'f8p.staff')
        self.assertEqual(self.url_open('/portal/info-request/new').status_code, 403)
