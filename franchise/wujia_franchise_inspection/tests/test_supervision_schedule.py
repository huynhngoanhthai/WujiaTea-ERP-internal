# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo import fields


@tagged('post_install', '-at_install', 'wujia_inspection')
class TestSupervisionSchedule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Franchise = cls.env['wujia.franchise.management']
        cls.Schedule = cls.env['wujia.supervision.schedule']
        cls.Area = cls.env['res.area']
        cls.User = cls.env['res.users']

        # Tạo user quản lý khu vực và giám sát viên
        cls.area_manager = cls.User.create({
            'name': 'Area Manager Test',
            'login': 'area.mgr.test@example.com',
            'email': 'area.mgr.test@example.com',
        })
        cls.inspector = cls.User.create({
            'name': 'Inspector Test',
            'login': 'inspector.test@example.com',
            'email': 'inspector.test@example.com',
        })

        cls.area = cls.Area.create({
            'name': 'Khu vực Miền Nam Test',
            'code': 'KV-MN-TEST',
            'manager_user_id': cls.area_manager.id,
        })

        cls.partner = cls.env['res.partner'].create({
            'name': 'Store Sched 01 Partner',
        })
        cls.store = cls.Franchise.create({
            'code': 'STORE-SCHED-01',
            'name': 'Store Sched 01',
            'partner_id': cls.partner.id,
            'area_id': cls.area.id,
            'supervision_user_id': cls.inspector.id,
            'status': 'active',
        })

    def test_01_effective_supervisor_fallback(self):
        """Kiểm tra người phụ trách giám sát: ưu tiên supervisor, nếu để trống thì fallback về quản lý khu vực."""
        self.store._compute_effective_supervision_user_id()
        self.assertEqual(self.store.effective_supervision_user_id.id, self.inspector.id)

        # Gỡ supervisor -> Phải fallback về area manager
        self.store.supervision_user_id = False
        self.store._compute_effective_supervision_user_id()
        self.assertEqual(self.store.effective_supervision_user_id.id, self.area_manager.id)

    def test_02_create_schedule(self):
        """Kiểm tra tạo lịch giám sát và tính toán ngày kiểm tra gần nhất."""
        today = fields.Date.today()
        schedule = self.Schedule.create({
            'store_id': self.store.id,
            'user_id': self.inspector.id,
            'date': today,
            'state': 'scheduled',
        })
        self.store._compute_nearest_schedule_date()
        self.assertEqual(self.store.nearest_supervision_schedule_date, today)
