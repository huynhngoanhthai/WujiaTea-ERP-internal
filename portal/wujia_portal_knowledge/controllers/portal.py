import logging

from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request
from odoo.tools.translate import LazyTranslate

from odoo.addons.wujia_portal_base.controllers.utils import (
    build_pager,
    fmt_local_dt,
    parse_page_size,
)

_logger = logging.getLogger(__name__)
_lt = LazyTranslate(__name__)

PAGE_SIZE = 12
# Lưới bài viết 3 cột nên bậc cỡ trang là bội của 12, không dùng bậc 10/20/50 chung.
PAGE_SIZE_OPTIONS = (12, 24, 48)
NOTICES = ('category_gone', 'tag_gone', 'article_gone')


class WujiaPortalKnowledge(http.Controller):

    @staticmethod
    def _filter_record(model, raw_id):
        """(record, invalid): id không parse được / không tồn tại / inactive ⇒ invalid."""
        if not raw_id:
            return model.browse(), False
        try:
            rec = model.browse(int(raw_id)).exists()
        except (TypeError, ValueError):
            return model.browse(), True
        if not rec or not rec.active:
            return model.browse(), True
        return rec, False

    @http.route(['/portal/knowledge'], type='http', auth='user', sitemap=False)
    def portal_knowledge_list(self, page=1, category_id=None, tag_id=None,
                              keyword='', notice=None, page_size=None, **kw):
        Article = request.env['wujia.knowledge.article'].sudo()
        Category = request.env['wujia.knowledge.category'].sudo()
        Tag = request.env['wujia.knowledge.tag'].sudo()

        category, cat_invalid = self._filter_record(Category, category_id)
        tag, tag_invalid = self._filter_record(Tag, tag_id)
        if cat_invalid or tag_invalid:
            _logger.info(
                'Invalid knowledge filter (category_id=%r, tag_id=%r), user %s',
                category_id, tag_id, request.env.uid,
            )
            return request.redirect(
                '/portal/knowledge?notice=%s'
                % ('category_gone' if cat_invalid else 'tag_gone')
            )

        domain = Article._portal_visible_domain()
        if keyword:
            domain += Article._portal_search_domain(keyword)
        if category:
            domain.append(('category_id', '=', category.id))
        if tag:
            domain.append(('tag_ids', 'in', tag.ids))

        try:
            page = max(1, int(page))
        except (TypeError, ValueError):
            page = 1
        size = parse_page_size(page_size, PAGE_SIZE, PAGE_SIZE_OPTIONS)
        offset = (page - 1) * size
        total = Article.search_count(domain)
        articles = Article.search(
            domain, limit=size, offset=offset,
            order='sequence, publish_date desc, id desc',
        )

        categories = Category.search([('active', '=', True)], order='sequence, name')
        tags = Tag.search([('active', '=', True)], order='name')
        pgn = build_pager(total, page, size, path='/portal/knowledge',
                          item_label=_lt('articles'),
                          page_size_options=PAGE_SIZE_OPTIONS)
        return request.render('wujia_portal_knowledge.portal_knowledge_list', {
            'articles': articles, 'categories': categories, 'tags': tags,
            'pgn': pgn, 'keyword': keyword,
            'category_id': category.id or None, 'tag_id': tag.id or None,
            'current_category': category or None,
            'current_tag': tag or None,
            'notice': notice if notice in NOTICES else '',
            'wj_dt': fmt_local_dt,
        })

    @http.route(['/portal/knowledge/<string:slug>'],
                type='http', auth='user', sitemap=False)
    def portal_knowledge_detail(self, slug, **kw):
        Article = request.env['wujia.knowledge.article'].sudo()
        article = Article.search(Article._portal_visible_domain() + [('slug', '=', slug)], limit=1)
        if not article:
            return request.redirect('/portal/knowledge?notice=article_gone')
        article.action_increment_view()
        related = Article.search(
            Article._portal_visible_domain() + [
                ('category_id', '=', article.category_id.id),
                ('id', '!=', article.id),
            ], order='publish_date desc', limit=4)
        return request.render('wujia_portal_knowledge.portal_knowledge_detail', {
            'article': article, 'related': related, 'wj_dt': fmt_local_dt,
        })

    @http.route(['/portal/knowledge/<string:slug>/attachment/<int:att_id>'],
                type='http', auth='user', sitemap=False)
    def portal_knowledge_attachment_download(self, slug, att_id, **kw):
        """Stream attachment bài viết (Sprint 15 — mobile bấm tải thật).

        ACL: bài phải đang hiện trên portal + attachment phải thuộc bài (m2m
        attachment_ids hoặc res_model/res_id trỏ về bài). KHÔNG dùng
        check_attachment_access (util đó check theo franchise — knowledge
        là global published cho mọi portal user).
        """
        Article = request.env['wujia.knowledge.article'].sudo()
        article = Article.search(Article._portal_visible_domain() + [('slug', '=', slug)], limit=1)
        if not article:
            return request.redirect('/portal/knowledge?notice=article_gone')
        att = article._portal_get_attachment(att_id)
        if not att:
            raise Forbidden()
        return request.env['ir.binary']._get_stream_from(att).get_response(
            as_attachment=True,
        )

    @http.route(['/portal/knowledge/search'], type='json',
                auth='user', methods=['POST', 'GET'])
    def portal_knowledge_search_ajax(self, keyword='', limit=10, **kw):
        """Search-as-you-type — debounce client-side 300ms."""
        keyword = (keyword or '').strip()
        if len(keyword) < 2:
            return {'results': []}
        try:
            limit = max(1, min(int(limit), 20))
        except (TypeError, ValueError):
            limit = 10
        Article = request.env['wujia.knowledge.article'].sudo()
        articles = Article.search(
            Article._portal_visible_domain() + Article._portal_search_domain(keyword),
            limit=limit, order='publish_date desc')
        return {'results': [
            {
                'id': a.id,
                'name': a.name,
                'slug': a.slug,
                'category': a.category_id.name or '',
                'url': '/portal/knowledge/%s' % (a.slug or a.id),
            }
            for a in articles
        ]}
