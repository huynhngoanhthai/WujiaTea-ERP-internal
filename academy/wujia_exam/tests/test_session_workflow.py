from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from .common import load_vi


@tagged('post_install', '-at_install')
class TestSessionWorkflow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = load_vi(cls.env)

        cls.slot = cls.env['wujia.exam.time.slot'].create({
            'name': 'Test Slot 08:00-10:00',
            'code': 'TEST-0810',
            'time_from': 8.0,
            'time_to': 10.0,
        })

        cls.course = cls.env['wujia.exam.course'].create({
            'name': 'Test Course',
            'time_slot_ids': [(6, 0, cls.slot.ids)],
        })
        cls.course.action_publish()

    def _create_session(self):
        return self.env['wujia.exam.session'].create({
            'course_id': self.course.id,
            'time_slot_id': self.slot.id,
            'exam_date': '2026-12-01',
            'capacity': 10,
        })

    def test_action_open_success(self):
        session = self._create_session()
        self.assertEqual(session.state, 'draft')
        session.action_open()
        self.assertEqual(session.state, 'open')

    def test_action_open_fail_not_draft(self):
        session = self._create_session()
        session.action_open()
        with self.assertRaises(ValidationError):
            session.action_open()

    def test_action_close_success(self):
        session = self._create_session()
        session.action_open()
        session.action_close()
        self.assertEqual(session.state, 'closed')

    def test_action_close_fail_not_open(self):
        session = self._create_session()
        with self.assertRaises(ValidationError):
            session.action_close()

    def test_action_mark_done_from_open(self):
        session = self._create_session()
        session.action_open()
        session.action_mark_done()
        self.assertEqual(session.state, 'done')

    def test_action_mark_done_from_closed(self):
        session = self._create_session()
        session.action_open()
        session.action_close()
        session.action_mark_done()
        self.assertEqual(session.state, 'done')

    def test_action_mark_done_fail_draft(self):
        session = self._create_session()
        with self.assertRaises(ValidationError):
            session.action_mark_done()

    def test_action_cancel_success(self):
        session = self._create_session()
        session.cancellation_reason = 'Test Reason'
        session.action_cancel()
        self.assertEqual(session.state, 'cancelled')

    def test_action_cancel_fail_no_reason(self):
        session = self._create_session()
        with self.assertRaises(ValidationError):
            session.action_cancel()

    def test_action_cancel_fail_done(self):
        session = self._create_session()
        session.action_open()
        session.action_mark_done()
        session.cancellation_reason = 'Test Reason'
        with self.assertRaises(ValidationError):
            session.action_cancel()
