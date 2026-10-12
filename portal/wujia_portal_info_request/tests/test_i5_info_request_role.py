from odoo.tests import tagged

from odoo.addons.wujia_portal_base.tests.test_i5_store_role import NO_PERMISSION, I5Common


@tagged('post_install', '-at_install', 'wujia_role_i5')
class TestInfoRequestRole(I5Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Model = cls.env['wujia.info.update.request']
        cls.req_a, cls.req_b = (Model.create({
            'franchise_id': store.id, 'request_type': 'phone', 'new_value': '0909',
            'created_by_user_id': cls.mix.id,
        }) for store in (cls.store_a, cls.store_b))
        att = cls.env['ir.attachment'].create({
            'name': 'i5.txt', 'raw': b'i5', 'res_model': Model._name, 'res_id': cls.req_b.id})
        cls.req_b.attachment_ids = [(4, att.id)]
        cls.att_b = att

    def test_admin_at_selected_store(self):
        for login in ('i5.mix', 'i5.mgr'):
            for url in ('/portal/info-request', '/portal/info-request/new',
                        '/portal/info-request/%s' % self.req_a.id):
                res = self._open(url, self.store_a, login)
                self.assertEqual(res.status_code, 200, url)
                self.assertNotIn(NO_PERMISSION, res.text)
        ajax = self.make_jsonrpc_request(
            '/portal/info-request/franchise/%s/values' % self.store_a.id, {'request_type': 'phone'})
        self.assertNotIn('error', ajax)

    def test_owner_elsewhere_is_staff_here(self):
        for url in ('/portal/info-request', '/portal/info-request/new',
                    '/portal/info-request/%s' % self.req_b.id,
                    '/portal/info-request/%s' % self.req_a.id):
            res = self._open(url, self.store_b)
            self.assertEqual(res.status_code, 403, url)
            self.assertIn(NO_PERMISSION, res.text)
            self.assertNotIn(self.req_b.name, res.text)
        post = self._post('/portal/info-request/new', self.store_b, {
            'franchise_id': self.store_b.id, 'request_type': 'phone', 'new_value': '0911',
            'action': 'submit'})
        self.assertEqual(post.status_code, 403)
        cancel = self._post('/portal/info-request/%s/cancel' % self.req_b.id, self.store_b, {})
        self.assertEqual(cancel.status_code, 403)
        self.assertNotEqual(self.req_b.state, 'cancel')
        self.assertEqual(self.env['wujia.info.update.request'].search_count(
            [('franchise_id', '=', self.store_b.id)]), 1)
        att = self._open('/portal/info-request/%s/attachment/%s' % (self.req_b.id, self.att_b.id),
                         self.store_b)
        self.assertEqual(att.status_code, 404)
        ajax = self.make_jsonrpc_request(
            '/portal/info-request/franchise/%s/values' % self.store_b.id, {'request_type': 'phone'})
        self.assertEqual(ajax, {'error': 'forbidden'})
