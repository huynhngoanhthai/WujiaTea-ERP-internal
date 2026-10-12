"""WJ-EXAM-007 — giới hạn người/phiếu chỉ có MỘT nguồn (ca thi → khóa)."""
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from .common import load_vi


@tagged('post_install', '-at_install', 'wujia_exam_c10')
class TestExamQuotaSource(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # J-V3: câu báo gốc tiếng Anh, assert tiếng Việt ⇒ chạy ở vi_VN.
        cls.env = load_vi(cls.env)
        cls.slot = cls.env['wujia.exam.time.slot'].create({
            'name': 'C10 08:00-10:00', 'code': 'C10-0810',
            'time_from': 8.0, 'time_to': 10.0,
        })
        cls.course = cls.env['wujia.exam.course'].create({
            'name': 'C10 course', 'time_slot_ids': [(6, 0, cls.slot.ids)],
            'max_participants_per_registration': 2,
        })
        cls.course.action_publish()

    def _session(self, **vals):
        return self.env['wujia.exam.session'].create({
            'course_id': self.course.id, 'time_slot_id': self.slot.id,
            'exam_date': '2026-12-01', 'capacity': 10, **vals,
        })

    def test_session_value_wins(self):
        self.assertEqual(self._session(
            max_participants_per_registration=3)._effective_max_per_registration(), 3)

    def test_falls_back_to_course(self):
        self.assertEqual(self._session(
            max_participants_per_registration=0)._effective_max_per_registration(), 2)

    def test_course_record_reads_own_value(self):
        self.assertEqual(self.course._effective_max_per_registration(), 2)

    def test_server_rejects_over_limit(self):
        # F12: constraint dùng chung nguồn với portal — ca để trống ⇒ giới hạn của khóa (2).
        session = self._session(max_participants_per_registration=0)
        session.action_open()
        lines = [(0, 0, {'employee_name': 'NV %d' % i, 'phone': '090000000%d' % i})
                 for i in range(3)]
        with self.assertRaisesRegex(ValidationError, 'tối đa 2'):
            self.env['wujia.exam.registration'].create({
                'session_id': session.id,
                'franchise_id': self.env['wujia.franchise.management'].search(
                    [], limit=1).id,
                'state': 'submitted', 'line_ids': lines,
            })
