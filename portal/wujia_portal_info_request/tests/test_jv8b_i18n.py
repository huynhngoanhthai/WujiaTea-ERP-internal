"""J-V8b — câu gốc màn Yêu cầu cập nhật thông tin là tiếng Anh; user vi_VN phải thấy y chữ trước phiên.

Bảng VN chép nguyên từ source TRƯỚC J-V8b (HEAD dbd4335b). Chạy: `--test-tags wujia_jv8b`.
"""
import re

from odoo import http
from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase

from odoo.addons.wujia_info_request.models.wujia_info_update_request import REQUEST_TYPE
from odoo.addons.wujia_portal_base.tests.common import legacy_vn_badge
from odoo.addons.wujia_portal_info_request.controllers import portal as ctrl

from .common import load_vi

TYPE_VI = {
    'address': 'Địa chỉ', 'phone': 'Số điện thoại', 'email': 'Email', 'owner_name': 'Tên chủ cửa hàng',
    'bank_info': 'Thông tin ngân hàng', 'representative': 'Người đại diện', 'other': 'Khác',
}
STATE_VI = {
    'draft': 'Nháp', 'submitted': 'Đã gửi', 'reviewing': 'Đang xem', 'approved': 'Đã duyệt', 'rejected': 'Từ chối',
}
ERR_VI = {
    "Could not submit the request. Please check the information and try again.":
        'Không thể gửi yêu cầu. Vui lòng kiểm tra lại thông tin và thử lại.',
    "Invalid store.": 'Cửa hàng không hợp lệ.',
    "You cannot access this store.": 'Cửa hàng không truy cập được.',
    "Invalid information type.": 'Loại thông tin không hợp lệ.',
    "Please enter the new value.": 'Vui lòng nhập giá trị mới.',
    "Enter the field name when choosing 'Other'.": "Khi chọn 'Khác' phải nhập tên field.",
    "You do not have permission to view this store's information update requests.":
        'Bạn không có quyền xem yêu cầu cập nhật thông tin của cửa hàng.',
}
VIEWS = (
    'wujia_portal_info_request.portal_info_request_list',
    'wujia_portal_info_request.portal_info_request_form',
    'wujia_portal_info_request.portal_info_request_detail',
)
VN_CHARS = re.compile('[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]', re.I)


def _arch(view, env):
    return re.sub(r'<!--.*?-->', '', view.with_env(env).arch, flags=re.S)


def _text(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))


@tagged('post_install', '-at_install', 'wujia_jv8b')
class TestJv8bInfoRequestLabels(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env_vi = load_vi(cls.env)
        cls.env_en = cls.env(context=dict(cls.env.context, lang='en_US'))

    def test_type_labels_vi_unchanged(self):
        self.assertEqual(list(ctrl.REQUEST_TYPE_LABELS), [code for code, _label in REQUEST_TYPE])
        for code, old in TYPE_VI.items():
            with self.subTest(code=code):
                lazy = ctrl.REQUEST_TYPE_LABELS[code]
                self.assertEqual(self.env_vi._(lazy), old)
                self.assertFalse(VN_CHARS.search(lazy._source))

    def test_state_labels_and_badges_unchanged(self):
        self.assertEqual(set(ctrl.STATE_LABELS), set(STATE_VI))
        for state, old in STATE_VI.items():
            with self.subTest(state=state):
                lazy, css = ctrl.STATE_LABELS[state]
                self.assertEqual(self.env_vi._(lazy), old)
                # Màu badge trước phiên tính từ nhãn VN — phải trùng màu tính từ nhãn EN.
                self.assertEqual(css, legacy_vn_badge(old))
                self.assertFalse(VN_CHARS.search(lazy._source))

    def test_error_messages_vi_unchanged(self):
        for msg, old in ERR_VI.items():
            with self.subTest(msg=msg):
                self.assertEqual(self.env_vi._(msg), old)
                self.assertEqual(self.env_en._(msg), msg)

    def test_controller_source_has_no_vietnamese(self):
        src = open(ctrl.__file__, encoding='utf-8').read()
        code = re.sub(r'#.*', '', re.sub(r'"""(.|\n)*?"""', '', src))
        self.assertFalse(VN_CHARS.search(code), VN_CHARS.findall(code)[:5])

    def test_view_labels_in_arch(self):
        words = {
            'wujia_portal_info_request.portal_info_request_list': (
                'Tất cả trạng thái', 'Tất cả loại thông tin', 'kết quả'),
            'wujia_portal_info_request.portal_info_request_form': (
                '— Chọn cửa hàng —', '— Chọn loại —', 'Giá trị mới <span class="text-danger">*</span>'),
            'wujia_portal_info_request.portal_info_request_detail': (
                'Huỷ yêu cầu này?', 'Huỷ yêu cầu', 'Yêu cầu đã được huỷ.'),
        }
        for xmlid in VIEWS:
            view = self.env.ref(xmlid)
            arch_vi, arch_en = _arch(view, self.env_vi), _arch(view, self.env_en)
            with self.subTest(xmlid=xmlid):
                for w in words[xmlid]:
                    self.assertIn(w, arch_vi)
                self.assertFalse(VN_CHARS.search(arch_en), VN_CHARS.findall(arch_en)[:5])


@tagged('post_install', '-at_install', 'wujia_jv8b')
class TestJv8bInfoRequestPages(HttpCase):
    LOGIN = 'jv8b_inf'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_vi(cls.env)
        env = cls.env
        cls.franchise = env['wujia.franchise.management'].create({
            'code': 'JV8I', 'name': 'JV8B info store', 'franchise_end_date': '2030-01-01',
            'partner_id': env['res.partner'].create({'name': 'JV8B info partner'}).id})
        cls.user = env['res.users'].create({
            'name': cls.LOGIN, 'login': cls.LOGIN, 'password': cls.LOGIN, 'lang': 'vi_VN',
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
        env['wujia.franchise.member'].create({
            'user_id': cls.user.id, 'franchise_id': cls.franchise.id, 'role': 'owner'})
        cls.rec = env['wujia.info.update.request'].create({
            'franchise_id': cls.franchise.id, 'request_type': 'bank_info',
            'new_value': 'JV8B v', 'created_by_user_id': cls.user.id})

    def _login(self, lang):
        self.user.lang = lang
        self.env.flush_all()
        # Ngôn ngữ phiên chốt lúc đăng nhập ⇒ đổi lang thì đăng nhập lại.
        self.authenticate(self.LOGIN, self.LOGIN)

    def _get(self, url, lang):
        self._login(lang)
        res = self.url_open(url, timeout=30)
        self.assertEqual(res.status_code, 200, url)
        return res.text

    def test_list_singular_state_and_type(self):
        en = _text(self._get('/portal/info-request', 'en_US'))
        self.assertIn('1 result ', en)
        self.assertNotIn('1 results', en)
        self.assertIn('Bank information', en)
        self.assertIn('Draft', en)
        vi = _text(self._get('/portal/info-request', 'vi_VN'))
        self.assertIn('1 kết quả', vi)
        self.assertIn('Thông tin ngân hàng', vi)
        self.assertIn('Nháp', vi)
        self.assertNotIn('Bank information', vi)

    def test_detail_confirm_follows_lang(self):
        url = '/portal/info-request/%d' % self.rec.id
        attr_en = 'data-wj-msg-confirm="Withdraw this request?"'
        attr_vi = 'data-wj-msg-confirm="Huỷ yêu cầu này?"'
        self.assertIn(attr_en, self._get(url, 'en_US'))
        self.assertIn(attr_vi, self._get(url, 'vi_VN'))

    def test_validation_error_follows_lang(self):
        data = {'franchise_id': self.franchise.id, 'request_type': 'zzz', 'new_value': 'x', 'action': 'draft'}
        for lang, expected in (('en_US', 'Invalid information type.'), ('vi_VN', 'Loại thông tin không hợp lệ.')):
            with self.subTest(lang=lang):
                self._login(lang)
                body = self.url_open('/portal/info-request/new', timeout=30,
                                     data=dict(data, csrf_token=http.Request.csrf_token(self))).text
                self.assertIn(expected, body)
