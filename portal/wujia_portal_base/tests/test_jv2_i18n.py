"""J-V2 — Việt hoá source `wujia_portal_base`: câu gốc tiếng Anh, tiếng Việt qua `i18n/vi_VN.po`.

Màu badge trạng thái tra theo câu gốc EN (`_lt`) nên không đổi theo ngôn ngữ người xem; module chưa
qua Phần V còn truyền nhãn tiếng Việt viết cứng ⇒ tra ngược qua .po (tạm, ★J-VR xoá).
"""
from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase

from odoo.addons.wujia_portal_base.controllers.portal import FRANCHISE_STATUS_LABELS
from odoo.addons.wujia_portal_base.controllers.utils import (
    ERR_DATE_RANGE,
    RETURN_STATUS_LABELS,
    SALE_STATE_META,
    STATUS_VARIANT_BY_LABEL,
    VI_WEEKDAYS,
    status_badge_for,
)
from odoo.addons.wujia_portal_base.models.wujia_franchise_member import ROLE_LABELS

from .common import legacy_vn_badge, load_vi


@tagged('post_install', '-at_install', 'wujia_jv2')
class TestStatusBadgeAnyLanguage(TransactionCase):

    def test_english_source_and_lazy_label_give_same_variant(self):
        lazy = SALE_STATE_META['sale'][0]
        self.assertEqual(status_badge_for(lazy), 'wj-status-badge--info')
        self.assertEqual(status_badge_for('Confirmed'), 'wj-status-badge--info')

    def test_translated_label_does_not_pick_colour(self):
        """★J-VR: bỏ nhánh tra ngược vi_VN.po — nhãn đã dịch ra neutral, caller phải truyền `_lt`.

        `legacy_vn_badge` (chỉ test) giữ đáp án màu cũ cho test chống lùi Phần V.
        """
        cases = {
            'Đã xác nhận': 'info', 'Chờ xác nhận': 'pending', 'Đang giao': 'processing',
            'Hoàn tất': 'success', 'Có quá hạn': 'danger', 'Cần bổ sung': 'feedback',
            'Đã đóng': 'neutral', 'Đã hủy': 'danger',
        }
        for label, variant in cases.items():
            with self.subTest(label=label):
                self.assertEqual(status_badge_for(label), 'wj-status-badge--neutral')
                self.assertEqual(legacy_vn_badge(label), 'wj-status-badge--' + variant)

    def test_both_spellings_of_cancelled(self):
        """'huỷ' (portal_support cũ) và 'hủy' cùng một chữ trong đáp án màu cũ."""
        self.assertEqual(legacy_vn_badge('Đã huỷ'), 'wj-status-badge--danger')

    def test_every_english_key_has_a_vietnamese_translation(self):
        vi = load_vi(self.env)
        for key in STATUS_VARIANT_BY_LABEL:
            with self.subTest(key=key):
                self.assertNotEqual(vi._(key), key, 'thiếu bản dịch vi_VN ⇒ nhãn VN cũ mất màu')


@tagged('post_install', '-at_install', 'wujia_jv2')
class TestLabelsFollowLang(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env_vi = load_vi(cls.env)
        cls.env_en = cls.env(context=dict(cls.env.context, lang='en_US'))

    def test_constants_translate(self):
        pairs = [
            (ROLE_LABELS['owner'], 'Store owner', 'Chủ tiệm'),
            (ROLE_LABELS['staff'], 'Staff', 'Nhân viên'),
            (FRANCHISE_STATUS_LABELS['active'], 'Enabled', 'Đang hoạt động'),
            (FRANCHISE_STATUS_LABELS['locked'], 'Locked', 'Khóa'),
            (RETURN_STATUS_LABELS['partial'][0], 'Partially compensated', 'Đang bù một phần'),
            (VI_WEEKDAYS[6], 'Sun', 'CN'),
            (ERR_DATE_RANGE, 'From date cannot be later than To date', 'Từ ngày không được lớn hơn Đến ngày'),
        ]
        for lazy, en, vi in pairs:
            with self.subTest(en=en):
                self.assertEqual(self.env_en._(lazy), en)
                self.assertEqual(self.env_vi._(lazy), vi)

    def test_member_role_label_follows_env_lang(self):
        user = self.env['res.users'].create({
            'name': 'jv2 role', 'login': 'jv2_role',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        franchise = self.env['wujia.franchise.management'].create({
            'code': 'JV2R', 'name': 'JV2 role store', 'franchise_end_date': '2030-01-01',
            'partner_id': self.env['res.partner'].create({'name': 'JV2R partner'}).id,
        })
        member = self.env['wujia.franchise.member'].create({
            'user_id': user.id, 'franchise_id': franchise.id, 'role': 'manager',
        })
        self.assertEqual(member.with_env(self.env_en)._portal_role_label(), 'Manager')
        self.assertEqual(member.with_env(self.env_vi)._portal_role_label(), 'Quản lý')


@tagged('post_install', '-at_install', 'wujia_jv2')
class TestHomeFollowsUserLang(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_vi(cls.env)
        franchise = cls.env['wujia.franchise.management'].create({
            'code': 'JV2H', 'name': 'JV2 home store', 'franchise_end_date': '2030-01-01',
            'partner_id': cls.env['res.partner'].create({'name': 'JV2H partner'}).id,
        })
        for login, lang in (('jv2_vi', 'vi_VN'), ('jv2_en', 'en_US')):
            user = cls.env['res.users'].create({
                'name': login, 'login': login, 'password': login + '_pw', 'lang': lang,
                'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
            })
            user.lang = lang  # portal_base đặt mặc định vi_VN lúc tạo ⇒ ghi lại cho chắc
            cls.env['wujia.franchise.member'].create({
                'user_id': user.id, 'franchise_id': franchise.id, 'role': 'owner',
            })

    def _home(self, login):
        self.authenticate(login, login + '_pw')
        res = self.url_open('/portal', timeout=60)
        self.assertEqual(res.status_code, 200)
        return res.text

    def test_vietnamese_user_sees_vietnamese(self):
        html = self._home('jv2_vi')
        for text in ('Tổng quan cửa hàng', 'Khung giờ đặt hàng', 'Giao hàng sắp tới', 'Chủ tiệm'):
            self.assertIn(text, html)
        self.assertNotIn('Store overview', html)

    def test_english_user_sees_english(self):
        html = self._home('jv2_en')
        for text in ('Store overview', 'Ordering window', 'Upcoming deliveries', 'Store owner'):
            self.assertIn(text, html)
        self.assertNotIn('Tổng quan cửa hàng', html)

    def test_home_counts_singular_plural(self):
        """EN "1 orders"/"1 undelivered orders" sai ngữ pháp ⇒ msgid số ít riêng, vi_VN giữ y câu cũ."""
        view = self.env.ref('wujia_portal_base.portal_home_page')
        arch_en = view.with_context(lang='en_US').arch_db
        for text in ('order in 30 days', '%s undelivered order<', 'undelivered order<'):
            self.assertIn(text, arch_en)
        arch_vi = view.with_context(lang='vi_VN').arch_db
        self.assertNotIn(' order in 30 days', arch_vi)
        self.assertNotIn('undelivered order', arch_vi)
        self.assertGreaterEqual(arch_vi.count('đơn trong 30 ngày'), 2)
        self.assertGreaterEqual(arch_vi.count('đơn chưa giao'), 4)
