"""Wujia portal — profile + change password controllers.

Routes:
- /portal/profile (GET) — render hồ sơ user.
- /portal/profile/update (POST) — update name/email/phone/street + avatar upload.
- /portal/profile/avatar/<int:user_id> (GET) — serve avatar (ETag + Cache-Control).
- /portal/change-password (GET/POST) — đổi mật khẩu (validate old qua _check_credentials).
"""
import base64
import logging
import re
from urllib.parse import quote, urlparse

from werkzeug.exceptions import Forbidden, NotFound

from odoo import _, http
from odoo.exceptions import AccessDenied, UserError, ValidationError
from odoo.http import request
from odoo.tools.translate import LazyTranslate

from .utils import safe_local_path

_logger = logging.getLogger(__name__)


# Ngôn ngữ khách chọn ở màn đăng nhập — auth.py áp vào res.users sau khi vào.
PRE_LOGIN_LANG = 'wj_pre_login_lang'

_PHONE_RE = re.compile(r'^[+]?[0-9\s().\-]{7,20}$')
_AVATAR_MAX_BYTES = 2 * 1024 * 1024  # 2MB
_AVATAR_MIME = ('image/png', 'image/jpeg', 'image/jpg', 'image/webp')

# Role label map — bản local (wujia_portal_layout KHÔNG depend wujia_portal_base
# nên KHÔNG import ROLE_LABELS từ đó; xem registry-guard ở _resolve_active_store).
_lt = LazyTranslate(__name__)
_ROLE_LABELS = {'owner': _lt('Store owner'), 'manager': _lt('Manager'), 'staff': _lt('Staff')}
# Cookie chứa franchise đang chọn — owned by wujia_portal_base. Đọc theo tên
# (coupling bằng string, có guard) để hiển thị "Cửa hàng / Vai trò" ở màn profile.
_ACTIVE_FRANCHISE_COOKIE = 'wujia_active_franchise_id'


class WujiaPortalLayout(http.Controller):
    """Layout-only routes. Route `/portal` (dashboard) đã chuyển sang
    wujia_portal_base để aggregate counter từ các module khác (xem ADR-016)."""

    # ------------------------------------------------------------------ profile
    def _resolve_active_store(self):
        """Trả (franchise_name, franchise_code, role_label) cho cửa hàng đang
        active — phục vụ màn mobile "Thông tin tài khoản" (Figma 01).

        Registry-guard: layout KHÔNG depend wujia_portal_base/franchise; nếu
        thiếu model / multi-franchise chưa chọn → trả 3× None (template hiện "—").
        Lọc is_currently_valid bằng Python (field computed, tránh phụ thuộc
        search method)."""
        Member = request.env.get('wujia.franchise.member')
        if Member is None:
            return None, None, None
        try:
            members = Member.sudo().search(
                [('user_id', '=', request.env.uid)]
            ).filtered('is_currently_valid')
            if not members:
                return None, None, None
            raw = request.httprequest.cookies.get(_ACTIVE_FRANCHISE_COOKIE)
            active_fid = int(raw) if raw else False
            member = members.filtered(
                lambda m: m.franchise_id.id == active_fid
            )[:1] if active_fid else members[:0]
            if not member and len(members) == 1:
                member = members
            if not member:
                return None, None, None  # multi-franchise chưa chọn store
            fr = member.franchise_id
            return fr.name, fr.code, str(_ROLE_LABELS.get(member.role, member.role))
        except (ValueError, TypeError, AccessDenied):
            return None, None, None

    @http.route('/portal/profile', type='http', auth='user', website=False,
                sitemap=False)
    def portal_profile(self, **kw):
        fr_name, fr_code, role_label = self._resolve_active_store()
        return request.render('wujia_portal_layout.profile_page', {
            'title': _('Profile'),
            'lang': request.env.lang or 'en',
            'profile': request.env.user.partner_id,
            'user': request.env.user,
            'franchise_name': fr_name,
            'franchise_code': fr_code,
            'role_label': role_label,
            'message': kw.get('message'),
            'error': kw.get('error'),
        })

    @http.route('/portal/profile/update', type='http', auth='user',
                methods=['POST'], website=False, sitemap=False, csrf=True)
    def portal_profile_update(self, **post):
        """Validate + persist partner fields + optional avatar upload.

        PRG redirect on success (anti F5 double-submit).
        """
        user = request.env.user
        partner = user.partner_id
        name = (post.get('name') or '').strip()
        email = (post.get('email') or '').strip()
        phone = (post.get('phone') or '').strip()
        street = (post.get('street') or '').strip()

        # Validation
        if not name:
            return request.redirect('/portal/profile?error=' + _('Full name is required'))
        if phone and not _PHONE_RE.match(phone):
            return request.redirect('/portal/profile?error=' + _('Invalid phone number'))

        # Build partner vals — KHÔNG cho đổi login email (chỉ partner contact email).
        vals = {'name': name, 'phone': phone, 'street': street}
        if email and email != partner.email:
            vals['email'] = email
            _logger.info('Portal user %s changed contact email %s → %s',
                         user.login, partner.email, email)

        try:
            partner.sudo().write(vals)
        except (UserError, ValidationError) as e:
            return request.redirect('/portal/profile?error=' + quote(str(e)))

        # Avatar upload — optional. Size + MIME validation backend.
        avatar = request.httprequest.files.get('avatar')
        if avatar and avatar.filename:
            data = avatar.read()
            if len(data) > _AVATAR_MAX_BYTES:
                return request.redirect('/portal/profile?error=' + _('Avatar exceeds 2MB'))
            if avatar.mimetype not in _AVATAR_MIME:
                return request.redirect('/portal/profile?error=' + _('Unsupported image format'))
            try:
                # image_1920 → Odoo auto-generate _128/_256/_512.
                user.sudo().write({'image_1920': base64.b64encode(data)})
            except Exception:
                _logger.exception('Avatar write failed for user %s', user.login)
                return request.redirect('/portal/profile?error=' + _('Failed to save image'))

        return request.redirect('/portal/profile?message=' + _('Updated successfully'))

    @http.route('/portal/profile/avatar/<int:user_id>', type='http',
                auth='user', website=False, sitemap=False)
    def portal_profile_avatar(self, user_id, **kw):
        """Serve avatar ảnh với ACL theo accessible franchise.

        ETag + Cache-Control: private, max-age=300 → giảm DB load 1500 user.
        """
        User = request.env['res.users'].sudo()
        target = User.browse(int(user_id)).exists()
        if not target:
            raise NotFound()

        # ACL: self luôn OK, còn lại phải share franchise.
        if target.id != request.env.uid:
            # ADR-027 R2: khung không depend nghiệp vụ. `wujia_franchise` tắt ⇒ không
            # ai ngoài chính chủ xem được ảnh (đóng, không 500).
            _get_fids = getattr(request.env.user, '_get_accessible_franchise_ids', None)
            accessible_fids = set(_get_fids()) if _get_fids else set()
            target_fids = set(
                target.mapped('member_ids.franchise_id.id')
            ) if 'member_ids' in target._fields else set()
            if not (accessible_fids & target_fids):
                raise Forbidden()

        stream = request.env['ir.binary']._get_image_stream_from(
            target, 'avatar_256',
        )
        response = stream.get_response(as_attachment=False)
        response.headers['Cache-Control'] = 'private, max-age=300'
        return response

    # ----------------------------------------------------------- change password
    @http.route('/portal/change-password', type='http', auth='user',
                methods=['GET', 'POST'], website=False, sitemap=False,
                csrf=True)
    def portal_change_password(self, **post):
        # Store/role feed the shared PC account-nav card (Figma pc_05..08).
        fr_name, fr_code, role_label = self._resolve_active_store()
        values = {
            'title': _('Change password'),
            'lang': request.env.lang or 'en',
            'user': request.env.user,
            'franchise_name': fr_name,
            'franchise_code': fr_code,
            'role_label': role_label,
        }
        if request.httprequest.method != 'POST':
            return request.render('wujia_portal_layout.change_password_page', values)

        old_pwd = post.get('old-password') or ''
        new_pwd = post.get('new-password') or ''
        confirm = post.get('con-password') or ''

        # error_field = ô cần viền đỏ; template đọc mã này, không dò chữ trong câu lỗi
        # (câu lỗi đã dịch theo ngôn ngữ user).
        if not old_pwd or not new_pwd:
            values['error'] = _('Please fill in all fields.')
        elif new_pwd != confirm:
            values['error'] = _('Password confirmation does not match the new password.')
            values['error_field'] = 'confirm'
        elif len(new_pwd) < 8:
            values['error'] = _('New password must be at least 8 characters.')
            values['error_field'] = 'new'
        elif new_pwd == old_pwd:
            values['error'] = _('New password must differ from the old password.')
            values['error_field'] = 'new'
        else:
            try:
                # change_password(old, new) tự verify old qua _check_credentials.
                request.env['res.users'].change_password(old_pwd, new_pwd)
                values['message'] = _('Your password has been updated.')
            except AccessDenied:
                values['error'] = _('Current password is incorrect. Please check again.')
                values['error_field'] = 'old'
            except UserError as e:
                values['error'] = str(e)
            except Exception:
                _logger.exception('Change password failed for %s',
                                  request.env.user.login)
                values['error'] = _('Something went wrong. Please try again.')

        return request.render('wujia_portal_layout.change_password_page', values)

    # -------------------------------------------------------------- switch language
    @http.route('/portal/set-lang/<string:lang_code>', type='http', auth='public',
                website=False, sitemap=False)
    def portal_set_lang(self, lang_code, **kw):
        """Đổi ngôn ngữ portal. Thay route /website/lang/* của module website —
        website KHÔNG cài trên portal Vuexy nên route đó 404 (bug đổi ngôn ngữ).
        Chỉ nhận ngôn ngữ đang bật + URL nội bộ (tránh open-redirect). Khách chưa
        đăng nhập cũng đổi được để dùng ở màn login (WJ-LANG-001)."""
        lang = request.env['res.lang'].sudo().search(
            [('code', '=', lang_code), ('active', '=', True)], limit=1)
        if lang:
            # Session cache context['lang'] từ lúc login → phải cập nhật để đổi
            # ngôn ngữ có hiệu lực NGAY ở request kế (setter đánh dấu dirty → lưu).
            request.session.context = dict(request.session.context or {}, lang=lang.code)
            if request.env.user._is_public():
                # Chưa có tài khoản để ghi → nhớ tạm, portal_login áp sau khi vào.
                request.session[PRE_LOGIN_LANG] = lang.code
            else:
                request.env.user.sudo().lang = lang.code
        target = safe_local_path(request.httprequest.referrer,
                                 host=urlparse(request.httprequest.url).netloc)
        return request.redirect(target)
