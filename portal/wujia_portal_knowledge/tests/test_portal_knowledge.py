"""Test màn portal Knowledge — cụm C4 (WJ-KNW-001…004) + F9. Chạy: `--test-tags wujia_knowledge`.

Controller: filter rác không lộ thông tin, thông báo khi bài đã gỡ, search theo summary/content,
giờ portal đúng Asia/Ho_Chi_Minh, tải đính kèm chỉ của bài, Home không hiện bài hẹn giờ.
Luật nghiệp vụ (hiển thị, cron, attachment) test ở `wujia_knowledge`.
"""

from datetime import datetime, timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_knowledge.tests.test_knowledge import KnowledgeCommon
from odoo.addons.wujia_portal_base.controllers.utils import fmt_local_dt


@tagged('post_install', '-at_install', 'wujia_knowledge')
class TestKnowledgePortal(KnowledgeCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_knowledge()
        cls.env['res.users'].create({
            'name': 'knw_user', 'login': 'knw_user', 'password': 'knw_user',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })

    def setUp(self):
        super().setUp()
        self.authenticate('knw_user', 'knw_user')

    def _get(self, url):
        return self.url_open(url, timeout=30)

    def _assert_no_leak(self, res):
        self.assertEqual(res.status_code, 200)
        for leak in ('wujia.knowledge.category', 'wujia.knowledge.tag',
                     'User: ', 'Traceback'):
            self.assertNotIn(leak, res.text)

    def test_unknown_category_shows_friendly_notice(self):
        res = self._get('/portal/knowledge?category_id=999999')
        self._assert_no_leak(res)
        self.assertIn('Danh mục đã chọn không còn khả dụng.', res.text)

    def test_unknown_tag_shows_friendly_notice(self):
        res = self._get('/portal/knowledge?tag_id=999999')
        self._assert_no_leak(res)
        self.assertIn('Thẻ đã chọn không còn khả dụng.', res.text)

    def test_inactive_category_shows_friendly_notice(self):
        cat = self.env['wujia.knowledge.category'].create(
            {'name': 'C4 Inactive cat', 'active': False})
        res = self._get('/portal/knowledge?category_id=%s' % cat.id)
        self._assert_no_leak(res)
        self.assertIn('Danh mục đã chọn không còn khả dụng.', res.text)

    def test_valid_category_still_filters(self):
        res = self._get('/portal/knowledge?category_id=%s' % self.category.id)
        self.assertEqual(res.status_code, 200)
        self.assertIn(self.article.name, res.text)
        self.assertNotIn('không còn khả dụng', res.text)

    def test_unpublished_slug_shows_notice(self):
        gone = self._article('Đã gỡ', 'c4-da-go')
        gone.state = 'draft'
        res = self._get('/portal/knowledge/c4-da-go')
        self.assertEqual(res.status_code, 200)
        self.assertIn('Bài viết không tồn tại hoặc không còn khả dụng.', res.text)
        self.assertNotIn('Đã gỡ', res.text)

    def test_attachment_of_unpublished_article_redirects(self):
        gone = self._article('Đã gỡ 2', 'c4-da-go-2')
        gone.state = 'draft'
        res = self._get('/portal/knowledge/c4-da-go-2/attachment/1')
        self.assertEqual(res.status_code, 200)
        self.assertIn('Bài viết không tồn tại hoặc không còn khả dụng.', res.text)

    def test_search_matches_summary(self):
        res = self._get('/portal/knowledge?keyword=Tóm+tắt+cho+bài+Checklist')
        self.assertEqual(res.status_code, 200)
        self.assertIn(self.article.name, res.text)

    def test_search_matches_content_across_markup(self):
        res = self._get('/portal/knowledge?keyword=Nội+dung+chi+tiết')
        self.assertEqual(res.status_code, 200)
        self.assertIn(self.article.name, res.text)

    def test_search_without_match_shows_empty_state(self):
        res = self._get('/portal/knowledge?keyword=zzz-khong-co-gi')
        self.assertEqual(res.status_code, 200)
        self.assertIn('Chưa có bài viết', res.text)

    def test_detail_prints_local_time(self):
        self.article.publish_date = datetime(2026, 8, 12, 9, 5)
        res = self._get('/portal/knowledge/%s' % self.article.slug)
        self.assertEqual(res.status_code, 200)
        self.assertIn('12/08/2026 16:05', res.text)

    def test_fmt_local_dt_shifts_to_portal_tz(self):
        """UTC 09:05 phải in ra 16:05 giờ Asia/Ho_Chi_Minh (WJ-KNW-002)."""
        self.assertEqual(
            fmt_local_dt(datetime(2026, 8, 12, 9, 5), '%d/%m/%Y %H:%M'),
            '12/08/2026 16:05')

    def test_attachment_download_only_serves_article_files(self):
        own = self._attachment('f9-own.txt', res_model=self.article._name, res_id=self.article.id)
        other = self._article('Bài khác', 'f9-bai-khac')
        foreign = self._attachment('f9-foreign.txt', res_model=other._name, res_id=other.id)
        res = self._get('/portal/knowledge/%s/attachment/%s' % (self.article.slug, own.id))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, b'f9-own.txt')
        res = self._get('/portal/knowledge/%s/attachment/%s' % (self.article.slug, foreign.id))
        self.assertEqual(res.status_code, 403)


@tagged('post_install', '-at_install', 'wujia_knowledge')
class TestKnowledgeOnHome(KnowledgeCommon, HttpCase):
    """Home (portal_base) dùng chung luật hiển thị: bài hẹn giờ chưa tới ngày không hiện (F9)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_knowledge()
        env = cls.env
        franchise = env['wujia.franchise.management'].create({
            'code': 'F9KN', 'name': 'F9 store', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'F9 partner'}).id})
        user = env['res.users'].create({
            'name': 'f9_home', 'login': 'f9_home', 'password': 'f9_home',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
        env['wujia.franchise.member'].create({
            'user_id': user.id, 'franchise_id': franchise.id, 'role': 'owner'})

    def test_home_hides_scheduled_article(self):
        now = fields.Datetime.now()
        fresh = self._article('F9 Bài vừa đăng', 'f9-vua-dang', publish_date=now - timedelta(seconds=1))
        scheduled = self._article('F9 Bài hẹn giờ', 'f9-hen-gio', publish_date=now + timedelta(days=5))
        self.authenticate('f9_home', 'f9_home')
        res = self.url_open('/portal', timeout=30)
        self.assertEqual(res.status_code, 200)
        self.assertIn(fresh.name, res.text)
        self.assertNotIn(scheduled.name, res.text)
