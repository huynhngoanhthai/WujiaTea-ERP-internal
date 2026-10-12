"""WJ-ORD-031 — sản phẩm công khai Portal bắt buộc có danh mục Portal hợp lệ."""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged

from .common import load_vi


@tagged('post_install', '-at_install', 'wujia_sale')
class TestPortalCategory(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = load_vi(cls.env)
        cls.categ = cls.env['wujia.product.category'].create({'name': 'I1 Trà'})
        cls.Product = cls.env['product.product']

    def _product(self, **vals):
        return self.Product.create({'name': 'I1 SP', 'type': 'consu', 'min_qty': 1, **vals})

    def test_publish_without_category_blocked(self):
        product = self._product()
        for lang, text in (('vi_VN', "phải có danh mục Portal trước khi được public"),
                           ('en_US', "must have a portal category before it can be published")):
            with self.subTest(lang=lang), self.assertRaises(ValidationError) as cm:
                product.with_context(lang=lang).write({'is_public_portal': True})
            self.assertIn(text, str(cm.exception))
        with self.assertRaises(ValidationError):
            self._product(is_public_portal=True)

    def test_clear_category_of_published_blocked(self):
        product = self._product(is_public_portal=True, public_categ_id=self.categ.id)
        with self.assertRaises(ValidationError):
            product.public_categ_id = False

    def test_legacy_product_without_category_still_editable(self):
        product = self._product()
        self.env.cr.execute('UPDATE product_product SET is_public_portal = TRUE WHERE id = %s',
                            (product.id,))
        product.invalidate_recordset()
        product.write({'min_qty': 2, 'wujia_packaging': '1kg'})
        self.assertEqual(product.min_qty, 2)
        self.assertFalse(product._portal_is_orderable())
        product.write({'is_public_portal': False})

    def test_orderable_domain_and_record_agree(self):
        archived = self.env['wujia.product.category'].create({'name': 'I1 Cũ'})
        ok = self._product(name='I1 OK', is_public_portal=True, public_categ_id=self.categ.id)
        in_archived = self._product(name='I1 Archived', is_public_portal=True,
                                    public_categ_id=archived.id)
        hidden = self._product(name='I1 Hidden', public_categ_id=self.categ.id)
        archived.active = False
        mine = ok | in_archived | hidden
        found = self.Product.search(self.Product._portal_orderable_domain() + [('id', 'in', mine.ids)])
        self.assertEqual(found, ok)
        self.assertEqual([p._portal_is_orderable() for p in mine], [True, False, False])
        archived.active = True
        self.assertTrue(in_archived._portal_is_orderable())
