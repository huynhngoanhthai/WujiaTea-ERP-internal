"""F10 — route portal gọi luật model: phạm vi ticket, trả lời, tải đính kèm. Chạy: `--test-tags wujia_support`."""
from odoo import http
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_support.tests.test_support import SupportCommon


@tagged('post_install', '-at_install', 'wujia_support')
class TestPortalSupportF10(SupportCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_support()
        cls.mine = cls._ticket(title='F10 của tôi')
        cls.cancelled = cls._ticket(title='F10 đã huỷ', cancel_reason='x')
        cls.cancelled.action_cancel()
        cls.theirs = cls._ticket(user=cls.staff, title='F10 của nhân viên')
        cls.own_file = cls._pdf(res_model=cls.mine._name, res_id=cls.mine.id)
        cls.their_file = cls._pdf('their.pdf', res_model=cls.theirs._name, res_id=cls.theirs.id)
        cls.stray = cls._pdf('stray.pdf')
        cls.note_file = cls._pdf('note.pdf')
        cls.mine.message_post(
            body='F10 ghi chú nội bộ', message_type='comment',
            subtype_xmlid='mail.mt_note', attachment_ids=[cls.note_file.id])

    def setUp(self):
        super().setUp()
        self.authenticate('f10.owner', 'f10.owner')

    def test_list_shows_only_own_open_tickets(self):
        body = self.url_open('/portal/support').text
        self.assertIn('F10 của tôi', body)
        self.assertNotIn('F10 đã huỷ', body)
        self.assertNotIn('F10 của nhân viên', body)

    def test_other_users_ticket_redirects(self):
        res = self.url_open(f'/portal/support/{self.theirs.id}', allow_redirects=False)
        self.assertEqual(res.status_code, 303)
        self.assertTrue(res.headers['Location'].endswith('/portal/support'))
        res = self.url_open(f'/portal/support/{self.theirs.id}/reply', allow_redirects=False,
                            data={'body': 'chen ngang', 'csrf_token': http.Request.csrf_token(self)})
        self.assertTrue(res.headers['Location'].endswith('/portal/support'))
        self.assertNotIn('chen ngang', ''.join(self.theirs.message_ids.mapped('body')))

    def test_reply_posts_as_store_user(self):
        res = self.url_open(f'/portal/support/{self.mine.id}/reply', allow_redirects=False,
                            data={'body': 'Đã gửi ảnh', 'csrf_token': http.Request.csrf_token(self)})
        self.assertTrue(res.headers['Location'].endswith(f'/portal/support/{self.mine.id}'))
        msg = self.mine.message_ids[:1]
        self.assertIn('Đã gửi ảnh', msg.body)
        self.assertEqual(msg.author_id, self.owner.partner_id)
        self.assertEqual(self.mine.last_response_by, 'customer')

    def test_detail_lists_uploaded_files_and_hides_internal_notes(self):
        body = self.url_open(f'/portal/support/{self.mine.id}').text
        link = f'/portal/support/{self.mine.id}/attachment/{self.own_file.id}'
        self.assertEqual(body.count(link), 2, 'link tải ở cả PC lẫn mobile')
        self.assertNotIn('F10 ghi chú nội bộ', body)
        self.assertNotIn('note.pdf', body)
        self.assertEqual(self.url_open(
            f'/portal/support/{self.mine.id}/attachment/{self.note_file.id}').status_code, 403)

    def test_attachment_download_only_serves_ticket_files(self):
        base = f'/portal/support/{self.mine.id}/attachment/'
        self.assertEqual(self.url_open(base + str(self.own_file.id)).status_code, 200)
        self.assertEqual(self.url_open(base + str(self.stray.id)).status_code, 403)
        self.assertEqual(self.url_open(base + str(self.their_file.id)).status_code, 403)
        self.assertEqual(self.url_open(
            f'/portal/support/{self.theirs.id}/attachment/{self.own_file.id}').status_code, 404)

    def test_post_to_store_outside_scope_is_rejected(self):
        before = self.Ticket.search_count([])
        res = self.url_open('/portal/support/new', allow_redirects=False, data={
            'franchise_id': self.other_franchise.id, 'category_id': self.cat.id, 'title': 'lạc cửa hàng',
            'csrf_token': http.Request.csrf_token(self)})
        self.assertTrue(res.headers['Location'].endswith('/portal/support/new?error=invalid_franchise'))
        self.assertEqual(self.Ticket.search_count([]), before)
