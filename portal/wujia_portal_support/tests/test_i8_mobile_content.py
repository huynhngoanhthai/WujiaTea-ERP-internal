"""WJ-SUPPORT-002: chi tiết phiếu mobile có thẻ Nội dung yêu cầu (đầy đủ, như PC).

Chạy: `--test-tags wujia_support_i8`.
"""
from lxml import html as lhtml

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.wujia_portal_base.controllers.portal import ACTIVE_FRANCHISE_COOKIE
from odoo.addons.wujia_support.tests.test_support import SupportCommon

LONG_TOKEN = 'I8_' + 'X' * 180
DESCRIPTION = ('<p>I8 dòng một</p><p>I8 dòng hai<br>I8 dòng ba</p>'
               '<p>https://support.example.com/a/very/long/path/%s</p>' % LONG_TOKEN)


@tagged('post_install', '-at_install', 'wujia_support_i8')
class TestSupportMobileContent(SupportCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_support()
        cls.t_desc = cls._ticket(title='I8 có nội dung', description=DESCRIPTION)
        cls.t_empty = cls._ticket(title='I8 không nội dung', description=False)

    def _doc(self, ticket):
        self.authenticate('f10.owner', 'f10.owner')
        self.opener.cookies.set(ACTIVE_FRANCHISE_COOKIE, str(self.franchise.id))
        res = self.url_open('/portal/support/%d' % ticket.id, timeout=30, allow_redirects=False)
        self.assertEqual(res.status_code, 200)
        return lhtml.fromstring(res.text)

    @staticmethod
    def _mobile(doc):
        blocks = doc.xpath('//div[contains(@class, "wujia-mticket") and contains(@class, "d-lg-none")]')
        return blocks[0]

    @staticmethod
    def _pc(doc):
        return doc.xpath('//div[contains(@class, "content-wrapper") and contains(@class, "d-lg-block")]')[0]

    def test_mobile_shows_full_content(self):
        m = self._mobile(self._doc(self.t_desc))
        content = m.xpath('.//div[contains(@class, "wujia-mticket-content")]')
        self.assertEqual(len(content), 1)
        text = content[0].text_content()
        for part in ('I8 dòng một', 'I8 dòng hai', 'I8 dòng ba', LONG_TOKEN):
            self.assertIn(part, text)
        # đủ đoạn, không cắt/thu gọn
        self.assertEqual(len(content[0].xpath('.//p')), 3)
        self.assertIn('wj-sup-content', content[0].get('class'))

    def test_mobile_content_before_thread_and_reply(self):
        m = self._mobile(self._doc(self.t_desc))
        order = [el.get('class') for el in m.iter()
                 if el.get('class') and any(c in el.get('class').split() for c in (
                     'wujia-mticket-content', 'wujia-mticket-thread'))]
        self.assertEqual([c.split()[0] for c in order], ['wujia-mticket-content', 'wujia-mticket-thread'])

    def test_mobile_empty_description_dash(self):
        m = self._mobile(self._doc(self.t_empty))
        content = m.xpath('.//div[contains(@class, "wujia-mticket-content")]')
        self.assertEqual(content[0].text_content().strip(), '—')

    def test_pc_keeps_content(self):
        pc = self._pc(self._doc(self.t_desc))
        content = pc.xpath('.//div[contains(@class, "wj-sup-content")]')
        self.assertEqual(len(content), 1)
        self.assertIn(LONG_TOKEN, content[0].text_content())
        self.assertFalse(pc.xpath('.//div[contains(@class, "wujia-mticket-content")]'))
