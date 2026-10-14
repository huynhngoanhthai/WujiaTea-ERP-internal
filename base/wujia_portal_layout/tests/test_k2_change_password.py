"""K2 — đổi mật khẩu: lỗi theo từng ô, hộp tổng lỗi, không render lại mật khẩu."""
from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import load_vi

FORMS = ("//form[contains(@class, 'wj-pc-acct-pw-form')]", "//form[contains(@class, 'wujia-maccount-form')]")


@tagged('post_install', '-at_install', 'wujia_layout_k2')
class TestK2ChangePassword(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_vi(cls.env)
        cls.env['res.users'].create({'name': 'K2 pw', 'login': 'k2.pw@wujia.test',
                                     'password': 'k2-pw-1234', 'lang': 'vi_VN'})

    def _post(self, old, new, confirm):
        self.authenticate('k2.pw@wujia.test', 'k2-pw-1234')
        doc = etree.HTML(self.url_open('/portal/change-password', timeout=30).text)
        token = doc.xpath("//input[@name='csrf_token']/@value")[0]
        res = self.url_open('/portal/change-password', data={
            'csrf_token': token, 'old-password': old, 'new-password': new, 'con-password': confirm,
        }, timeout=30)
        self.assertEqual(res.status_code, 200)
        return res.text, [etree.HTML(res.text).xpath(f)[0] for f in FORMS]

    @staticmethod
    def _shown(form):
        return sorted(p.get('id').split('-', 1)[1] for p in
                      form.xpath('.//p[contains(@class, "wj-field-error")][not(@hidden)]'))

    def test_each_rule_marks_its_field(self):
        cases = (
            (('', '', ''), ['con-password-err', 'new-password-err', 'old-password-err']),
            (('k2-pw-1234', 'abcdefgh1', 'zzzzzzzz9'), ['con-password-err']),
            (('k2-pw-1234', 'short', 'short'), ['new-password-err']),
            (('k2-pw-1234', 'k2-pw-1234', 'k2-pw-1234'), ['new-password-err']),
            (('wrong-old-pw', 'abcdefgh1', 'abcdefgh1'), ['old-password-err']),
        )
        for args, expected in cases:
            with self.subTest(args=args):
                _body, forms = self._post(*args)
                for form in forms:
                    self.assertEqual(self._shown(form), expected)
                    for err_id in form.xpath('.//p[contains(@class, "wj-field-error")][not(@hidden)]/@id'):
                        ctrl = form.xpath('.//input[@id="%s"]' % err_id[:-4])[0]
                        self.assertEqual(ctrl.get('aria-invalid'), 'true')
                        self.assertEqual(ctrl.get('aria-describedby'), err_id)

    def test_passwords_not_rendered_back(self):
        body, forms = self._post('wrong-old-pw', 'abcdefgh-secret', 'abcdefgh-secret')
        self.assertNotIn('wrong-old-pw', body)
        self.assertNotIn('abcdefgh-secret', body)
        for form in forms:
            self.assertIsNotNone(form.get('data-wj-validate'))
            self.assertEqual(len(form.xpath('.//*[@data-wj-error-summary]')), 1)
            self.assertTrue(form.xpath('.//input[@name="con-password"]/@data-wj-match'))

    def test_messages_follow_lang(self):
        _body, forms = self._post('wrong-old-pw', 'abcdefgh1', 'abcdefgh1')
        err = forms[0].xpath('.//p[@id="pc-old-password-err"]')[0]
        self.assertNotIn('Current password', ''.join(err.itertext()))
