# Part of Odoo. See LICENSE file for full copyright and licensing details.
from . import common


class TestManual(common.TestEdi):


    @classmethod
    def setUpClass(cls):
        super(TestManual, cls).setUpClass()

        # Force user to be loggin in "Reponsable Inscripto" Argentinian Company
        context = dict(cls.env.context, allowed_company_ids=[cls.company_ri.id])
        cls.env = cls.env(context=context)

        cls.journal = cls._create_journal(cls, 'preprinted')
        cls.partner = cls.partner_ri

    def test_01_create_invoice(self):
        """ Create and validate an invoice for a Responsable Inscripto

        * Proper set the current user company
        * Properly set the tax amount of the product / partner
        * Proper fiscal position (this case not fiscal position is selected)
        """
        invoice = self._create_invoice()
        self.assertEqual(invoice.company_id, self.company_ri, 'created with wrong company')
        self.assertEqual(invoice.amount_tax, 21, 'invoice taxes are not properly set')
        self.assertEqual(invoice.amount_total, 121.0, 'invoice taxes has not been applied to the total')
        self.assertEqual(invoice.l10n_latam_document_type_id, self.document_type['invoice_a'], 'selected document type should be Factura A')
        invoice.post()
        self.assertEqual(invoice.state, 'posted', 'invoice has not been validate in Odoo')
        self.assertEqual(invoice.name, 'FA-A %05d-00000001' % self.journal.l10n_ar_afip_pos_number, 'Invoice number is wrong')

    def test_02_fiscal_position(self):
        # ADHOC SA > IVA Responsable Inscripto > Without Fiscal Positon
        invoice = self._create_invoice({'partner': self.partner_ri})
        self.assertFalse(invoice.fiscal_position_id, 'Fiscal position should be set to empty')

        # Consumidor Final > IVA Responsable Inscripto > Without Fiscal Positon
        invoice = self._create_invoice({'partner': self.partner_cf})
        self.assertFalse(invoice.fiscal_position_id, 'Fiscal position should be set to empty')

        # Cerro Castor > IVA Liberado – Ley Nº 19.640 > Compras / Ventas Zona Franca > IVA Exento
        invoice = self._create_invoice({'partner': self.partner_fz})
        self.assertEqual(invoice.fiscal_position_id, self._search_fp('Compras / Ventas Zona Franca'))

        # Expresso > Cliente / Proveedor del Exterior >  > IVA Exento
        invoice = self._create_invoice({'partner': self.partner_ex})
        self.assertEqual(invoice.fiscal_position_id, self._search_fp('Compras / Ventas al exterior'))

    def test_03_afip_concept(self):
        # Products / Definitive export of goods
        invoice = self._create_invoice()
        self.assertEqual(invoice.l10n_ar_afip_concept, '1', 'The correct AFIP Concept should be: Concept should be: Products / Definitive export of goods')

        # Services
        invoice = self._create_invoice({'lines': [{'product': self.service_iva_27}]})
        self.assertEqual(invoice.l10n_ar_afip_concept, '2', 'The correct AFIP Concept should be: Services')

        # Product and services
        invoice = self._create_invoice({'lines': [{'product': self.service_iva_27}, {'product': self.product_iva_21}]})
        self.assertEqual(invoice.l10n_ar_afip_concept, '3', 'The correct AFIP Concept should be: Products and Services')
