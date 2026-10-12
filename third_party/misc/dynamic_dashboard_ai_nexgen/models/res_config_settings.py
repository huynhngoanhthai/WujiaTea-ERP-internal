# Copyright (C) NexGen Solutions
from odoo import api, fields, models, _
from odoo.exceptions import UserError


# Static Cursor Cloud Agents model catalog (enriched at runtime via GET /v1/models).
CURSOR_AI_MODELS = [
    ('auto', 'Auto (Cursor default)'),
    # Composer (Cursor-native)
    ('composer-2.5', 'Composer 2.5'),
    ('composer-2.5-fast', 'Composer 2.5 Fast'),
    ('composer-2', 'Composer 2'),
    ('composer-2-fast', 'Composer 2 Fast'),
    ('composer-1.5', 'Composer 1.5'),
    ('composer', 'Composer (alias)'),
    # Claude via Cursor
    ('claude-fable-5', 'Claude Fable 5'),
    ('claude-fable-5-thinking-high', 'Claude Fable 5 Thinking (High)'),
    ('claude-mythos-5', 'Claude Mythos 5'),
    ('claude-sonnet-5', 'Claude Sonnet 5'),
    ('claude-sonnet-5-thinking-high', 'Claude Sonnet 5 Thinking (High)'),
    ('claude-opus-4.8', 'Claude Opus 4.8'),
    ('claude-opus-4-8-thinking-high', 'Claude Opus 4.8 Thinking (High)'),
    ('claude-opus-4.7', 'Claude Opus 4.7'),
    ('claude-sonnet-4', 'Claude Sonnet 4'),
    ('claude-4.6-sonnet-thinking', 'Claude 4.6 Sonnet Thinking'),
    ('claude-4.6-sonnet', 'Claude 4.6 Sonnet'),
    ('claude-4.5-sonnet-thinking', 'Claude 4.5 Sonnet Thinking'),
    ('claude-4.5-sonnet', 'Claude 4.5 Sonnet'),
    ('claude-4-sonnet-thinking', 'Claude 4 Sonnet Thinking'),
    ('claude-4-sonnet', 'Claude 4 Sonnet'),
    ('claude-3-7-sonnet-latest', 'Claude 3.7 Sonnet'),
    ('claude-3-5-sonnet-latest', 'Claude 3.5 Sonnet'),
    ('claude-3-5-haiku-latest', 'Claude 3.5 Haiku'),
    # GPT via Cursor
    ('gpt-5.6-sol', 'GPT-5.6 Sol'),
    ('gpt-5.6-sol-medium', 'GPT-5.6 Sol Medium'),
    ('gpt-5.6-terra', 'GPT-5.6 Terra'),
    ('gpt-5.6-terra-medium', 'GPT-5.6 Terra Medium'),
    ('gpt-5.6-luna', 'GPT-5.6 Luna'),
    ('gpt-5.4', 'GPT-5.4'),
    ('gpt-5', 'GPT-5'),
    ('gpt-4.1', 'GPT-4.1'),
    ('gpt-4o', 'GPT-4o'),
    ('gpt-4o-mini', 'GPT-4o Mini'),
    ('o3', 'o3'),
    ('o3-mini', 'o3 Mini'),
    ('o1', 'o1'),
    # Grok / other via Cursor
    ('cursor-grok-4.5', 'Grok 4.5'),
    ('cursor-grok-4.5-high-fast', 'Grok 4.5 High Fast'),
    ('grok-3', 'Grok 3'),
    ('gemini-2.5-pro', 'Gemini 2.5 Pro (via Cursor)'),
    ('gemini-2.5-flash', 'Gemini 2.5 Flash (via Cursor)'),
]


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dynamic_dashboard_ai_nexgen_ai_provider = fields.Selection(
        [
            ('openai', 'OpenAI'),
            ('gemini', 'Google Gemini'),
            ('claude', 'Anthropic Claude'),
            ('cursor', 'Cursor AI'),
        ],
        string="AI Provider",
        config_parameter='dynamic_dashboard_ai_nexgen.ai_provider',
        default='openai'
    )

    dynamic_dashboard_ai_nexgen_openai_api_key = fields.Char(
        string="OpenAI API Key",
        config_parameter='dynamic_dashboard_ai_nexgen.openai_api_key',
        help="API Key for generative AI dashboard creation using OpenAI."
    )

    dynamic_dashboard_ai_nexgen_gemini_api_key = fields.Char(
        string="Gemini API Key",
        config_parameter='dynamic_dashboard_ai_nexgen.gemini_api_key',
        help="API Key for generative AI dashboard creation using Google Gemini."
    )

    dynamic_dashboard_ai_nexgen_claude_api_key = fields.Char(
        string="Claude API Key",
        config_parameter='dynamic_dashboard_ai_nexgen.claude_api_key',
        help="API Key for generative AI dashboard creation using Anthropic Claude."
    )
    dynamic_dashboard_ai_nexgen_cursor_api_key = fields.Char(
        string="Cursor API Key",
        config_parameter='dynamic_dashboard_ai_nexgen.cursor_api_key',
        help="User or service-account API key from Cursor Dashboard → Integrations "
             "(key format starts with cursor_ or crsr_). Used for Cloud Agents chat.",
    )
    dynamic_dashboard_ai_nexgen_ai_max_tokens = fields.Integer(
        string="AI Max Tokens",
        config_parameter='dynamic_dashboard_ai_nexgen.ai_max_tokens',
        default=1200,
    )
    dynamic_dashboard_ai_nexgen_openai_model = fields.Selection([
        ('gpt-5.6-sol', 'GPT-5.6 Sol'),
        ('gpt-5.6-terra', 'GPT-5.6 Terra'),
        ('gpt-5.6-luna', 'GPT-5.6 Luna'),
        ('o3', 'o3'),
        ('o3-mini', 'o3 Mini'),
        ('o1', 'o1 (Latest)'),
        ('o1-preview', 'o1 Preview'),
        ('o1-mini', 'o1 Mini'),
        ('gpt-4.5-turbo', 'GPT-4.5 Turbo'),
        ('gpt-4o', 'GPT-4o'),
        ('gpt-4o-mini', 'GPT-4o Mini'),
        ('gpt-4-turbo', 'GPT-4 Turbo'),
        ('gpt-4', 'GPT-4'),
        ('gpt-3.5-turbo', 'GPT-3.5 Turbo'),
    ],
        string="OpenAI Model",
        config_parameter='dynamic_dashboard_ai_nexgen.openai_model',
        default='gpt-5.6-sol',
        help="Select the OpenAI model to use for generative AI.",
    )
    dynamic_dashboard_ai_nexgen_gemini_model = fields.Selection([
        ('gemini-3.5-pro', 'Gemini 3.5 Pro'),
        ('gemini-3.5-flash', 'Gemini 3.5 Flash'),
        ('gemini-3.1-flash-lite', 'Gemini 3.1 Flash Lite'),
        ('gemini-3.0-pro', 'Gemini 3.0 Pro'),
        ('gemini-2.5-pro', 'Gemini 2.5 Pro'),
        ('gemini-2.0-pro', 'Gemini 2.0 Pro'),
        ('gemini-2.0-flash', 'Gemini 2.0 Flash'),
        ('gemini-1.5-pro', 'Gemini 1.5 Pro'),
        ('gemini-1.5-flash', 'Gemini 1.5 Flash'),
    ],
        string="Gemini Model",
        config_parameter='dynamic_dashboard_ai_nexgen.gemini_model',
        default='gemini-3.5-pro',
        help="Current Google AI model id, e.g. gemini-3.5-flash. "
             "Deprecated ids like gemini-1.5-flash / gemini-2.0-flash are ignored automatically.",
    )

    dynamic_dashboard_ai_nexgen_claude_model = fields.Selection([
        ('claude-fable-5', 'Claude Fable 5'),
        ('claude-mythos-5', 'Claude Mythos 5'),
        ('claude-sonnet-5', 'Claude Sonnet 5'),
        ('claude-opus-4.8', 'Claude Opus 4.8'),
        ('claude-opus-4.7', 'Claude Opus 4.7'),
        ('claude-sonnet-4', 'Claude Sonnet 4'),
        ('claude-3-7-sonnet-latest', 'Claude 3.7 Sonnet'),
        ('claude-3-5-sonnet-latest', 'Claude 3.5 Sonnet'),
        ('claude-3-5-haiku-latest', 'Claude 3.5 Haiku'),
        ('claude-3-opus-latest', 'Claude 3 Opus'),
        ('claude-3-sonnet-20240229', 'Claude 3 Sonnet (Legacy)'),
        ('claude-3-haiku-20240307', 'Claude 3 Haiku (Legacy)'),
    ],
        string="Claude Model",
        config_parameter='dynamic_dashboard_ai_nexgen.claude_model',
        default='claude-fable-5',
        help="Select the Anthropic Claude model to use for generative AI.",
    )

    dynamic_dashboard_ai_nexgen_cursor_model = fields.Selection(
        selection='_selection_cursor_models',
        string="Cursor Model",
        config_parameter='dynamic_dashboard_ai_nexgen.cursor_model',
        default='composer-2.5',
        help="Model id from Cursor Cloud Agents (GET /v1/models). "
             "Use Auto to let Cursor pick, or Composer 2.5 for Cursor-native generation.",
    )

    dynamic_dashboard_ai_nexgen_google_sheets_api_key = fields.Char(
        string="Google Sheets API Key",
        config_parameter='dynamic_dashboard_ai_nexgen.google_sheets_api_key',
    )

    @api.model
    def _selection_cursor_models(self):
        """Static catalog + models previously discovered via Refresh from Cursor API."""
        ICP = self.env['ir.config_parameter'].sudo()
        seen = {m[0]: m[1] for m in CURSOR_AI_MODELS}
        try:
            import json
            extra = json.loads(ICP.get_param('dynamic_dashboard_ai_nexgen.cursor_models_extra') or '[]')
            for item in extra:
                mid = (item.get('id') or '').strip()
                if not mid:
                    continue
                label = (item.get('displayName') or mid).strip()
                if mid not in seen:
                    seen[mid] = label
                for variant in item.get('variants') or []:
                    params = variant.get('params') or []
                    if not params:
                        continue
                    bits = ','.join(
                        f"{p.get('id')}={p.get('value')}"
                        for p in params if p.get('id') is not None
                    )
                    if not bits:
                        continue
                    vid = f"{mid}[{bits}]"
                    vlabel = variant.get('displayName') or vid
                    if vid not in seen:
                        seen[vid] = vlabel
        except Exception:
            pass
        return sorted(seen.items(), key=lambda x: (0 if x[0] == 'auto' else 1, x[1].lower()))

    def action_refresh_cursor_models(self):
        """Fetch live model list from Cursor GET /v1/models and cache for the selection."""
        self.ensure_one()
        import json
        import requests

        key = (self.dynamic_dashboard_ai_nexgen_cursor_api_key or '').strip()
        if not key:
            key = (self.env['ir.config_parameter'].sudo()
                   .get_param('dynamic_dashboard_ai_nexgen.cursor_api_key') or '').strip()
        if not key:
            raise UserError(_("Enter your Cursor API Key first, then refresh models."))

        try:
            res = requests.get(
                'https://api.cursor.com/v1/models',
                auth=(key, ''),
                headers={'Accept': 'application/json'},
                timeout=30,
            )
            if res.status_code == 401:
                raise UserError(_("Invalid Cursor API Key. Create one in Cursor Dashboard → Integrations."))
            res.raise_for_status()
            items = (res.json() or {}).get('items') or []
        except UserError:
            raise
        except Exception as e:
            raise UserError(_("Could not fetch Cursor models: %s") % e) from e

        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('dynamic_dashboard_ai_nexgen.cursor_models_extra', json.dumps(items))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cursor Models Updated'),
                'message': _('Loaded %s model(s) from Cursor. Re-open the Model dropdown to see them.')
                % len(items),
                'type': 'success',
                'sticky': False,
            },
        }
