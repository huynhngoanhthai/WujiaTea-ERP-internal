"""Test nghiệp vụ Support — F10. Chạy: `--test-tags wujia_support`.

Mã ticket, mốc ngày theo trạng thái, lý do huỷ, phân tích phản hồi cửa hàng/HQ, và luật portal
dùng chung (`_portal_scope_domain`, `create_from_portal`, `_portal_reply`, `_portal_get_attachment`).
`SupportCommon` dùng lại ở test portal.
"""
import base64

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


class SupportCommon:

    @classmethod
    def _setup_support(cls):
        env = cls.env
        env['res.lang']._activate_lang('vi_VN')  # như UAT; DB copy cũ để admin vi_VN mà lang chưa bật
        cls.franchise = env['wujia.franchise.management'].create({
            'code': 'F10SUP', 'name': 'F10 support store', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'F10 sup partner'}).id})
        cls.other_franchise = env['wujia.franchise.management'].create({
            'code': 'F10OTH', 'name': 'F10 other store', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'F10 other partner'}).id})
        portal = env.ref('base.group_portal')
        cls.owner = env['res.users'].create({
            'name': 'f10 owner', 'login': 'f10.owner', 'password': 'f10.owner',
            'group_ids': [(6, 0, [portal.id])]})
        cls.staff = env['res.users'].create({
            'name': 'f10 staff', 'login': 'f10.staff', 'password': 'f10.staff',
            'group_ids': [(6, 0, [portal.id])]})
        cls.hq = env['res.users'].create({
            'name': 'f10 hq', 'login': 'f10.hq', 'lang': 'en_US',
            'group_ids': [(6, 0, [env.ref('base.group_user').id])]})
        Member = env['wujia.franchise.member']
        Member.create({'user_id': cls.owner.id, 'franchise_id': cls.franchise.id, 'role': 'owner'})
        Member.create({'user_id': cls.staff.id, 'franchise_id': cls.franchise.id, 'role': 'staff'})
        Cat = env['wujia.support.category']
        cls.cat = Cat.create({'name': 'F10 cat active'})
        cls.cat_archived = Cat.create({'name': 'F10 cat archived', 'active': False})
        cls.Ticket = env['wujia.support.ticket'].sudo()

    @classmethod
    def _ticket(cls, user=None, **vals):
        user = user or cls.owner
        return cls.Ticket.create(dict({
            'title': 'F10 ticket', 'franchise_id': cls.franchise.id,
            'created_by_id': user.id, 'category_id': cls.cat.id,
        }, **vals))

    @classmethod
    def _pdf(cls, name='f10.pdf', **vals):
        return cls.env['ir.attachment'].create(dict({
            'name': name, 'mimetype': 'application/pdf',
            'datas': base64.b64encode(b'%PDF-1.4 f10')}, **vals))


@tagged('post_install', '-at_install', 'wujia_support')
class TestSupportTicket(SupportCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_support()

    def _portal_vals(self, **kw):
        return dict({'title': 'Máy POS lỗi', 'description': 'Không in được bill',
                     'franchise_id': self.franchise.id, 'created_by_id': self.owner.id,
                     'category_id': self.cat.id, 'priority': 'urgent'}, **kw)

    # --- nghiệp vụ gốc ------------------------------------------------------
    def test_code_role_and_open_date(self):
        t = self._ticket()
        self.assertRegex(t.name, r'^WJ-TK/\d{2}/\d{5}$')
        self.assertTrue(t.open_date)
        self.assertEqual(t.created_by_role, 'owner')
        self.assertEqual(self._ticket(user=self.staff).created_by_role, 'staff')

    def test_state_transitions_stamp_dates(self):
        t = self._ticket()
        t.action_set_in_progress()
        self.assertEqual(t.state, 'in_progress')
        self.assertTrue(t.in_progress_date)
        t.action_set_resolved()
        self.assertTrue(t.resolved_date)
        t.action_set_closed()
        self.assertEqual(t.state, 'closed')
        self.assertTrue(t.closed_date)

    def test_cancel_needs_reason(self):
        t = self._ticket()
        with self.assertRaises(ValidationError):
            t.action_cancel()
        t.cancel_reason = 'Trùng'
        t.action_cancel()
        self.assertEqual(t.state, 'cancelled')

    # --- luật portal --------------------------------------------------------
    def test_scope_domain_is_own_visible_tickets(self):
        mine = self._ticket()
        hidden = self._ticket(portal_visible=False)
        theirs = self._ticket(user=self.staff)
        other_store = self._ticket(franchise_id=self.other_franchise.id)
        found = self.Ticket.search(self.Ticket._portal_scope_domain(self.owner, (self.franchise.id,)))
        self.assertIn(mine, found)
        self.assertNotIn(hidden, found)
        self.assertNotIn(theirs, found)
        self.assertNotIn(other_store, found)
        self.assertFalse(self.Ticket.search(self.Ticket._portal_scope_domain(self.owner, ())))

    def test_create_from_portal_ok(self):
        ticket, error = self.Ticket.create_from_portal(
            self._portal_vals(priority='bogus'), [self.franchise.id],
            attach=lambda t: self._pdf(res_model=t._name, res_id=t.id))
        self.assertIsNone(error)
        self.assertEqual(ticket.priority, 'normal', 'priority lạ về normal')
        self.assertEqual(ticket.attachment_count, 1)

    def test_create_from_portal_rejects_bad_input(self):
        cases = {
            'missing_fields': [self._portal_vals(title=''), self._portal_vals(franchise_id=0),
                               self._portal_vals(category_id=0)],
            'invalid_franchise': [self._portal_vals(franchise_id=self.other_franchise.id)],
            'invalid_input': [self._portal_vals(category_id=self.cat_archived.id),
                              self._portal_vals(category_id=999999)],
        }
        before = self.Ticket.search_count([])
        for expected, vals_list in cases.items():
            for vals in vals_list:
                ticket, error = self.Ticket.create_from_portal(vals, [self.franchise.id])
                self.assertEqual(error, expected, vals)
                self.assertFalse(ticket)
        self.assertEqual(self.Ticket.search_count([]), before)

    def test_create_from_portal_rolls_back_when_attachment_fails(self):
        # Không dùng assertRaises: Odoo tự bọc savepoint quanh nó nên không bắt được lỗi quên savepoint (F8).
        before = self.Ticket.search_count([])
        att_before = self.env['ir.attachment'].search_count([('res_model', '=', self.Ticket._name)])

        def attach(ticket):
            self._pdf(res_model=ticket._name, res_id=ticket.id)
            raise ValidationError('file lạ')

        ticket, error = self.Ticket.create_from_portal(self._portal_vals(), [self.franchise.id], attach=attach)
        self.assertEqual(error, 'invalid_attachment')
        self.assertFalse(ticket)
        self.assertEqual(self.Ticket.search_count([]), before)
        self.assertEqual(
            self.env['ir.attachment'].search_count([('res_model', '=', self.Ticket._name)]), att_before)

    def test_portal_reply_updates_response_analytics(self):
        t = self._ticket()
        t.action_set_waiting_customer()
        n = len(t.message_ids)
        t._portal_reply(self.owner, '   ')
        self.assertEqual(len(t.message_ids), n, 'câu trả lời rỗng không ghi chatter')
        t.with_user(self.hq).message_post(
            body='HQ hỏi', message_type='comment', subtype_xmlid='mail.mt_comment')
        self.assertEqual(t.last_response_by, 'hq')
        self.assertTrue(t.need_customer_reply)
        t._portal_reply(self.owner, ' Đã gửi ảnh ')
        self.assertEqual(t.message_ids[0].author_id, self.owner.partner_id)
        self.assertEqual(t.last_response_by, 'customer')
        self.assertFalse(t.need_customer_reply)

    def test_get_attachment_only_returns_ticket_files(self):
        t = self._ticket()
        other = self._ticket()
        own = self._pdf(res_model=t._name, res_id=t.id)
        legacy = self._pdf('legacy.pdf')
        t.attachment_ids = [(4, legacy.id)]
        foreign = self._pdf(res_model=other._name, res_id=other.id)
        stray = self._pdf('stray.pdf')
        self.assertEqual(t._portal_get_attachment(own.id), own)
        self.assertEqual(t._portal_get_attachment(legacy.id), legacy)
        self.assertFalse(t._portal_get_attachment(foreign.id))
        self.assertFalse(t._portal_get_attachment(stray.id))

    def test_portal_hides_internal_notes_and_their_files(self):
        t = self._ticket()
        upload = self._pdf('upload.pdf', res_model=t._name, res_id=t.id)
        note_file = self._pdf('note.pdf')
        reply_file = self._pdf('reply.pdf')
        t.message_post(body='ghi chú HQ', message_type='comment',
                        subtype_xmlid='mail.mt_note', attachment_ids=[note_file.id])
        t.message_post(body='HQ trả lời', message_type='comment',
                        subtype_xmlid='mail.mt_comment', attachment_ids=[reply_file.id])
        bodies = ''.join(t._portal_messages().mapped('body'))
        self.assertIn('HQ trả lời', bodies)
        self.assertNotIn('ghi chú HQ', bodies)
        self.assertEqual(t._portal_attachments(), upload | reply_file)
        self.assertFalse(t._portal_get_attachment(note_file.id))
