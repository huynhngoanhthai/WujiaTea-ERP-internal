from odoo import fields, models


class WujiaKnowledgeTag(models.Model):
    _name = 'wujia.knowledge.tag'
    _description = 'Wujia Knowledge Tag'
    _order = 'name'

    name = fields.Char(string='Tag', required=True, translate=True)
    color = fields.Integer(string='Color', default=0)
    active = fields.Boolean(string='Active', default=True)
    article_count = fields.Integer(
        string='Articles', compute='_compute_article_count',
    )

    _sql_constraints = [
        ('uniq_name', 'unique(name)', 'Tag name must be unique.'),
    ]

    def _compute_article_count(self):
        Article = self.env['wujia.knowledge.article'].sudo()
        groups = Article._read_group(
            [('tag_ids', 'in', self.ids), ('state', '=', 'published')],
            groupby=['tag_ids'], aggregates=['__count'],
        )
        mapping = {tag.id: count for tag, count in groups}
        for tag in self:
            tag.article_count = mapping.get(tag.id, 0)
