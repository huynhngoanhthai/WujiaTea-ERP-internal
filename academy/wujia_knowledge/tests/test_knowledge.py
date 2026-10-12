"""Test nghiệp vụ Knowledge — cụm C4 (WJ-KNW-001…004) + F9. Chạy: `--test-tags wujia_knowledge`.

`TestKnowledgeArticle` — field text strip HTML, luật hiển thị portal (publish date tương lai /
hết hạn / draft / archived / inactive), mã + slug + ngày phát hành tự sinh, cron hạ bài hết hạn,
attachment thuộc bài. `KnowledgeCommon` dùng lại ở test portal.
"""

import base64
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


class KnowledgeCommon:

    @classmethod
    def _setup_knowledge(cls):
        cls.category = cls.env['wujia.knowledge.category'].create({
            'name': 'C4 Category', 'sequence': 1})
        cls.now = fields.Datetime.now()
        cls.article = cls.env['wujia.knowledge.article'].create({
            'name': 'Checklist mở cửa hàng buổi sáng',
            'slug': 'c4-checklist-mo-cua-hang',
            'category_id': cls.category.id,
            'summary': 'Tóm tắt cho bài Checklist mở cửa hàng buổi sáng.',
            # Keyword bị thẻ HTML cắt ngang → chỉ bản strip mới khớp.
            'content': '<p>Nội dung <strong>chi tiết</strong> cho bài viết.</p>',
            'state': 'published',
            'publish_date': cls.now - timedelta(days=1),
        })

    @classmethod
    def _article(cls, name, slug, **vals):
        return cls.env['wujia.knowledge.article'].create(dict({
            'name': name, 'slug': slug, 'category_id': cls.category.id,
            'state': 'published', 'publish_date': cls.now - timedelta(days=1),
        }, **vals))

    @classmethod
    def _attachment(cls, name, **vals):
        return cls.env['ir.attachment'].create(dict({
            'name': name, 'datas': base64.b64encode(name.encode()), 'mimetype': 'text/plain',
        }, **vals))


@tagged('post_install', '-at_install', 'wujia_knowledge')
class TestKnowledgeArticle(KnowledgeCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_knowledge()

    def test_content_text_strips_markup(self):
        self.assertEqual(
            self.article.wujia_content_text, 'Nội dung chi tiết cho bài viết.')

    def test_content_text_follows_content(self):
        self.article.content = '<div>Quy trình <em>đóng</em> ca tối</div>'
        self.assertEqual(self.article.wujia_content_text, 'Quy trình đóng ca tối')

    def test_visible_domain_excludes_hidden_articles(self):
        Article = self.env['wujia.knowledge.article']
        hidden = {
            'draft': self._article('Draft', 'c4-draft', state='draft'),
            'archived': self._article('Archived', 'c4-arch', state='archived'),
            'inactive': self._article('Inactive', 'c4-inactive', active=False),
            'expired': self._article(
                'Expired', 'c4-expired', expired_date=self.now - timedelta(hours=1)),
            'future': self._article(
                'Future', 'c4-future', publish_date=self.now + timedelta(days=3)),
        }
        visible = Article.search(Article._portal_visible_domain())
        self.assertIn(self.article, visible)
        for label, rec in hidden.items():
            self.assertNotIn(rec, visible, 'Bài %s không được hiện trên portal' % label)

    def test_search_domain_matches_name_summary_and_stripped_content(self):
        Article = self.env['wujia.knowledge.article']
        for keyword in ('Checklist mở cửa', 'Tóm tắt cho bài', 'Nội dung chi tiết'):
            self.assertIn(self.article, Article.search(Article._portal_search_domain(keyword)), keyword)
        self.assertFalse(Article.search(
            [('id', '=', self.article.id)] + Article._portal_search_domain('zzz-khong-co')))

    def test_create_fills_code_slug_and_publish_date(self):
        art = self.env['wujia.knowledge.article'].create({
            'name': 'Quy Trình Đóng Ca', 'category_id': self.category.id, 'state': 'published'})
        self.assertTrue(art.code.startswith('KNW-'))
        self.assertEqual(art.slug, 'quy-trình-đóng-ca')
        self.assertTrue(art.publish_date)
        self.assertTrue(art.is_published_portal)

    def test_publish_from_draft_sets_publish_date(self):
        art = self._article('Nháp', 'f9-nhap', state='draft', publish_date=False)
        self.assertFalse(art.is_published_portal)
        art.action_publish()
        self.assertTrue(art.publish_date)
        self.assertTrue(art.is_published_portal)

    def test_cron_hides_expired_article(self):
        art = self._article('Sắp hết hạn', 'f9-het-han', expired_date=self.now + timedelta(days=1))
        self.assertTrue(art.is_published_portal)
        # Hết hạn theo thời gian: không có write nào kích compute — chỉ cron hạ cờ.
        self.env.cr.execute(
            "UPDATE wujia_knowledge_article SET expired_date = %s WHERE id = %s",
            (self.now - timedelta(hours=1), art.id))
        art.invalidate_recordset(['expired_date'])
        self.assertTrue(art.is_published_portal)
        self.env['wujia.knowledge.article']._cron_recompute_is_published()
        self.assertFalse(art.is_published_portal)

    def test_get_attachment_only_returns_article_files(self):
        other = self._article('Bài khác', 'f9-bai-khac')
        m2m = self._attachment('f9-m2m.txt')
        own = self._attachment('f9-own.txt', res_model=self.article._name, res_id=self.article.id)
        foreign = self._attachment('f9-foreign.txt', res_model=other._name, res_id=other.id)
        loose = self._attachment('f9-loose.txt')
        self.article.attachment_ids = [(6, 0, m2m.ids)]
        self.assertEqual(self.article._portal_get_attachment(m2m.id), m2m)
        self.assertEqual(self.article._portal_get_attachment(own.id), own)
        self.assertFalse(self.article._portal_get_attachment(foreign.id))
        self.assertFalse(self.article._portal_get_attachment(loose.id))
