"""WJ-NOTI-001 — giờ gửi thông báo trên portal phải theo múi giờ người dùng."""

from datetime import datetime

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.wujia_portal_base.controllers.utils import (
    fmt_local_dt,
    local_day_range_utc,
    portal_tz,
)


@tagged('post_install', '-at_install', 'wujia_notification')
class TestNotificationTimezone(TransactionCase):

    def setUp(self):
        super().setUp()
        self.tz = portal_tz(self.env)

    def test_default_tz_is_vietnam(self):
        self.env.user.tz = False
        self.assertEqual(str(portal_tz(self.env)), 'Asia/Ho_Chi_Minh')

    def test_published_date_rendered_utc_plus_7(self):
        # Backend ghi 09:51 ngày 03/08/2026 ⇒ cột lưu 02:51 UTC (ca lỗi BA báo).
        utc = datetime(2026, 8, 3, 2, 51)
        self.assertEqual(fmt_local_dt(utc, '%d/%m/%Y %H:%M', self.tz), '03/08/2026 09:51')
        self.assertEqual(fmt_local_dt(utc, '%H:%M %d/%m/%Y', self.tz), '09:51 03/08/2026')

    def test_day_boundary_shifts_date_too(self):
        # 20:30 UTC 02/08 là 03:30 ngày 03/08 giờ Việt Nam — lệch cả NGÀY chứ không chỉ giờ.
        self.assertEqual(
            fmt_local_dt(datetime(2026, 8, 2, 20, 30), '%d/%m/%Y %H:%M', self.tz),
            '03/08/2026 03:30',
        )

    def test_empty_datetime_returns_blank(self):
        self.assertEqual(fmt_local_dt(False, '%d/%m/%Y', self.tz), '')
        self.assertEqual(fmt_local_dt(None, '%d/%m/%Y', self.tz), '')

    def test_date_filter_range_converted_to_utc(self):
        # Lọc "ngày 03/08" theo giờ VN = 02/08 17:00 UTC → 03/08 16:59:59 UTC.
        day = datetime(2026, 8, 3).date()
        utc_from, utc_to = local_day_range_utc(day, day, self.tz)
        self.assertEqual(utc_from, datetime(2026, 8, 2, 17, 0, 0))
        self.assertEqual(utc_to.strftime('%Y-%m-%d %H:%M'), '2026-08-03 16:59')

    def test_notification_published_at_boundary_is_inside_local_day(self):
        # Thông báo gửi 03/08 02:51 UTC (= 09:51 VN) phải nằm trong bộ lọc ngày 03/08.
        day = datetime(2026, 8, 3).date()
        utc_from, utc_to = local_day_range_utc(day, day, self.tz)
        published = datetime(2026, 8, 3, 2, 51)
        self.assertTrue(utc_from <= published <= utc_to)
