"""F12 — luật đăng ký thi ở model: chọn được ca / lịch tháng / meta khóa / tạo phiếu từ portal."""
import base64
import io
import re
from datetime import date, timedelta

from PIL import Image

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.wujia_exam.models.wujia_exam_registration import ExamPortalError

from .common import load_vi


def png_b64(size=(20, 20)):
    buf = io.BytesIO()
    Image.new('RGB', size, (10, 120, 60)).save(buf, 'PNG')
    return base64.b64encode(buf.getvalue()).decode()


class ExamCommon:
    """Fixture dùng chung với test portal: 2 cửa hàng, 1 khóa (tối đa 2 người/phiếu), 4 ca cùng ngày D.

    J-V3: câu báo assert bằng tiếng Việt ⇒ env + user portal ở vi_VN (nạp .po của `_vi_modules`).
    """

    _vi_modules = ('wujia_exam',)

    @classmethod
    def _setup_exam(cls, login='f12_owner'):
        cls.env = load_vi(cls.env, cls._vi_modules)
        cls.store_a, cls.store_b = [cls._store(code) for code in ('F12A', 'F12B')]
        cls.user = cls.env['res.users'].create({
            'name': 'F12 Owner', 'login': login, 'password': login, 'lang': 'vi_VN',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.member = cls.env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.store_a.id, 'role': 'owner'})
        slots = cls.env['wujia.exam.time.slot'].create([
            {'name': 'F12 %s' % code, 'code': 'F12-%s' % code, 'time_from': start, 'time_to': start + 1}
            for code, start in (('A', 8.0), ('B', 10.0), ('C', 13.0), ('D', 15.0))])
        cls.course = cls.env['wujia.exam.course'].create({
            'name': 'F12 khóa', 'time_slot_ids': [(6, 0, slots.ids)],
            'max_participants_per_registration': 2, 'registration_horizon_days': 30})
        cls.course.action_publish()
        cls.now = fields.Datetime.now()
        cls.day = fields.Date.context_today(cls.course) + timedelta(days=7)
        cls.open, cls.full, cls.expired, cls.closed = [
            cls._session(slot, cap=cap) for slot, cap in zip(slots, (20, 1, 20, 20))]
        for s in cls.open | cls.full | cls.expired | cls.closed:
            s.action_open()
        cls._reg(cls.full, [cls._person(1)])
        cls.closed.action_close()
        # Quá hạn: sửa thẳng DB (create/write chặn hạn trong quá khứ khi còn phiếu mở).
        cls.env.cr.execute("UPDATE wujia_exam_session SET registration_deadline = %s WHERE id = %s",
                           (cls.now - timedelta(hours=1), cls.expired.id))
        cls.expired.invalidate_recordset(['registration_deadline'])

    @classmethod
    def _store(cls, code):
        return cls.env['wujia.franchise.management'].create({
            'code': code, 'name': 'Cửa hàng %s' % code,
            'partner_id': cls.env['res.partner'].create({'name': code}).id,
            'franchise_start_date': fields.Date.today(),
            'franchise_end_date': fields.Date.add(fields.Date.today(), years=1),
        })

    @classmethod
    def _session(cls, slot, cap=20, **vals):
        return cls.env['wujia.exam.session'].create({
            'course_id': cls.course.id, 'exam_date': cls.day, 'time_slot_id': slot.id,
            'capacity': cap, 'max_participants_per_registration': 0,
            'registration_deadline': cls.now + timedelta(days=2), **vals})

    @staticmethod
    def _person(n, **vals):
        return {'employee_name': 'Thí sinh %d' % n, 'phone': '09123456%02d' % n, **vals}

    @classmethod
    def _reg(cls, session, people, store=None):
        # create thường (không qua register_from_portal) ⇒ test portal chạy đối chứng được trên code trước F12.
        return cls.env['wujia.exam.registration'].sudo().create({
            'session_id': session.id, 'franchise_id': (store or cls.store_a).id,
            'requester_user_id': cls.user.id, 'line_ids': [(0, 0, p) for p in people]})


@tagged('post_install', '-at_install', 'wujia_exam')
class TestPortalRules(ExamCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_exam()
        cls.Reg = cls.env['wujia.exam.registration'].sudo()

    def test_slot_status_per_session(self):
        self.assertEqual([s._portal_slot_status(self.now) for s in self.course._portal_sessions_on(self.day)],
                         ['open', 'full', 'expired', 'closed'])
        self.assertEqual([s._portal_is_selectable(self.now) for s in (self.open, self.full, self.expired)],
                         [True, False, False])

    def test_day_states(self):
        states = self.course._portal_day_states(self.day.year, self.day.month)
        self.assertEqual(states[self.day], 'available')
        self.open.write({'capacity': 1})
        self._reg(self.open, [self._person(2)])
        self.assertEqual(self.course._portal_day_states(self.day.year, self.day.month)[self.day], 'full')
        # Ngoài cửa sổ đăng ký (horizon 30 ngày) ⇒ none dù có ca mở.
        self.course.registration_horizon_days = 5
        self.assertEqual(self.course._portal_day_states(self.day.year, self.day.month)[self.day], 'none')

    def test_booking_meta_full_vs_closed(self):
        self.assertEqual(self.course._portal_booking_meta(), {'upcoming_count': 3, 'closed': False, 'full': False})
        self.open.write({'capacity': 1})
        self._reg(self.open, [self._person(2)])
        self.assertEqual(self.course._portal_booking_meta(), {'upcoming_count': 3, 'closed': True, 'full': True})
        (self.open | self.full).action_close()
        self.assertEqual(self.course._portal_booking_meta(), {'upcoming_count': 1, 'closed': True, 'full': False})

    def test_register_creates_submitted_registration(self):
        reg = self.env['wujia.exam.registration'].sudo().register_from_portal(
            self.open.id, self.store_a.id, self.user,
            [self._person(3, birth_year='1999', photo='data:image/png;base64,' + png_b64())], note='  ghi chú  ')
        self.assertEqual((reg.state, reg.franchise_id, reg.requester_user_id, reg.member_id, reg.note),
                         ('submitted', self.store_a, self.user, self.member, 'ghi chú'))
        self.assertEqual((reg.line_ids.birth_year, bool(reg.line_ids.image_1920)), (1999, True))
        self.assertEqual(self.Reg.search(self.Reg._portal_scope_domain(self.store_b.id) + [('id', '=', reg.id)]),
                         self.Reg)

    def _kind(self, session_id, people):
        try:
            self.Reg.register_from_portal(session_id, self.store_a.id, self.user, people)
        except ExamPortalError as e:
            return e.kind, e.args[0]
        return None

    def test_register_rejects_bad_input(self):
        before = self.Reg.search_count([])
        self.assertEqual(self._kind(0, [self._person(1)])[0], 'not_found')
        self.course.action_reset_to_draft()
        self.assertEqual(self._kind(self.open.id, [self._person(1)])[0], 'not_found')
        self.course.action_publish()
        self.assertEqual(self._kind(self.open.id, []), ('validation', 'Cần ít nhất 1 người dự thi.'))
        # Ca để trống ⇒ tối đa của khóa (2).
        self.assertEqual(self._kind(self.open.id, [self._person(i) for i in range(3)]),
                         ('validation', 'Tối đa 2 người mỗi phiếu.'))
        self.assertIn('không hợp lệ', self._kind(self.open.id, [self._person(1, phone='123')])[1])
        self.assertIn('họ tên', self._kind(self.open.id, [{'employee_name': ' ', 'phone': '0912345678'}])[1])
        self.assertIn('Năm sinh', self._kind(self.open.id, [self._person(1, birth_year='abc')])[1])
        self.assertIn('định dạng', self._kind(self.open.id, [self._person(1, photo='data:image/gif;base64,R0lG')])[1])
        self.assertIn('bị hỏng', self._kind(self.open.id, [self._person(1, photo=base64.b64encode(b'x' * 50).decode())])[1])
        big = base64.b64encode(b'\0' * (5 * 1024 * 1024 + 1)).decode()
        self.assertIn('5 MB', self._kind(self.open.id, [self._person(1, photo=big)])[1])
        self.assertEqual(self.Reg.search_count([]), before)

    def test_error_follows_user_lang(self):
        """J-V3: câu gốc tiếng Anh, user vi_VN vẫn nhận đúng câu cũ (kể cả lỗi constraint)."""
        for lang, empty, phone in (
                ('en_US', 'At least 1 participant is required.', "Phone number '123' is invalid"),
                ('vi_VN', 'Cần ít nhất 1 người dự thi.', "Số điện thoại '123' không hợp lệ")):
            with self.subTest(lang=lang):
                Reg = self.Reg.with_context(lang=lang)
                with self.assertRaises(ExamPortalError) as cm:
                    Reg.register_from_portal(self.open.id, self.store_a.id, self.user, [])
                self.assertEqual(cm.exception.args[0], empty)
                with self.assertRaisesRegex(ValidationError, re.escape(phone)):
                    self._reg(self.open, [self._person(1)]).line_ids.with_context(lang=lang).phone = '123'

    def test_business_error_rolls_back(self):
        before = self.Reg.search_count([])
        for session in (self.full, self.expired, self.closed):
            try:
                self.Reg.register_from_portal(session.id, self.store_a.id, self.user, [self._person(9)])
            except ExamPortalError:
                self.fail('lỗi tạo phiếu phải là lỗi nghiệp vụ, không phải lỗi đầu vào')
            except ValidationError:
                pass
            else:
                self.fail('%s phải bị từ chối' % session.name)
        self.assertEqual(self.Reg.search_count([]), before)

    def test_result_counts(self):
        reg = self._reg(self.open, [self._person(4), self._person(5)])
        reg.action_confirm()
        reg.line_ids[0].result = 'passed'
        reg.line_ids[1].result = 'failed'
        self.assertEqual(reg._portal_result_counts(), (1, 1))
