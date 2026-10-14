from werkzeug.exceptions import Forbidden, NotFound

from odoo import http
from odoo.http import request
from odoo.tools.translate import LazyTranslate

from odoo.addons.wujia_portal_base.controllers.portal import (
    get_current_store_ids, get_store_scope_state,
)
from odoo.addons.wujia_portal_base.controllers.utils import (
    DEFAULT_DOC_MIME,
    attach_files_to_record,
    build_pager,
    fmt_local_dt,
    status_badge,
    status_badge_for,
)

_lt = LazyTranslate(__name__)

PAGE_SIZE = 20

# Display labels for portal templates — keys map to ticket.state values. `_lt` ⇒ dịch lúc render
# bằng `_translated` (ngôn ngữ người xem). Màu theo bảng chung `status_badge_for`; "Canceled" (vi "Đã huỷ")
# không có trong bảng nên ghim danger như trước J-V7.
STATE_LABELS = {
    'new': (_lt('New'), status_badge_for(_lt('New'))),
    'in_progress': (_lt('Processing'), status_badge_for(_lt('Processing'))),
    'waiting_customer': (_lt('Awaiting reply'), status_badge_for(_lt('Awaiting reply'))),
    'resolved': (_lt('Resolved'), status_badge_for(_lt('Resolved'))),
    'closed': (_lt('Closed'), status_badge_for(_lt('Closed'))),
    'cancelled': (_lt('Canceled'), status_badge('danger')),
}

# Nhãn MOBILE (Figma Mobile_Ticket), tách khỏi STATE_LABELS desktop. LƯU Ý
# 'waiting_customer'="Replied" (mobile/Figma) ≠ desktop "Awaiting reply" — drift chủ đích, đối chiếu BA.
MOBILE_TICKET_BADGES = {
    'new':              (_lt('New'), status_badge('info')),
    'in_progress':      (_lt('Processing'), status_badge('processing')),
    'waiting_customer': (_lt('Replied'), status_badge('feedback')),
    'resolved':         (_lt('Resolved'), status_badge('success')),
    'closed':           (_lt('Closed'), status_badge('neutral')),
    'cancelled':        (_lt('Canceled'), status_badge('danger')),
}

# Một nguồn nhãn mức độ cho PC + mobile, danh sách + chi tiết (WJ-SUPPORT-003).
PRIORITY_LABELS = {
    'normal': (_lt('Normal'), 'wujia-badge-muted'),
    'urgent': (_lt('Urgent'), 'wujia-badge-danger'),
}


# Mã lỗi form → field bị đánh dấu lỗi, cùng cho PC + mobile.
ERROR_FIELDS = {
    'missing_fields': ('title', 'category_id'),
    'invalid_franchise': ('franchise_id',),
    'invalid_input': ('category_id',),
    'invalid_attachment': ('attachments',),
}

META_LABELS = {
    'category': _lt('Classification'),
    'priority': _lt('Severity'),
    'sender': _lt('Sender'),
    'sent': _lt('Sent on'),
    'assignee': _lt('Assignee'),
    'resolved': _lt('Resolved on'),
}
META_EMPTY = {
    'assignee': _lt('Not assigned yet'),
    'resolved': _lt('Not resolved yet'),
}


def _translated(labels):
    """{key: (nhãn, class)} với nhãn `_lt` dịch theo ngôn ngữ người xem (không `str(lazy)`)."""
    result = {}
    for key, (label, css) in labels.items():
        result[key] = (request.env._(label), css)
    return result


def _label_ctx():
    return {
        'state_labels': _translated(STATE_LABELS),
        'priority_labels': _translated(PRIORITY_LABELS),
        'm_ticket_badges': _translated(MOBILE_TICKET_BADGES),
    }


def _ticket_meta(ticket):
    """Thẻ thông tin chi tiết ticket — một danh sách cho PC + mobile."""
    tr = request.env._
    prio = PRIORITY_LABELS.get(ticket.priority)
    rows = (
        ('category', 'tag', ticket.category_id.name or '—'),
        ('priority', 'flag', tr(prio[0]) if prio else ticket.priority),
        ('sender', 'user', ticket.created_by_id.name or '—'),
        ('sent', 'calendar', fmt_local_dt(ticket.create_date, '%d/%m/%Y %H:%M') or '—'),
        ('assignee', 'user-check', ticket.assigned_user_id.name or tr(META_EMPTY['assignee'])),
        ('resolved', 'check-circle', fmt_local_dt(ticket.resolved_date, '%d/%m/%Y') or tr(META_EMPTY['resolved'])),
    )
    return [{'key': key, 'icon': icon, 'label': tr(META_LABELS[key]), 'value': value}
            for key, icon, value in rows]


def _categories():
    return request.env['wujia.support.category'].sudo().search(
        [('active', '=', True)], order='sequence, name',
    )


def _scoped_ticket(ticket_id):
    Ticket = request.env['wujia.support.ticket'].sudo()
    return Ticket.search(
        [('id', '=', ticket_id)] + Ticket._portal_scope_domain(request.env.user, get_current_store_ids()),
        limit=1,
    )


class WujiaPortalSupport(http.Controller):

    @http.route(['/portal/support'], type='http', auth='user', sitemap=False)
    def portal_support_list(self, page=1, state='', q='', **kw):
        franchise_ids = get_current_store_ids()
        if not franchise_ids:
            return request.render('wujia_portal_support.portal_support_list', {
                'tickets': [], 'pgn': None, **_label_ctx(), 'state': '', 'q': '',
                'no_franchise': True, 'store_scope': get_store_scope_state(),
            })
        Ticket = request.env['wujia.support.ticket'].sudo()
        domain = Ticket._portal_scope_domain(request.env.user, franchise_ids) + [('state', '!=', 'cancelled')]
        if state and state in STATE_LABELS:
            domain.append(('state', '=', state))
        # Sprint 17 — tìm theo Mã (name) HOẶC Tiêu đề (title). ilike trigram-friendly.
        q = (q or '').strip()
        if q:
            domain += ['|', ('name', 'ilike', q), ('title', 'ilike', q)]
        try:
            page = max(1, int(page))
        except (TypeError, ValueError):
            page = 1
        offset = (page - 1) * PAGE_SIZE
        total = Ticket.search_count(domain)
        tickets = Ticket.search(
            domain, limit=PAGE_SIZE, offset=offset, order='create_date desc',
        )
        pgn = build_pager(total, page, PAGE_SIZE, path='/portal/support',
                          item_label=_lt('requests'))
        return request.render('wujia_portal_support.portal_support_list', {
            'tickets': tickets, 'pgn': pgn, 'wj_dt': fmt_local_dt,
            **_label_ctx(),
            'state': state,
            'q': q,
        })

    @http.route(['/portal/support/new'], type='http', auth='user', sitemap=False,
                methods=['GET'])
    def portal_support_new(self, **kw):
        franchise_ids = get_current_store_ids()
        if not franchise_ids:
            return request.redirect('/portal/support')
        franchises = request.env['wujia.franchise.management'].sudo().browse(franchise_ids)
        error = kw.get('error', '')
        if error not in ERROR_FIELDS:
            error = ''
        return request.render('wujia_portal_support.portal_support_form', {
            'franchises': franchises,
            'categories': _categories(),
            'priority_options': [(key, label) for key, (label, _css) in _translated(PRIORITY_LABELS).items()],
            'error': error,
            'error_fields': ERROR_FIELDS.get(error, ()),
        })

    @http.route(['/portal/support/new'], type='http', auth='user', sitemap=False,
                methods=['POST'], csrf=True)
    def portal_support_create(self, **post):
        try:
            franchise_id = int(post.get('franchise_id') or 0)
            category_id = int(post.get('category_id') or 0)
        except (TypeError, ValueError):
            return request.redirect('/portal/support/new?error=invalid_input')
        # Accept both 'title' (new) and 'subject' (legacy) form keys.
        title = (post.get('title') or post.get('subject') or '').strip()
        files = request.httprequest.files.getlist('attachments')
        ticket, error = request.env['wujia.support.ticket'].sudo().create_from_portal({
            'title': title,
            'description': (post.get('description') or '').strip(),
            'franchise_id': franchise_id,
            'created_by_id': request.env.user.id,
            'category_id': category_id,
            'priority': post.get('priority', 'normal'),
        }, get_current_store_ids(), attach=lambda t: attach_files_to_record(
            t, files, allowed_mime=DEFAULT_DOC_MIME, max_size_mb=5, max_count=6,
        ))
        if error:
            return request.redirect(f'/portal/support/new?error={error}')
        return request.redirect(f'/portal/support/{ticket.id}')

    @http.route(['/portal/support/<int:ticket_id>'],
                type='http', auth='user', sitemap=False)
    def portal_support_detail(self, ticket_id, **kw):
        ticket = _scoped_ticket(ticket_id)
        if not ticket:
            return request.redirect('/portal/support')
        return request.render('wujia_portal_support.portal_support_detail', {
            'ticket': ticket,
            'meta': _ticket_meta(ticket),
            'wj_dt': fmt_local_dt,
            **_label_ctx(),
        })

    @http.route(['/portal/support/<int:ticket_id>/reply'],
                type='http', auth='user', sitemap=False,
                methods=['POST'], csrf=True)
    def portal_support_reply(self, ticket_id, **post):
        ticket = _scoped_ticket(ticket_id)
        if not ticket:
            return request.redirect('/portal/support')
        ticket._portal_reply(request.env.user, post.get('body'))
        return request.redirect(f'/portal/support/{ticket_id}')

    @http.route(['/portal/support/<int:ticket_id>/attachment/<int:att_id>'],
                type='http', auth='user', sitemap=False)
    def portal_support_attachment_download(self, ticket_id, att_id, **kw):
        """Stream attachment với ACL: chỉ owner ticket được tải."""
        ticket = _scoped_ticket(ticket_id)
        if not ticket:
            raise NotFound()
        att = ticket._portal_get_attachment(att_id)
        if not att:
            raise Forbidden()
        return request.env['ir.binary']._get_stream_from(att).get_response(
            as_attachment=True,
        )
