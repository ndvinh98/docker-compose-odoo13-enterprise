# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests import tagged
from . import common
import logging

_logger = logging.getLogger(__name__)


@tagged('fe', 'ri')
class TestFe(common.TestEdi):

    @classmethod
    def setUpClass(cls):
        super(TestFe, cls).setUpClass()

        # Force user to be loggin in "Reponsable Inscripto" Argentinian Company
        context = dict(cls.env.context, allowed_company_ids=[cls.company_ri.id])
        cls.env = cls.env(context=context)

        cls.partner = cls.partner_ri
        cls.journal = cls._create_journal(cls, 'wsfe')

    def test_00_connection(self):
        self._test_connection()

    def test_01_consult_invoice(self):
        self._test_consult_invoice()

    def test_02_invoice_a_product(self):
        self._test_case('invoice_a', 'product')

    def test_03_invoice_a_service(self):
        self._test_case('invoice_a', 'service')

    def test_04_invoice_a_product_service(self):
        self._test_case('invoice_a', 'product_service')

    def test_05_invoice_b_product(self):
        self._test_case('invoice_b', 'product')

    def test_06_invoice_b_service(self):
        self._test_case('invoice_b', 'service')

    def test_07_invoice_b_product_service(self):
        self._test_case('invoice_b', 'product_service')

    def test_08_credit_note_a_product(self):
        invoice = self._test_case('invoice_a', 'product')
        self._test_case_credit_note('credit_note_a', invoice)

    def test_09_credit_note_a_service(self):
        invoice = self._test_case('invoice_a', 'service')
        self._test_case_credit_note('credit_note_a', invoice)

    def test_10_credit_note_a_product_service(self):
        invoice = self._test_case('invoice_a', 'product_service')
        self._test_case_credit_note('credit_note_a', invoice)

    def test_11_credit_note_b_product(self):
        invoice = self._test_case('invoice_b', 'product')
        self._test_case_credit_note('credit_note_b', invoice)

    def test_12_credit_note_b_service(self):
        invoice = self._test_case('invoice_b', 'service')
        self._test_case_credit_note('credit_note_b', invoice)

    def test_13_credit_note_b_product_service(self):
        invoice = self._test_case('invoice_b', 'product_service')
        self._test_case_credit_note('credit_note_b', invoice)

    def test_20_corner_cases(self):
        cases = {'demo_invoice_1': '"Mono" partner of tipe Service and VAT 21',
                 'demo_invoice_2': '"Exento" partner with multiple VAT types 21, 27 and 10,5',
                 'demo_invoice_3': '"RI" partner with VAT 0 and 21',
                 'demo_invoice_4': '"RI" partner with VAT exempt and 21',
                 'demo_invoice_5': '"RI" partner with all type of taxes',
                 'demo_invoice_8': '"Consumidor Final"',
                 'demo_invoice_11': '"RI" partner with many lines in order to prove rounding error, with 4'
                 ' decimals of precision for the currency and 2 decimals for the product the error apperar',
                 'demo_invoice_12': '"RI" partner with many lines in order to test rounding error, it is required'
                 ' to use a 4 decimal precision in prodct in order to the error occur',
                 'demo_invoice_13': '"RI" partner with many lines in order to test zero amount'
                 ' invoices y rounding error. it is required to set the product decimal precision to 4 and change 260.59'
                 ' for 260.60 in order to reproduce the error',
                 'demo_invoice_17': '"RI" partner with 100%% of discount',
                 'demo_invoice_18': '"RI" partner with 100%% of discount and with different VAT aliquots'}
        self._test_demo_cases(cases)

    def test_21_currency(self):
        self._prepare_multicurrency_values()
        self._test_demo_cases({'demo_invoice_10': '"Responsable Inscripto" in USD and VAT 21'})

    def test_22_iibb_sales_ars(self):
        iibb_tax = self._search_tax('percepcion_iibb')
        iibb_tax.active = True

        product_27 = self.env.ref('l10n_ar.product_product_telefonia_product_template')
        product_no_gravado = self.env.ref('l10n_ar.product_product_no_gravado')
        product_exento = self.env.ref('l10n_ar.product_product_exento')

        invoice = self._create_invoice(data={
            'lines': [{'product': product_27, 'price_unit': 100.0, 'quantity': 8},
                      {'product': product_no_gravado, 'price_unit': 750.0, 'quantity': 1},
                      {'product': product_exento, 'price_unit': 40.0, 'quantity': 20}]})

        # Add perceptions taxes
        invoice.invoice_line_ids.filtered(lambda x: x.product_id == product_27).tax_ids = [(4, iibb_tax.id)]
        invoice.invoice_line_ids.filtered(lambda x: x.product_id == product_exento).tax_ids = [(4, iibb_tax.id)]

        self.assertIn(iibb_tax.name, invoice.invoice_line_ids.mapped('tax_ids').mapped('name'))
        self._edi_validate_and_review(invoice)

    def test_23_iibb_sales_usd(self):
        iibb_tax = self._search_tax('percepcion_iibb')
        iibb_tax.active = True

        self._prepare_multicurrency_values()
        invoice = self._create_invoice({'currency': self.env.ref('base.USD')})
        invoice.invoice_line_ids.filtered(lambda x: x.tax_ids).tax_ids = [(4, iibb_tax.id)]
        self.assertIn(iibb_tax.name, invoice.invoice_line_ids.mapped('tax_ids').mapped('name'))
        self._edi_validate_and_review(invoice)


@tagged('vendor', 'ri', 'mono')
class TestVendorBill(common.TestEdi):

    @classmethod
    def setUpClass(cls):
        super(TestVendorBill, cls).setUpClass()

        # Force user to be loggin in "Reponsable Inscripto" Argentinian Company
        context = dict(cls.env.context, allowed_company_ids=[cls.company_ri.id])
        cls.env = cls.env(context=context)

        cls.partner = cls.partner_ri
        cls.journal = cls._create_journal(cls, 'wsfe')

    def test_01_vendor_bill_verify(self):
        # Create a customer invoice in "Responsable Inscripto" Company to "Monotributista" Company
        mono_company = self.env.ref('l10n_ar.company_mono')
        invoice = self._create_invoice({'partner': mono_company.partner_id})
        self._edi_validate_and_review(invoice)

        # Login in "Monotributista" Company
        context = dict(self.env.context, allowed_company_ids=[mono_company.id])
        self.env = self.env(context=context)

        # Create a vendor bill with the same values of "Responsable Inscripto"
        bill = self._create_invoice({
            'lines': [{'price_unit': invoice.amount_total}], 'document_number': invoice.l10n_latam_document_number},
            invoice_type='in_invoice')

        # Set CAE type and number to be able to verify in AFIP
        bill.l10n_ar_afip_auth_mode = 'CAE'
        bill.l10n_ar_afip_auth_code = invoice.l10n_ar_afip_auth_code

        # Verify manually vendor bill in AFIP from "Responsable Inscripto" in "Monotributista" Company
        self.assertFalse(bill.l10n_ar_afip_verification_result)
        bill.l10n_ar_verify_on_afip()
        if 'Error interno de aplicación:' in ' '.join(bill.message_ids.mapped('body')):
            _logger.warning('WSDC is not avaiable so we were not able to fully run the test')
            return

        self.assertTrue(bill.l10n_ar_afip_verification_result)
        # Need to use a real CUIT to be able to verify vendor bills in AFIP, that is why we receive Rejected
        self.assertEqual(bill.l10n_ar_afip_verification_result, 'R', bill.message_ids[0].body)
