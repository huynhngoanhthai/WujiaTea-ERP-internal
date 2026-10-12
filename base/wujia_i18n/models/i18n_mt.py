import hashlib
import json
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..tools import mt_deepl
from .i18n_term import DB_KINDS

_logger = logging.getLogger(__name__)

PARAM_PROVIDER = 'wujia_i18n.mt_provider'
PARAM_KEY = 'wujia_i18n.deepl_api_key'
PARAM_ERROR = 'wujia_i18n.mt_last_error'
PARAM_CAPS = 'wujia_i18n.mt_capabilities'
SCOPE_STATES = {
    'missing': ('missing',),
    'refresh': ('missing', 'synced', 'machine'),  # không bao giờ đè bản người sửa (override)
}
QUEUE_PAGE = 500


class WujiaI18nValue(models.Model):
    """Dịch máy (J-T5): xếp hàng → cron dịch theo lô → ghi state `machine` + áp ngay nhãn/menu/view."""
    _inherit = 'wujia.i18n.value'

    # ------------------------------------------------------------------ provider
    @api.model
    def _wj_mt_client(self):
        ICP = self.env['ir.config_parameter'].sudo()
        provider = ICP.get_param(PARAM_PROVIDER) or 'deepl'
        key = ICP.get_param(PARAM_KEY)
        if not key:
            raise UserError(_('Enter the DeepL API key in Settings → Translation Tool first.'))
        if provider not in mt_deepl.PROVIDERS:
            raise UserError(_('Unknown machine translation provider: %s', provider))
        return mt_deepl.PROVIDERS[provider](key)

    @api.model
    def _wj_mt_capabilities(self, client, refresh=False):
        """{'targets': {mã đích}, 'pairs': {(nguồn, đích)}} — hỏi DeepL 1 lần/ngày/key, lưu ir.config_parameter."""
        ICP = self.env['ir.config_parameter'].sudo()
        fingerprint = hashlib.md5(client.api_key.encode()).hexdigest()[:8]
        today = fields.Date.today().isoformat()
        try:
            cached = json.loads(ICP.get_param(PARAM_CAPS) or '{}')
        except ValueError:
            cached = {}
        if refresh or cached.get('date') != today or cached.get('key') != fingerprint:
            cached = {
                'date': today, 'key': fingerprint, 'provider': client.name,
                'targets': sorted(client.target_languages()),
                'pairs': sorted([list(p) for p in client.glossary_pairs()]),
            }
            ICP.set_param(PARAM_CAPS, json.dumps(cached))
        return {'targets': set(cached['targets']), 'pairs': {tuple(p) for p in cached['pairs']}}

    @api.model
    def _wj_mt_cached_targets(self):
        """Danh sách ngôn ngữ đích lần hỏi gần nhất (không gọi mạng) — None nếu chưa hỏi."""
        try:
            cached = json.loads(self.env['ir.config_parameter'].sudo().get_param(PARAM_CAPS) or '{}')
        except ValueError:
            return None
        return set(cached['targets']) if cached.get('targets') else None

    # ------------------------------------------------------------------ queue
    @api.model
    def _wj_mt_domain(self, lang, modules, scope='missing'):
        return [('lang', '=', lang), ('module', 'in', list(modules)), ('state', 'in', SCOPE_STATES[scope]),
                ('term_active', '=', True)]

    @api.model
    def _wj_mt_enqueue(self, lang, modules, scope='missing'):
        values = self.sudo().search(self._wj_mt_domain(lang, modules, scope))
        values.with_context(wj_i18n_scan=True).write({'mt_queued': True, 'mt_error': False})
        if values:
            self.env.ref('wujia_i18n.ir_cron_wujia_i18n_mt').sudo()._trigger()
        _logger.info('wujia_i18n machine translation: %s strings queued for %s', len(values), lang)
        return values

    @api.model
    def _wj_mt_run_queue(self, max_batches=None):
        """Cron: dịch hàng đợi theo lô. Hết hạn mức / key sai ⇒ dừng, giữ hàng đợi; DeepL bận ⇒ hẹn lại 1 phút."""
        Value = self.sudo().with_context(wj_i18n_scan=True)
        ICP = self.env['ir.config_parameter'].sudo()
        cron = self.env.ref('wujia_i18n.ir_cron_wujia_i18n_mt').sudo()
        in_cron = bool(self.env.context.get('cron_id'))
        if not Value.search_count([('mt_queued', '=', True)], limit=1):
            return 0
        try:
            client = Value._wj_mt_client()
            caps = Value._wj_mt_capabilities(client)
        except UserError as e:
            ICP.set_param(PARAM_ERROR, str(e))
            return 0
        except mt_deepl.MTError as e:
            return self._wj_mt_stop(e, cron)

        done = batches_run = 0
        while True:
            page = Value.search([('mt_queued', '=', True)], order='lang, id', limit=QUEUE_PAGE)
            if not page:
                ICP.set_param(PARAM_ERROR, '')
                break
            lang = page[0].lang
            same_lang = page.filtered(lambda v: v.lang == lang)
            if mt_deepl.deepl_target(lang) not in caps['targets']:
                Value.search([('mt_queued', '=', True), ('lang', '=', lang)]).write({
                    'mt_queued': False, 'mt_error': _('Language not supported by DeepL')})
                continue
            batch = Value.browse([v.id for v in next(mt_deepl.batches(same_lang, size_of=lambda v: len(v.src or '')))])
            try:
                batch._wj_mt_translate_batch(client, caps, lang)
            except mt_deepl.MTError as e:
                if e.kind != 'other':
                    return done + self._wj_mt_stop(e, cron)
                batch.write({'mt_queued': False, 'mt_error': str(e)[:250]})
            done += len(batch)
            batches_run += 1
            if in_cron:
                left = Value.search_count([('mt_queued', '=', True)])
                if self.env['ir.cron']._commit_progress(len(batch), remaining=left) < 30 and left:
                    cron._trigger()
                    break
            if max_batches and batches_run >= max_batches:
                break
        _logger.info('wujia_i18n machine translation: %s strings processed', done)
        return done

    @api.model
    def _wj_mt_stop(self, error, cron):
        self.env['ir.config_parameter'].sudo().set_param(PARAM_ERROR, f'{error.kind}: {error}')
        _logger.warning('wujia_i18n machine translation stopped (%s): %s', error.kind, error)
        if error.kind == 'rate':
            cron._trigger(at=fields.Datetime.now() + timedelta(minutes=1))
        return 0

    def _wj_mt_translate_batch(self, client, caps, lang):
        """1 lô cùng ngôn ngữ: bảo toàn định dạng → DeepL → kiểm → ghi `machine`; nhãn/menu/view áp ngay."""
        Glossary = self.env['wujia.i18n.glossary']
        keep, mapping = Glossary._wj_terms(lang)
        target = mt_deepl.deepl_target(lang)
        has_pair = ('en', mt_deepl.deepl_glossary_lang(lang)) in caps['pairs']
        glossary_id = Glossary._wj_deepl_glossary_id(client, lang, mapping) if has_pair else None
        # Cặp ngôn ngữ không có glossary ⇒ thay thuật ngữ bằng bản dịch đã chốt (bọc thẻ giữ nguyên).
        fallback = {} if has_pair else mapping

        keep_re = mt_deepl._term_pattern(keep)
        groups = {'en': self.browse(), 'auto': self.browse()}
        for val in self:
            text = keep_re.sub('', val.src) if keep_re else val.src
            groups['auto' if mt_deepl.is_vietnamese(text) else 'en'] |= val

        results = {}
        for group, source, gid, repl in ((groups['en'], 'EN', glossary_id, fallback),
                                         (groups['auto'], None, None, {})):
            if not group:
                continue
            prepared = [mt_deepl.protect(v.src, v.kind == 'model_terms', keep, repl) for v in group]
            out = client.translate([p[0] for p in prepared], target, source=source, glossary_id=gid)
            for val, (_text, meta), raw in zip(group, prepared, out):
                try:
                    final = mt_deepl.restore(raw, meta)
                except ValueError as e:
                    results[val.id] = (None, str(e))
                    continue
                err = mt_deepl.check(val.src, final, meta['markup'])
                results[val.id] = (None, err) if err else (final, '')

        # Đọc lại: người vừa sửa tay trong lúc chờ DeepL ⇒ giữ bản người.
        self.invalidate_recordset(['state', 'mt_queued'])
        done = self.browse()
        for val in self:
            value, err = results.get(val.id, (None, 'not translated'))
            if val.state == 'override' or not val.mt_queued:
                val.write({'mt_queued': False})
            elif err:
                val.write({'mt_queued': False, 'mt_error': err[:250]})
            else:
                val.write({'value': value, 'state': 'machine', 'mt_queued': False, 'mt_error': False,
                           'pending': val.kind not in DB_KINDS})
                done |= val
        done.filtered(lambda v: v.kind in DB_KINDS)._wj_apply()
        return done
