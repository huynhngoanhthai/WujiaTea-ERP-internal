"""Nghiệp vụ yêu cầu cập nhật thông tin — trước F8 chỉ có 3 test controller, 0 test model."""
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .common import load_vi


@tagged('post_install', '-at_install', 'wujia_info_request')
class TestInfoRequest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = env = load_vi(cls.env)
        cls.franchise = env['wujia.franchise.management'].create({
            'code': 'F8IR', 'name': 'F8 store', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'F8 partner', 'phone': '0281'}).id})
        cls.other = env['wujia.franchise.management'].create({
            'code': 'F8OT', 'name': 'F8 other', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'F8 other partner'}).id})
        cls.users = {}
        for role in ('owner', 'manager', 'staff'):
            user = env['res.users'].create({
                'name': f'f8 {role}', 'login': f'f8.{role}',
                'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
            env['wujia.franchise.member'].create({
                'user_id': user.id, 'franchise_id': cls.franchise.id, 'role': role})
            cls.users[role] = user
        cls.Model = env['wujia.info.update.request']

    def _vals(self, **kw):
        return dict({'franchise_id': self.franchise.id, 'request_type': 'phone', 'new_value': '0909'}, **kw)

    def test_sequence_and_lifecycle(self):
        rec = self.Model.create(self._vals())
        self.assertTrue(rec.name.startswith('INF-'))
        self.assertEqual(rec.state, 'draft')
        rec.action_submit()
        self.assertEqual(rec.state, 'submitted')
        self.assertTrue(rec.submitted_date)
        self.assertTrue(any('đã được gửi' in b for b in rec.message_ids.mapped('body')))
        rec.action_start_review()
        self.assertEqual((rec.state, rec.reviewer_id), ('reviewing', self.env.user))
        rec.action_approve()
        self.assertEqual(rec.state, 'approved')
        self.assertTrue(rec.reviewed_date)

    def test_cancel_only_draft_or_submitted(self):
        rec = self.Model.create(self._vals())
        rec.action_cancel()
        self.assertEqual((rec.state, rec.refuse_reason), ('rejected', 'User huỷ'))
        rec = self.Model.create(self._vals())
        rec.action_submit()
        rec.action_start_review()
        with self.assertRaises(ValidationError):
            rec.action_cancel()

    def test_other_requires_field_target(self):
        with self.assertRaises(ValidationError):
            self.Model.create(self._vals(request_type='other'))

    def test_old_value_shared_by_form_and_portal(self):
        rec = self.Model.create(self._vals(request_type='owner_name'))
        self.assertEqual(rec.old_value, 'F8 store')
        self.assertEqual(self.Model._franchise_value(self.franchise, 'other', ' name '), 'F8 store')
        self.assertEqual(self.Model._franchise_value(self.franchise, 'other', 'khong_co'), '')
        self.assertEqual(self.Model._franchise_value(self.franchise, 'bank_info'), '')

    def test_portal_gate_owner_manager_only(self):
        fids = [self.franchise.id]
        for role, allowed in (('owner', True), ('manager', True), ('staff', False)):
            Model = self.Model.with_user(self.users[role]).sudo()
            self.assertEqual(Model._portal_can_request(fids), allowed, role)
            self.assertFalse(Model._portal_can_request([self.other.id]), role)

    def test_scope_domain(self):
        mine = self.Model.create(self._vals())
        self.Model.create(self._vals(franchise_id=self.other.id))
        self.assertEqual(self.Model.search(self.Model._portal_scope_domain((self.franchise.id,))), mine)
        self.assertFalse(self.Model.search(self.Model._portal_scope_domain(())))

    def test_create_from_portal_attaches_and_submits(self):
        def attach(rec):
            return self.env['ir.attachment'].create({
                'name': 'f8.png', 'res_model': rec._name, 'res_id': rec.id, 'raw': b'f8'})
        rec = self.Model.create_from_portal(self._vals(), submit=True, attach=attach)
        self.assertEqual(rec.state, 'submitted')
        self.assertEqual(rec.attachment_ids.mapped('name'), ['f8.png'])
        draft = self.Model.create_from_portal(self._vals())
        self.assertEqual(draft.state, 'draft')

    def test_create_from_portal_rolls_back_whole_block(self):
        def attach(rec):
            raise ValidationError('file sai')
        before = self.Model.search_count([])
        # không dùng assertRaises: Odoo bọc sẵn savepoint, sẽ che mất lỗi thiếu savepoint
        try:
            self.Model.create_from_portal(self._vals(), submit=True, attach=attach)
        except ValidationError:
            pass
        else:
            self.fail('lỗi đính kèm phải lan ra ngoài')
        self.assertEqual(self.Model.search_count([]), before)
