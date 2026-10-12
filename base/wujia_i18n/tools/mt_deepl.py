# -*- coding: utf-8 -*-
"""Dịch máy cho wujia_i18n (J-T5): client DeepL + bảo toàn định dạng câu trước/sau khi gửi.

Không import odoo ⇒ test thuần chạy được ngoài Odoo. Mọi HTTP đi qua `DeepLClient._request` (test patch đúng 1 chỗ).
Bảo toàn: placeholder (`%s`, `%(x)s`, `{x}`, `{{ x }}`, `${x}`), entity HTML, thuật ngữ "không dịch" ⇒ thay bằng thẻ
`<x i="n"/>` (DeepL giữ nguyên thẻ khi `tag_handling=xml`), khoảng trắng đầu/cuối tách riêng, chuỗi không phải
HTML (code, nhãn field) escape XML trước khi gửi.
"""

import re
from collections import Counter
from xml.sax.saxutils import escape, unescape

DEEPL_FREE_URL = 'https://api-free.deepl.com'
DEEPL_PRO_URL = 'https://api.deepl.com'
MAX_TEXTS = 50          # DeepL: tối đa 50 câu / request
MAX_CHARS = 30000       # giữ request < 128 KiB

# Mã Odoo ↔ mã đích DeepL khác quy tắc "2 chữ in hoa"
DEEPL_TARGET = {
    'zh_CN': 'ZH-HANS', 'zh_SG': 'ZH-HANS', 'zh_TW': 'ZH-HANT', 'zh_HK': 'ZH-HANT',
    'en_US': 'EN-US', 'en_GB': 'EN-GB', 'pt_BR': 'PT-BR', 'pt_PT': 'PT-PT', 'pt_AO': 'PT-PT',
    'nb_NO': 'NB',
}

PLACEHOLDER = re.compile(
    r'%\([^)\s]+\)[#0\- +]*\d*(?:\.\d+)?[sdifrxX]'   # %(name)s
    r'|%[#0\- +]*\d*(?:\.\d+)?[sdifrxX]'             # %s %d %.2f
    r'|%%'
    r'|\{\{.*?\}\}'                                  # {{ x }}
    r'|\$\{[^}]*\}'                                  # ${x}
    r'|\{[A-Za-z0-9_.\[\]]*\}'                       # {x} {0} {}
)
ENTITY = re.compile(r'&(?:[A-Za-z][A-Za-z0-9]*|#\d+|#x[0-9A-Fa-f]+);')
TOKEN = re.compile(r'<x i="(\d+)"\s*(?:/>|>\s*</x>)')
TAG = re.compile(r'</?[A-Za-z][\w:.-]*(?:\s[^<>]*?)?/?>')
SPACES = re.compile(r'^(\s*)(.*?)(\s*)$', re.S)
# Chữ riêng tiếng Việt ⇒ câu nguồn còn tiếng Việt (module Thái chưa Việt hoá source) ⇒ để DeepL tự nhận ngôn ngữ.
VN_CHARS = re.compile('[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]', re.I)
XML_UNESCAPE = {'&quot;': '"', '&apos;': "'"}


class MTError(Exception):
    """kind: auth (key sai) · quota (hết hạn mức) · rate (quá tải, thử lại sau) · other."""

    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


def deepl_target(lang):
    return DEEPL_TARGET.get(lang) or lang.split('_')[0].upper()


def deepl_glossary_lang(lang):
    return lang.split('_')[0].lower()


def is_vietnamese(text):
    return bool(VN_CHARS.search(text or ''))


def placeholders(text):
    return Counter(PLACEHOLDER.findall(text or ''))


def tags(text):
    return Counter(re.sub(r'\s+', ' ', t) for t in TAG.findall(text or ''))


def _term_pattern(terms):
    terms = sorted({t for t in terms if t}, key=len, reverse=True)
    if not terms:
        return None
    return re.compile(r'(?<!\w)(' + '|'.join(re.escape(t) for t in terms) + r')(?!\w)', re.I)


def protect(src, markup=False, keep_terms=(), replace_terms=None):
    """→ (text gửi DeepL, meta). `markup` = câu đã là HTML/QWeb (term view) ⇒ không escape.
    keep_terms: giữ nguyên (không dịch); replace_terms {thuật ngữ nguồn (lower): bản dịch} khi cặp ngôn ngữ không có glossary."""
    lead, body, trail = SPACES.match(src).groups()
    originals = []

    def token(original):
        originals.append(original)
        return f'<x i="{len(originals) - 1}"/>'

    replace_terms = {k.lower(): v for k, v in (replace_terms or {}).items()}
    special = [PLACEHOLDER.pattern]
    if markup:
        special.append(ENTITY.pattern)
    pattern = re.compile('|'.join(special))
    term_re = _term_pattern(list(keep_terms) + list(replace_terms))

    def protect_text(text):
        # Đoạn chữ thường (ngoài thẻ): thuật ngữ → token, phần còn lại escape nếu chưa phải HTML.
        if not term_re:
            return text if markup else escape(text)
        out, pos = [], 0
        for m in term_re.finditer(text):
            out.append(text[pos:m.start()] if markup else escape(text[pos:m.start()]))
            out.append(token(replace_terms.get(m.group(0).lower(), m.group(0))))
            pos = m.end()
        out.append(text[pos:] if markup else escape(text[pos:]))
        return ''.join(out)

    parts, pos = [], 0
    chunks = TAG.split(body) if markup else [body]
    found_tags = TAG.findall(body) if markup else []
    for i, chunk in enumerate(chunks):
        for m in pattern.finditer(chunk):
            parts.append(protect_text(chunk[pos:m.start()]))
            parts.append(token(m.group(0)))
            pos = m.end()
        parts.append(protect_text(chunk[pos:]))
        pos = 0
        if i < len(found_tags):
            parts.append(found_tags[i])
    return ''.join(parts), {'lead': lead, 'trail': trail, 'originals': originals, 'markup': markup}


def restore(text, meta):
    """Ngược lại `protect`: token → bản gốc, unescape phần chữ (nếu câu không phải HTML), gắn lại khoảng trắng."""
    out, pos = [], 0
    originals = meta['originals']
    for m in TOKEN.finditer(text):
        out.append(_unescape(text[pos:m.start()], meta['markup']))
        idx = int(m.group(1))
        if idx >= len(originals):
            raise ValueError(f'unknown token {m.group(0)}')
        out.append(originals[idx])
        pos = m.end()
    out.append(_unescape(text[pos:], meta['markup']))
    return meta['lead'] + ''.join(out).strip() + meta['trail']


def _unescape(text, markup):
    return text if markup else unescape(text, XML_UNESCAPE)


def check(src, out, markup=False):
    """Lý do loại bản dịch ('' = nhận). Placeholder và thẻ phải giữ đủ (thứ tự được đổi)."""
    if not out.strip():
        return 'empty translation'
    if placeholders(src) != placeholders(out):
        return 'placeholders changed: %s → %s' % (sorted(placeholders(src).elements()), sorted(placeholders(out).elements()))
    if markup and tags(src) != tags(out):
        return 'HTML tags changed'
    if TOKEN.search(out) or '<x ' in out:
        return 'protected token left in translation'
    return ''


def batches(items, size_of=len, max_texts=MAX_TEXTS, max_chars=MAX_CHARS):
    """Chia danh sách theo giới hạn request DeepL."""
    batch, chars = [], 0
    for item in items:
        n = size_of(item)
        if batch and (len(batch) >= max_texts or chars + n > max_chars):
            yield batch
            batch, chars = [], 0
        batch.append(item)
        chars += n
    if batch:
        yield batch


class DeepLClient:
    name = 'deepl'

    def __init__(self, api_key, timeout=30):
        if not api_key:
            raise MTError('auth', 'DeepL API key is not set')
        self.api_key = api_key.strip()
        self.timeout = timeout

    @property
    def base_url(self):
        # Key gói Free kết thúc bằng ":fx"
        return DEEPL_FREE_URL if self.api_key.endswith(':fx') else DEEPL_PRO_URL

    @property
    def plan(self):
        return 'free' if self.api_key.endswith(':fx') else 'pro'

    def _request(self, method, path, params=None, json=None):
        import requests  # nạp muộn: test thuần không cần requests
        try:
            resp = requests.request(method, self.base_url + path, params=params, json=json, timeout=self.timeout,
                                    headers={'Authorization': f'DeepL-Auth-Key {self.api_key}'})
        except requests.RequestException as e:
            raise MTError('rate', f'DeepL unreachable: {e}') from e
        if resp.status_code in (401, 403):
            raise MTError('auth', 'DeepL rejected the API key')
        if resp.status_code == 456:
            raise MTError('quota', 'DeepL character quota exceeded')
        if resp.status_code in (429, 500, 502, 503, 504, 529):
            raise MTError('rate', f'DeepL busy (HTTP {resp.status_code})')
        if resp.status_code == 404 and method == 'DELETE':
            return None
        if resp.status_code >= 400:
            raise MTError('other', f'DeepL HTTP {resp.status_code}: {resp.text[:300]}')
        return resp.json() if resp.content else None

    def target_languages(self):
        return {row['language'].upper() for row in self._request('GET', '/v2/languages', params={'type': 'target'})}

    def glossary_pairs(self):
        data = self._request('GET', '/v2/glossary-language-pairs')
        return {(p['source_lang'].lower(), p['target_lang'].lower()) for p in data['supported_languages']}

    def usage(self):
        data = self._request('GET', '/v2/usage')
        return {'count': data.get('character_count', 0), 'limit': data.get('character_limit', 0)}

    def translate(self, texts, target, source=None, glossary_id=None):
        body = {
            'text': list(texts), 'target_lang': target, 'tag_handling': 'xml', 'ignore_tags': ['x'],
            'preserve_formatting': True,
        }
        if source:
            body['source_lang'] = source
        if glossary_id:
            body['glossary_id'] = glossary_id
        data = self._request('POST', '/v2/translate', json=body)
        out = [row['text'] for row in data['translations']]
        if len(out) != len(texts):
            raise MTError('other', f'DeepL returned {len(out)} texts for {len(texts)}')
        return out

    def create_glossary(self, name, source, target, entries):
        tsv = '\n'.join(f'{k}\t{v}' for k, v in entries.items())
        data = self._request('POST', '/v2/glossaries', json={
            'name': name, 'source_lang': source, 'target_lang': target, 'entries': tsv, 'entries_format': 'tsv',
        })
        return data['glossary_id']

    def delete_glossary(self, glossary_id):
        self._request('DELETE', f'/v2/glossaries/{glossary_id}')


PROVIDERS = {'deepl': DeepLClient}
