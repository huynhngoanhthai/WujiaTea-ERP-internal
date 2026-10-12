# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError


@tagged('post_install', '-at_install', 'wujia_inspection')
class TestInspectionAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Franchise = cls.env['wujia.franchise.management']
        cls.Inspection = cls.env['wujia.franchise.inspection']
        cls.User = cls.env['res.users']

        cls.portal_group = cls.env.ref('base.group_portal')
        cls.inspector_group = cls.env.ref('wujia_franchise_inspection.group_supervision_inspector')
        cls.admin_group = cls.env.ref('wujia_franchise_inspection.group_supervision_admin')

        # Portal user
        cls.portal_user = cls.User.create({
            'name': 'Portal User Test',
            'login': 'portal.user.test@example.com',
            'email': 'portal.user.test@example.com',
            'group_ids': [(6, 0, [cls.portal_group.id])],
        })

        # Inspector user
        cls.inspector_user = cls.User.create({
            'name': 'Inspector User Test',
            'login': 'inspector.user.test@example.com',
            'email': 'inspector.user.test@example.com',
            'group_ids': [(6, 0, [cls.inspector_group.id, cls.env.ref('base.group_user').id])],
        })

        # Cửa hàng và phiếu mẫu
        cls.partner = cls.env['res.partner'].create({
            'name': 'Access Test Store Partner',
        })
        cls.store = cls.Franchise.create({
            'code': 'ACC-STORE-01',
            'name': 'Access Test Store',
            'partner_id': cls.partner.id,
            'supervision_user_id': cls.inspector_user.id,
            'status': 'active',
        })

        cls.inspection = cls.Inspection.create({
            'franchise_id': cls.store.id,
            'inspector_user_id': cls.inspector_user.id,
            'state': 'draft',
        })

    def test_01_portal_user_cannot_create_inspection(self):
        """Portal user không được phép tạo phiếu khảo sát mới."""
        with self.assertRaises(AccessError):
            self.Inspection.with_user(self.portal_user).create({
                'franchise_id': self.store.id,
                'state': 'draft',
            })

    def test_02_inspector_can_create_and_read(self):
        """Inspector được phép tạo và đọc phiếu khảo sát."""
        insp = self.Inspection.with_user(self.inspector_user).create({
            'franchise_id': self.store.id,
            'inspector_user_id': self.inspector_user.id,
            'state': 'draft',
        })
        self.assertTrue(insp.id)
        read_insp = self.Inspection.with_user(self.inspector_user).browse(insp.id)
        self.assertEqual(read_insp.franchise_id.id, self.store.id)
