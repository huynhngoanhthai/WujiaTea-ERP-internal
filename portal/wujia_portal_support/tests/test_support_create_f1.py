"""F1 — POST /portal/support/new: input rác, danh mục, đính kèm. Chạy: `--test-tags wujia_f1`."""
from odoo import http
from odoo.tests import tagged
from odoo.tests.common import HttpCase

PDF = b'%PDF-1.4\n' + b'0' * 64


@tagged('post_install', '-at_install', 'wujia_f1')
class TestSupportCreateF1(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.franchise = env['wujia.franchise.management'].create({
            'code': 'F1SUP', 'name': 'F1 support store', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'F1 sup partner'}).id})
        cls.user = env['res.users'].create({
            'name': 'f1 sup', 'login': 'f1.sup', 'password': 'f1.sup',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
        env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.franchise.id, 'role': 'owner'})
        Cat = env['wujia.support.category']
        cls.cat = Cat.create({'name': 'F1 cat active'})
        cls.cat_archived = Cat.create({'name': 'F1 cat archived', 'active': False})
        cls.Ticket = env['wujia.support.ticket'].sudo()

    def _post(self, files=None, **data):
        self.authenticate('f1.sup', 'f1.sup')
        payload = {'franchise_id': self.franchise.id, 'category_id': self.cat.id,
                   'title': 'F1 ticket', 'csrf_token': http.Request.csrf_token(self)}
        payload.update(data)
        return self.url_open('/portal/support/new', data=payload, files=files,
                             allow_redirects=False)

    def _count(self):
        return self.Ticket.search_count([('created_by_id', '=', self.user.id)])

    def test_non_int_id_redirects_invalid_input(self):
        res = self._post(franchise_id='abc')
        self.assertEqual(res.status_code, 303)
        self.assertIn('error=invalid_input', res.headers['Location'])

    def test_archived_category_rejected(self):
        res = self._post(category_id=self.cat_archived.id)
        self.assertIn('error=invalid_input', res.headers['Location'])
        self.assertEqual(self._count(), 0)

    def test_html_attachment_rejected_without_ticket(self):
        res = self._post(files=[('attachments', ('x.html', b'<script>1</script>', 'text/html'))])
        self.assertIn('error=invalid_attachment', res.headers['Location'])
        self.assertEqual(self._count(), 0)
        self.assertFalse(self.env['ir.attachment'].sudo().search([('name', '=', 'x.html')]))

    def test_more_than_six_files_rejected(self):
        files = [('attachments', (f'f{i}.pdf', PDF, 'application/pdf')) for i in range(7)]
        res = self._post(files=files)
        self.assertIn('error=invalid_attachment', res.headers['Location'])
        self.assertEqual(self._count(), 0)

    def test_pdf_attachment_accepted(self):
        res = self._post(files=[('attachments', ('ok.pdf', PDF, 'application/pdf'))])
        ticket = self.Ticket.search([('created_by_id', '=', self.user.id)])
        self.assertEqual(len(ticket), 1)
        self.assertIn(f'/portal/support/{ticket.id}', res.headers['Location'])
        att = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'wujia.support.ticket'), ('res_id', '=', ticket.id)])
        self.assertEqual(att.mapped('mimetype'), ['application/pdf'])
