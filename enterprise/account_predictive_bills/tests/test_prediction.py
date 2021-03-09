# -*- encoding: utf-8 -*-

from odoo.addons.account.tests.account_test_savepoint import AccountTestInvoicingCommon
from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import Form


@tagged('post_install', '-at_install')
class TestBillsPrediction(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.test_partners = cls.env['res.partner'].create([{'name': 'test partner %s' % i} for i in range(7)])

        expense_type = cls.env.ref('account.data_account_type_expenses')
        cls.test_accounts = cls.env['account.account'].create({
            'code': 'test%s' % i,
            'name': name,
            'user_type_id': expense_type.id,
            'company_id': cls.company_data['company'].id,
        } for i, name in enumerate((
            "Test Maintenance and Repair",
            "Test Purchase of services, studies and preparatory work",
            "Test Various Contributions",
            "Test Rental Charges",
            "Test Purchase of commodity",
        )))

        cls.frozen_today = fields.Date.today()

    def _create_bill(self, vendor, line_name, expected_account, account_to_set=None):
        ''' Create a new vendor bill to test the prediction.
        :param vendor:              The vendor to set on the invoice.
        :param line_name:           The name of the invoice line that will be used to predict.
        :param expected_account:    The expected predicted account.
        :param account_to_set:      The optional account to set as a correction of the predicted account.
        :return:                    The newly created vendor bill.
        '''
        invoice_form = Form(self.env['account.move'].with_context(default_type='in_invoice'))
        invoice_form.partner_id = vendor
        invoice_form.invoice_date = self.frozen_today
        with invoice_form.invoice_line_ids.new() as invoice_line_form:
            # Set the default account to avoid "account_id is a required field" in case of bad configuration.
            invoice_line_form.account_id = self.company_data['default_journal_purchase'].default_credit_account_id

            invoice_line_form.quantity = 1.0
            invoice_line_form.price_unit = 42.0
            invoice_line_form.name = line_name
        invoice = invoice_form.save()
        invoice_line = invoice.invoice_line_ids

        self.assertEqual(
            invoice_line.account_id,
            expected_account,
            "Account '%s' should have been predicted instead of '%s'" % (
                expected_account.display_name,
                invoice_line.account_id.display_name,
            ),
        )

        if account_to_set:
            invoice_line.account_id = account_to_set

        invoice.post()
        return invoice

    def test_account_prediction_flow(self):
        default_account = self.company_data['default_journal_purchase'].default_debit_account_id
        self._create_bill(self.test_partners[0], "Maintenance and repair", self.test_accounts[0])
        self._create_bill(self.test_partners[5], "Subsidies obtained", default_account, account_to_set=self.test_accounts[1])
        self._create_bill(self.test_partners[6], "Prepare subsidies file", self.test_accounts[1])
        self._create_bill(self.test_partners[1], "Contributions January", self.test_accounts[2])
        self._create_bill(self.test_partners[2], "Coca-cola", default_account, account_to_set=self.test_accounts[4])
        self._create_bill(self.test_partners[1], "Contribution February", self.test_accounts[2])
        self._create_bill(self.test_partners[3], "Electricity Bruxelles", default_account, account_to_set=self.test_accounts[3])
        self._create_bill(self.test_partners[3], "Electricity Grand-Rosière", self.test_accounts[3])
        self._create_bill(self.test_partners[2], "Purchase of coca-cola", self.test_accounts[4])
        self._create_bill(self.test_partners[4], "Crate of coca-cola", self.test_accounts[4])
        self._create_bill(self.test_partners[1], "March", self.test_accounts[2])

    def test_account_prediction_with_product(self):
        product = self.env['product.product'].create({
            'name': 'product_a',
            'lst_price': 1000.0,
            'standard_price': 800.0,
            'property_account_income_id': self.company_data['default_account_revenue'].id,
            'property_account_expense_id': self.company_data['default_account_expense'].id,
        })

        invoice_form = Form(self.env['account.move'].with_context(default_type='in_invoice'))
        invoice_form.partner_id = self.test_partners[0]
        invoice_form.invoice_date = self.frozen_today
        with invoice_form.invoice_line_ids.new() as invoice_line_form:
            invoice_line_form.product_id = product
            invoice_line_form.name = "Maintenance and repair"
        invoice = invoice_form.save()

        self.assertRecordValues(invoice.invoice_line_ids, [{
            'name': "Maintenance and repair",
            'product_id': product.id,
            'account_id': self.company_data['default_account_expense'].id,
        }])
