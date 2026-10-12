"""Đặc tả khung giờ đặt hàng: nhiều khu vực, giờ địa phương cửa hàng, fallback chung, qua nửa đêm, chặn đơn portal."""
import importlib.util
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytz
from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from odoo.addons.wujia_order_window.models.sale_order import OrderWindowClosed
from odoo.addons.wujia_sale.tests.common import load_vi

TODAY = date(2026, 9, 25)
HCM, TOKYO = 'Asia/Ho_Chi_Minh', 'Asia/Tokyo'


@tagged('post_install', '-at_install', 'wujia_order_window')
class TestOrderWindow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Area = env['res.area']
        cls.area = Area.create({'code': 'F7-A', 'name': 'F7 có khung'})
        cls.area_b = Area.create({'code': 'F7-C', 'name': 'F7 khung chung A+B'})
        cls.area_empty = Area.create({'code': 'F7-B', 'name': 'F7 không khung'})
        cls.Window = env['wujia.order.window']
        cls.morning = cls.Window.create({
            'name': 'Sáng', 'area_ids': [(6, 0, cls.area.ids)], 'order_time_from': 7.0,
            'order_time_to': 11.5, 'sequence': 1})
        cls.evening = cls.Window.create({
            'name': 'Tối', 'area_ids': [(6, 0, cls.area.ids)], 'order_time_from': 20.0,
            'order_time_to': 2.0, 'sequence': 2})
        cls.Window.create({
            'name': 'Cũ', 'area_ids': [(6, 0, cls.area.ids)], 'order_time_from': 12.0,
            'order_time_to': 13.0, 'active': False})
        cls.shared = cls.Window.create({
            'name': 'Chung', 'area_ids': [(6, 0, (cls.area | cls.area_b).ids)],
            'order_time_from': 14.0, 'order_time_to': 16.0, 'sequence': 3})
        cls.ICP = env['ir.config_parameter'].sudo()
        cls.ICP.set_param('wujia_portal.portal_order_time_from', '9.0')
        cls.ICP.set_param('wujia_portal.portal_order_time_to', '3.0')
        cls.ICP.set_param('wujia_portal.portal_order_time_limit_enabled', 'True')
        cls.Settings = env['res.config.settings']
        cls.store = cls._store('F7ST', cls.area, HCM)
        cls.store_b = cls._store('F7SB', cls.area_b, HCM)
        cls.store_empty = cls._store('F7SE', cls.area_empty, HCM)
        cls.partner = cls.store.partner_id

    @classmethod
    def _store(cls, code, area, tz):
        partner = cls.env['res.partner'].create({'name': code, 'tz': tz})
        return cls.env['wujia.franchise.management'].create({
            'code': code, 'name': code, 'franchise_end_date': '2030-01-01',
            'partner_id': partner.id, 'area_id': area.id})

    def at(self, hours, tz=HCM, day=TODAY):
        local = datetime.combine(day, datetime.min.time()) + timedelta(hours=hours)
        utc = pytz.timezone(tz).localize(local).astimezone(pytz.UTC)
        return patch.object(type(self.Settings), '_utc_now', return_value=utc)

    def check(self, hours, store=None, tz=HCM):
        with self.at(hours, tz):
            return self.Settings._is_within_order_window(franchise=store)

    def test_area_windows_take_priority(self):
        for hours, expected in [(6.99, False), (7.0, True), (11.5, True), (13.0, False),
                                (12.5, False), (15.0, True), (20.0, True), (1.0, True), (2.5, False)]:
            with self.subTest(hours=hours):
                self.assertEqual(self.check(hours, self.store)[0], expected)
        allowed, window = self.check(9.0, self.store)
        self.assertEqual(window['source'], 'area:%s' % self.area.id)
        self.assertEqual((window['from'], window['to'], window['window_name']), (7.0, 11.5, 'Sáng'))
        self.assertEqual(window['window_count'], 3)
        self.assertEqual([w['name'] for w in window['windows']], ['Sáng', 'Tối', 'Chung'])
        _allowed, window = self.check(15.0, self.store)
        self.assertEqual(window['open_window']['name'], 'Chung')
        self.assertEqual(window['tz_label'], 'Asia/Ho_Chi_Minh (UTC+07:00)')

    def test_window_shared_by_two_areas(self):
        for hours, expected in [(13.9, False), (14.0, True), (16.0, True), (16.1, False), (9.0, False)]:
            with self.subTest(hours=hours):
                self.assertEqual(self.check(hours, self.store_b)[0], expected)

    def test_area_without_window_uses_global(self):
        for hours, expected in [(8.9, False), (9.0, True), (23.0, True), (3.0, True), (3.1, False)]:
            with self.subTest(hours=hours):
                self.assertEqual(self.check(hours, self.store_empty)[0], expected)
        _allowed, window = self.check(12.0, self.store_empty)
        self.assertEqual(window['source'], 'global')
        self.assertEqual(window['windows'], [{'name': '', 'from': 9.0, 'to': 3.0}])
        self.assertTrue(window['configured'])

    def test_store_local_time_not_user_tz(self):
        tokyo = self._store('F7TK', self.area_b, TOKYO)
        # 14:30 Tokyo = 12:30 HCM: Tokyo mở, HCM đóng — cùng một khoảnh khắc.
        with self.at(14.5, TOKYO):
            self.assertTrue(self.Settings._is_within_order_window(franchise=tokyo)[0])
            self.assertFalse(self.Settings._is_within_order_window(franchise=self.store_b)[0])
            self.env.user.tz = 'America/New_York'
            self.assertTrue(self.Settings._is_within_order_window(franchise=tokyo)[0])
            self.assertFalse(self.Settings._is_within_order_window(franchise=self.store_b)[0])
        self.assertIn('Asia/Tokyo (UTC+09:00)', self.check(14.5, tokyo, TOKYO)[1]['tz_label'])

    def test_dst_timezone(self):
        ny = self._store('F7NY', self.area_b, 'America/New_York')
        for day, offset in [(date(2026, 3, 7), '-05:00'), (date(2026, 3, 9), '-04:00')]:
            with self.subTest(day=day):
                with self.at(14.5, 'America/New_York', day):
                    allowed, window = self.Settings._is_within_order_window(franchise=ny)
                self.assertTrue(allowed)
                self.assertIn(offset, window['tz_label'])
                with self.at(13.5, 'America/New_York', day):
                    self.assertFalse(self.Settings._is_within_order_window(franchise=ny)[0])

    def test_store_without_timezone_blocked(self):
        self.store.partner_id.tz = False
        allowed, window = self.check(9.0, self.store)
        self.assertFalse(allowed)
        self.assertTrue(window['tz_missing'])
        with self.at(9.0):
            self.assertIsNone(self.Settings._next_order_window(franchise=self.store))
            with self.assertRaises(OrderWindowClosed) as err:
                self.env['sale.order'].with_context(lang='en_US').create(self.so_vals())
        self.assertIn('timezone is not configured', str(err.exception))

    def test_global_same_day_window(self):
        self.ICP.set_param('wujia_portal.portal_order_time_from', '8.0')
        self.ICP.set_param('wujia_portal.portal_order_time_to', '17.0')
        self.assertEqual([self.check(h, self.store_empty)[0] for h in (7.9, 8.0, 17.0, 17.1)],
                         [False, True, True, False])

    def test_disabled_always_open(self):
        self.ICP.set_param('wujia_portal.portal_order_time_limit_enabled', 'False')
        allowed, window = self.check(13.0, self.store)
        self.assertTrue(allowed)
        self.assertEqual((window['source'], window['windows'], window['enabled']), ('global', [], False))
        with self.at(13.0):
            self.assertIsNone(self.Settings._next_order_window(franchise=self.store))

    def test_not_configured_flag(self):
        self.ICP.search([('key', '=', 'wujia_portal.portal_order_time_from')]).unlink()
        _allowed, window = self.check(12.0, self.store_empty)
        self.assertFalse(window['configured'])
        self.assertEqual(window['from'], 10.0)

    def test_next_window_today_then_tomorrow(self):
        with self.at(5.0):
            nxt = self.Settings._next_order_window(franchise=self.store)
        self.assertEqual((nxt['name'], nxt['from'], nxt['date'], nxt['is_today']), ('Sáng', 7.0, TODAY, True))
        with self.at(17.0):
            nxt = self.Settings._next_order_window(franchise=self.store)
        self.assertEqual((nxt['name'], nxt['is_today']), ('Tối', True))
        with self.at(21.0):
            nxt = self.Settings._next_order_window(franchise=self.store)
        self.assertEqual((nxt['name'], nxt['date'], nxt['is_today']), ('Sáng', date(2026, 9, 26), False))
        # 23:30 HCM ngày 25 = 01:30 Tokyo ngày 26 ⇒ ngày mở lại tính theo lịch Tokyo.
        tokyo = self._store('F7TK2', self.area_b, TOKYO)
        with self.at(1.5, TOKYO, date(2026, 9, 26)):
            nxt = self.Settings._next_order_window(franchise=tokyo)
        self.assertEqual((nxt['date'], nxt['is_today']), (date(2026, 9, 26), True))

    def test_window_constraints(self):
        self.assertTrue(self.evening.is_overnight)
        self.assertFalse(self.morning.is_overnight)
        with self.assertRaises(ValidationError):
            self.Window.create({'name': 'Rỗng', 'area_ids': [(6, 0, self.area.ids)],
                                'order_time_from': 8.0, 'order_time_to': 8.0})
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.env.cr.savepoint():
            self.Window.create({'name': 'Quá 24', 'area_ids': [(6, 0, self.area.ids)],
                                'order_time_from': 24.0, 'order_time_to': 8.0})
        with self.assertRaises(ValidationError):
            self.Window.create({'name': 'Không khu vực', 'order_time_from': 8.0, 'order_time_to': 9.0})

    def test_duplicate_window_blocked(self):
        with self.assertRaisesRegex(ValidationError, 'duplicates'):
            self.Window.create({'name': 'Trùng', 'area_ids': [(6, 0, (self.area_b | self.area_empty).ids)],
                                'order_time_from': 14.0, 'order_time_to': 16.0})
        # Chồng một phần, hoặc trùng giờ nhưng khác khu vực, hoặc bản trùng đã lưu trữ ⇒ được lưu.
        self.Window.create({'name': 'Chồng', 'area_ids': [(6, 0, self.area_b.ids)],
                            'order_time_from': 15.0, 'order_time_to': 17.0})
        self.Window.create({'name': 'Khác KV', 'area_ids': [(6, 0, self.area_empty.ids)],
                            'order_time_from': 14.0, 'order_time_to': 16.0, 'active': False})
        self.Window.create({'name': 'Cũ 2', 'area_ids': [(6, 0, self.area.ids)],
                            'order_time_from': 12.0, 'order_time_to': 13.0})
        with self.assertRaisesRegex(ValidationError, 'duplicates'):
            self.shared.area_ids = [(4, self.area_empty.id)]
            self.Window.search([('name', '=', 'Khác KV'), ('active', '=', False)]).active = True

    def test_migration_moves_area_id(self):
        path = Path(__file__).parents[1] / 'migrations' / '19.0.2.0.0' / 'post-migrate.py'
        spec = importlib.util.spec_from_file_location('wj_ow_post_migrate', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cr = self.env.cr
        self.env.flush_all()
        cr.execute("ALTER TABLE wujia_order_window ADD COLUMN area_id int")
        cr.execute("UPDATE wujia_order_window SET area_id = %s WHERE id IN %s",
                   (self.area_empty.id, tuple((self.morning | self.evening).ids)))
        self.store_b.partner_id.tz = False
        self.env.flush_all()
        mod.migrate(cr, '19.0.1.1.0')
        self.env.invalidate_all()
        self.assertEqual(self.morning.area_ids, self.area | self.area_empty)
        self.assertEqual(self.evening.area_ids, self.area | self.area_empty)
        self.assertEqual(self.shared.area_ids, self.area | self.area_b)
        self.assertEqual(self.store_b.tz, HCM)
        self.assertEqual(self.store.tz, HCM)

    def so_vals(self, portal=True):
        return {'partner_id': self.partner.id, 'franchise_id': self.store.id, 'is_portal_order': portal}

    def test_portal_order_blocked_outside_window(self):
        SO = self.env['sale.order']
        # J-V4: câu gốc tiếng Anh, tiếng Việt qua .po — lỗi ra theo ngôn ngữ của env.
        with self.at(13.0), self.assertRaises(OrderWindowClosed) as err:
            SO.with_context(lang='en_US').create(self.so_vals())
        self.assertIn('Not within the ordering window', str(err.exception))
        self.assertRegex(str(err.exception), r'within \d\d:\d\d – \d\d:\d\d\.')  # giờ:phút, không phải 10.00
        with self.at(13.0), self.assertRaises(OrderWindowClosed) as err:
            load_vi(self.env)['sale.order'].create(self.so_vals())
        self.assertIn('khung giờ nhận đơn', str(err.exception))
        self.assertIsInstance(err.exception, ValidationError)
        with self.at(13.0):
            self.assertTrue(SO.create(self.so_vals(portal=False)))
        with self.at(9.0):
            self.assertTrue(SO.create(self.so_vals()))
