"""F1 — lỗi nội bộ không lộ ra portal, thông điệp trong query string được encode."""
from unittest.mock import patch

from odoo import http
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import load_vi


@tagged('post_install', '-at_install', 'wujia_f1')
class TestInfoRequestErrorsF1(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        load_vi(env)
        cls.franchise = env['wujia.franchise.management'].create({
            'code': 'F1IR', 'name': 'F1 ir store', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'F1 ir partner'}).id})
        cls.user = env['res.users'].create({
            'name': 'f1 ir', 'login': 'f1.ir', 'password': 'f1.ir', 'lang': 'vi_VN',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
        env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.franchise.id, 'role': 'owner'})
        cls.Model = type(env['wujia.info.update.request'])

    def _post_new(self):
        self.authenticate('f1.ir', 'f1.ir')
        return self.url_open('/portal/info-request/new', data={
            'franchise_id': self.franchise.id, 'request_type': 'owner_name',
            'new_value': 'F1 new', 'action': 'draft',
            'csrf_token': http.Request.csrf_token(self)})

    def test_generic_exception_is_not_leaked(self):
        with patch.object(self.Model, 'create', side_effect=Exception('SQL SECRET relation xyz')), \
                self.assertLogs('odoo.addons.wujia_portal_info_request.controllers.portal', 'ERROR'):
            body = self._post_new().text
        self.assertNotIn('SQL SECRET', body)
        self.assertIn('Không thể gửi yêu cầu', body)

    def test_validation_error_message_kept(self):
        with patch.object(self.Model, 'create', side_effect=ValidationError('F1 luật nghiệp vụ')):
            body = self._post_new().text
        self.assertIn('F1 luật nghiệp vụ', body)

    def test_cancel_error_message_is_url_encoded(self):
        rec = self.env['wujia.info.update.request'].create({
            'franchise_id': self.franchise.id, 'request_type': 'owner_name',
            'new_value': 'F1 v', 'created_by_user_id': self.user.id})
        self.authenticate('f1.ir', 'f1.ir')
        with patch.object(self.Model, 'action_cancel', side_effect=ValidationError('a&b#c')):
            res = self.url_open(f'/portal/info-request/{rec.id}/cancel',
                                data={'csrf_token': http.Request.csrf_token(self)},
                                allow_redirects=False)
        self.assertIn('message=a%26b%23c', res.headers['Location'])
