"""Hồ sơ cửa hàng: số ngày còn lại theo lịch cửa hàng, cùng tập trường PC ↔ mobile, card thành viên đọc đủ tên.

Chạy: `--test-tags wujia_profile_i11`.
"""
import re
from datetime import date, timedelta

from freezegun import freeze_time
from lxml import html as lhtml

from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase
from odoo.tools.misc import file_path

from odoo.addons.wujia_portal_base.controllers.portal import ACTIVE_FRANCHISE_COOKIE

BA_END = date(2028, 5, 15)


def _store(env, code, tz='Asia/Ho_Chi_Minh'):
    store = env['wujia.franchise.management'].create({
        'code': code, 'name': 'I11 store %s' % code, 'status': 'active',
        'partner_id': env['res.partner'].create({'name': 'I11 partner %s' % code, 'tz': tz}).id,
    })
    store.write({'franchise_start_date': '2020-01-01'})
    return store


def _set_end(store, end):
    store.write({'franchise_end_date': end})
    # giá trị stored cũ kiểu UAT (613 thay vì 585) — helper không được đọc nó
    store.write({'remaining_days': 999, 'is_expired': False})


@tagged('post_install', '-at_install', 'wujia_profile_i11')
class TestContractDays(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.store = _store(cls.env, 'I11D')

    def _days(self, end, now='2026-10-08 05:00:00'):
        _set_end(self.store, end)
        with freeze_time(now):
            return self.store._portal_contract_days()

    def test_ba_case_585(self):
        self.assertEqual(self._days(BA_END), (585, False))

    def test_boundaries(self):
        today = date(2026, 10, 8)
        self.assertEqual(self._days(today), (0, False))
        self.assertEqual(self._days(today - timedelta(days=1)), (-1, True))
        self.assertEqual(self._days(today + timedelta(days=30)), (30, False))
        self.assertEqual(self._days(today + timedelta(days=31)), (31, False))

    def test_no_end_date(self):
        self.assertEqual(self._days(False), (None, False))

    def test_decreases_with_calendar(self):
        self.assertEqual(self._days(BA_END, '2026-10-09 05:00:00'), (584, False))

    def test_store_timezone(self):
        # 05:00 UTC 08/10 = 18:00 07/10 ở Pago Pago (UTC−11)
        self.store.partner_id.tz = 'Pacific/Pago_Pago'
        self.assertEqual(self._days(BA_END)[0], 586)
        # 22:00 UTC 08/10 = 05:00 09/10 ở VN
        self.store.partner_id.tz = 'Asia/Ho_Chi_Minh'
        self.assertEqual(self._days(BA_END, '2026-10-08 22:00:00')[0], 584)

    def test_bad_timezone_falls_back(self):
        self.env.cr.execute("UPDATE res_partner SET tz = 'Mars/Olympus' WHERE id = %s", [self.store.partner_id.id])
        self.store.partner_id.invalidate_recordset(['tz'])
        self.assertEqual(self._days(BA_END)[0], 585)


@tagged('post_install', '-at_install', 'wujia_profile_i11')
class TestProfileRender(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.store = _store(env, 'I11R')
        cls.store.write({'opening_date': '2026-09-05', 'phone': '+84 28 0000 1111',
                         'email': 'i11@wujiatea.vn', 'address': '1 Lê Lợi'})
        _set_end(cls.store, date.today() + timedelta(days=400))
        portal = env.ref('base.group_portal').id
        cls.owner = env['res.users'].create({
            'name': 'I11 Chủ', 'login': 'i11.owner', 'password': 'i11.owner', 'lang': 'en_US', 'group_ids': [(6, 0, [portal])]})
        cls.long_name = 'Nguyễn Hoàng Bảo Ngọc Thị Phương Uyên Trần Lê'
        staff = env['res.users'].create({
            'name': cls.long_name, 'login': 'i11.staff', 'password': 'i11.staff', 'group_ids': [(6, 0, [portal])]})
        Member = env['wujia.franchise.member']
        Member.create({'user_id': cls.owner.id, 'franchise_id': cls.store.id, 'role': 'owner'})
        Member.create({'user_id': staff.id, 'franchise_id': cls.store.id, 'role': 'staff'})

    def _tree(self, url):
        self.authenticate('i11.owner', 'i11.owner')
        self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(self.store.id))
        res = self.url_open(url, timeout=30)
        self.assertEqual(res.status_code, 200)
        return lhtml.fromstring(res.text)

    @staticmethod
    def _kv(tree, item, key, val):
        t = lambda n: re.sub(r'\s+', ' ', n.text_content()).strip()
        return {t(f.find_class(key)[0]): t(f.find_class(val)[0]) for f in tree.find_class(item)}

    def test_pc_and_mobile_same_fields(self):
        tree = self._tree('/portal/franchise-information')
        pc = self._kv(tree, 'wj-pc-acct-field', 'wj-pc-acct-field__label', 'wj-pc-acct-field__value')
        mob = self._kv(tree, 'wujia-maccount-kv', 'wujia-maccount-kv-key', 'wujia-maccount-kv-val')
        days = '%s days' % self.store._portal_contract_days()[0]
        for label, value in (('Opening date', '05/09/2026'), ('Phone', '+84 28 0000 1111'),
                             ('Email', 'i11@wujiatea.vn'), ('Address', '1 Lê Lợi'), ('Remaining', days),
                             ('Person in charge', 'I11 Chủ'),
                             ('End date', self.store.franchise_end_date.strftime('%d/%m/%Y'))):
            self.assertEqual(pc.get(label), value, 'PC ' + label)
            self.assertEqual(mob.get(label), value, 'mobile ' + label)
        self.assertIn('Start date', pc)
        self.assertNotIn('999', pc['Remaining'] + mob['Remaining'])

    def test_expired_ignores_stored_flag(self):
        _set_end(self.store, date.today() - timedelta(days=2))
        tree = self._tree('/portal/franchise-information')
        self.assertEqual(len(tree.xpath('//span[contains(@class,"wj-status-badge--danger")][normalize-space()="Has expired"]')), 2)
        prof = self._tree('/portal/franchises/%s/profile' % self.store.id)
        self.assertTrue(prof.xpath('//dl[contains(@class,"profile-dl")]//span[normalize-space()="Has expired"]'))

    def test_legacy_profile_same_days(self):
        prof = self._tree('/portal/franchises/%s/profile' % self.store.id)
        dd = re.sub(r'\s+', ' ', prof.xpath('//dl[contains(@class,"profile-dl")]/dt[normalize-space()="Remaining"]'
                                            '/following-sibling::dd[1]')[0].text_content()).strip()
        self.assertEqual(dd, '%s days' % self.store._portal_contract_days()[0])

    def test_member_card_name_full_width(self):
        tree = self._tree('/portal/franchise-information')
        cards = [c for c in tree.find_class('wj-lc') if self.long_name in c.text_content()]
        self.assertEqual(len(cards), 1)
        card = cards[0]
        name = card.find_class('wj-lc__name')[0]
        self.assertIn('wj-lc__name--wrap', name.get('class'))
        head = card.find_class('wj-lc__head')[0]
        self.assertFalse(head.find_class('wujia-badge'), 'role không chen hàng tên')
        self.assertTrue(head.find_class('wj-lc__state'))
        self.assertTrue(card.find_class('wj-lc__body')[0].find_class('wujia-badge'))

    def test_wrap_modifier_css(self):
        css = open(file_path('wujia_portal_layout/static/assets/css/_components.css')).read()
        rule = re.search(r'\.wj-lc__name--wrap\s*\{([^}]*)\}', css)
        self.assertTrue(rule)
        body = rule.group(1)
        self.assertIn('display: block', body)
        self.assertIn('overflow: visible', body)
        self.assertNotIn('anywhere', body)
