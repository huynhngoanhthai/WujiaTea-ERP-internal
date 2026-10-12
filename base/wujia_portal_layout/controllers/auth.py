"""Wujia portal authentication controllers.

Routes:
- /portal/login (GET/POST)
- /portal/logout (GET)
- /portal/redirect (GET)
- /portal/forgot-pass (GET/POST) — rate-limited 10/hour/IP, defer email-exists leak
- /portal/reset_password (GET/POST) — token-based reset, uses auth_signup.do_signup
"""
import logging

import odoo
from odoo import _, http
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.exceptions import UserError
from odoo.http import request
from odoo.addons.web.controllers.home import ensure_db

from odoo.addons.wujia_portal_base.controllers.utils import rate_limit
from odoo.addons.wujia_portal_layout.controllers.portal import PRE_LOGIN_LANG

_logger = logging.getLogger(__name__)


# Inherit AuthSignupHome (subclass của web.Home) — có sẵn get_auth_signup_qcontext()
# và do_signup() để gọi từ reset_password flow.
class WujiaAuthController(AuthSignupHome):

    @http.route('/portal/login', type='http', auth='public', sitemap=False)
    def portal_login(self, redirect=None, **kw):
        ensure_db()
        request.params['login_success'] = False

        if request.httprequest.method == 'GET' and request.session.uid:
            return request.redirect(redirect or '/portal/redirect')

        values = {k: v for k, v in request.params.items() if k != 'password'}

        if request.httprequest.method == 'POST':
            try:
                credential = {
                    'login': request.params.get('login') or '',
                    'password': request.params.get('password') or '',
                    'type': 'password',
                }
                request.session.authenticate(request.env, credential)
                request.params['login_success'] = True
                self._apply_pre_login_lang()
                if redirect:
                    return request.redirect(redirect)
                if request.env.user.has_group('base.group_user'):
                    return request.redirect('/odoo')
                return request.redirect('/portal')
            except odoo.exceptions.AccessDenied as e:
                if e.args == odoo.exceptions.AccessDenied().args:
                    values['error'] = _("Wrong login/password")
                else:
                    values['error'] = e.args[0]

        if 'login' not in values and request.session.get('auth_login'):
            values['login'] = request.session.get('auth_login')

        return request.render('wujia_portal_layout.login', values)

    def _apply_pre_login_lang(self):
        """Giữ ngôn ngữ đã chọn ở màn đăng nhập: authenticate() ghi đè
        context['lang'] bằng res.users.lang, nên phải ghi lại vào tài khoản."""
        code = request.session.pop(PRE_LOGIN_LANG, None)
        if code and code != request.env.user.lang:
            request.env.user.sudo().lang = code
            request.session.context = dict(request.session.context or {}, lang=code)

    @http.route('/portal/logout', type='http', auth='public', sitemap=False)
    def portal_logout(self, redirect='/portal/login'):
        request.session.logout(keep_db=True)
        return request.redirect(redirect)

    @http.route('/portal/redirect', type='http', auth='user', sitemap=False)
    def portal_post_login_redirect(self, **kw):
        if request.env.user.has_group('base.group_user'):
            return request.redirect('/odoo')
        return request.redirect('/portal')

    # ==================================================================
    # Forgot password — rate-limited 10/hour/IP, không leak email tồn tại
    # ==================================================================
    @http.route('/portal/forgot-pass', type='http', auth='public',
                methods=['GET', 'POST'], sitemap=False, csrf=True)
    @rate_limit(max_calls=10, window_sec=3600)
    def portal_forgot_password(self, **kw):
        ensure_db()
        values = {k: v for k, v in kw.items() if k != 'password'}

        if request.httprequest.method == 'POST':
            login = (kw.get('login') or '').strip()
            if not login:
                values['error'] = _('Please enter your email.')
                return request.render('wujia_portal_layout.forgot_pass', values)
            try:
                # sudo() vì public user không có quyền search res.users
                request.env['res.users'].sudo().reset_password(login)
            except UserError as e:
                # Có thể là "no user found" hoặc "email config missing".
                # Security: log đầy đủ, nhưng response generic message
                # để tránh email-enumeration attack.
                _logger.info(
                    'Forgot password attempt for %s failed: %s', login, e
                )
            except Exception:
                _logger.exception('Forgot password unexpected error for %s', login)
            # Luôn show success message (anti email-enumeration)
            return request.render('wujia_portal_layout.forgot_pass', {
                'message': _(
                    'If the email exists in our system, password reset instructions '
                    'have been sent to your inbox.'
                ),
            })
        return request.render('wujia_portal_layout.forgot_pass', values)

    # ==================================================================
    # Reset password — qua token email
    # ==================================================================
    @http.route('/portal/reset_password', type='http', auth='public',
                methods=['GET', 'POST'], sitemap=False, csrf=True)
    def portal_reset_password(self, **kw):
        ensure_db()
        qcontext = self.get_auth_signup_qcontext()
        # qcontext có: db, token, login, name (decode từ partner_id qua token)

        if not qcontext.get('token'):
            return request.redirect('/portal/login?message=invalid_token')

        if request.httprequest.method == 'POST':
            password = qcontext.get('password') or ''
            confirm = qcontext.get('confirm_password') or ''
            if not password or password != confirm:
                qcontext['error'] = _('Password confirmation does not match.')
            elif len(password) < 8:
                qcontext['error'] = _('Password must be at least 8 characters.')
            else:
                try:
                    self.do_signup(qcontext)
                    return request.redirect(
                        '/portal/login?message=password_reset_ok'
                    )
                except UserError as e:
                    qcontext['error'] = str(e)
                except Exception:
                    _logger.exception('Reset password error')
                    qcontext['error'] = _('Something went wrong. Please try again.')

        return request.render('wujia_portal_layout.reset_pass', qcontext)
