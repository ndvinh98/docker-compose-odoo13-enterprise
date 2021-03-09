# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.account.tests.account_test_savepoint import AccountTestInvoicingCommon
from odoo.addons.account_reports.tests.common import _init_options
from odoo.tests import tagged
from odoo.tests.common import Form
from odoo import fields, release
from odoo.tools import date_utils


@tagged('post_install', '-at_install')
class SAFTReportTest(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        # prepare data required to create invoices
        cls.partner_a = cls.env['res.partner'].create({
            'name': 'SAFT Partner A',
            'city': 'Garnich',
            'zip': 'L-8353',
            'country_id': cls.env.ref('base.lu').id,
            'phone': '+352 24 11 11 11',
        })
        cls.partner_b = cls.env['res.partner'].create({
            'name': 'SAFT Partner B',
            'city': 'Garnich',
            'zip': 'L-8353',
            'country_id': cls.env.ref('base.lu').id,
            'phone': '+352 24 11 11 12',
        })
        cls.product_a = cls.env['product.product'].create({
            'name': 'SAFT A',
            'default_code': 'PA',
            'lst_price': 1000.0,
            'standard_price': 800.0,
            'property_account_income_id': cls.company_data['default_account_revenue'].id,
            'property_account_expense_id': cls.company_data['default_account_expense'].id,
        })
        cls.product_b = cls.env['product.product'].create({
            'name': 'SAFT B',
            'default_code': 'PB',
            'uom_id': cls.env.ref('uom.product_uom_dozen').id,
            'lst_price': 200.0,
            'standard_price': 160.0,
            'property_account_income_id': cls.company_data['default_account_revenue'].id,
            'property_account_expense_id': cls.company_data['default_account_expense'].id,
        })

        # Create three invoices, one refund and one bill in 2019
        partner_a_invoice1 = cls.init_invoice('out_invoice')
        partner_a_invoice2 = cls.init_invoice('out_invoice')
        partner_a_invoice3 = cls.init_invoice('out_invoice')
        partner_a_refund = cls.init_invoice('out_refund')

        partner_b_bill = cls.init_invoice('in_invoice', partner=cls.partner_b)

        # Create one invoice for partner B in 2018
        partner_b_invoice1 = cls.init_invoice('out_invoice', partner=cls.partner_b, invoice_date=fields.Date.from_string('2018-01-01'))

        # init_invoice has hardcoded 2019 year's date, we are resetting it to current year's one.
        (partner_a_invoice1 + partner_a_invoice2 + partner_a_invoice3 + partner_b_invoice1 + partner_a_refund + partner_b_bill).post()

        cls.report_options = cls.get_report_options()

        cls.country_name = cls.company_data['company'].country_id.name

    @classmethod
    def check_or_create_xsd_attachment(cls, module_name):
        # Check for cached XSD file in attachment
        xsd_file = cls.env['account.general.ledger']._get_xsd_file()
        attachment = cls.env['ir.attachment'].search([
            ('name', '=', 'xsd_cached_{0}'.format(xsd_file.replace('.', '_')))
        ])
        if not attachment:
            # Below might take some time to download XSD file
            cls.env.ref('{}.ir_cron_load_xsd_file'.format(module_name)).method_direct_trigger()
        return True

    @classmethod
    def get_report_options(cls):
        # Generate `options` to feed to SAFT report
        return _init_options(cls.env['account.general.ledger'], fields.Date.from_string('2019-01-01'), fields.Date.from_string('2019-12-31'))

    def generate_saft_report(self):
        return self.env['account.general.ledger'].get_xml(self.report_options)

    def get_report_values(self):
        with self.mocked_today('2019-01-01'):
            return self.env['account.general.ledger']._prepare_saft_report_data(self.report_options)

    def assertHeaderData(self, header_values, expected_values):
        expected_values.update({
            'date_created': fields.Date.from_string('2019-01-01'),
            'software_version': release.version,
            'company_currency': self.company_data['company'].currency_id.name,
            'date_from': self.report_options['date']['date_from'],
            'date_to': self.report_options['date']['date_to'],
        })
        # Test exported accounts' closing balance
        self.assertEqual(header_values, expected_values,
            "Header for {} SAF-T report is not correct.".format(self.country_name))

    def assertAccountBalance(self, values, expected_values):
        # Test exported accounts' closing balance
        for account_vals in values:
            expected = expected_values[account_vals['id']]
            self.assertEqual(account_vals['opening_balance'], expected['opening_balance'],
                "Wrong opening balance for account(s) of {} SAF-T report.".format(self.country_name))
            self.assertEqual(account_vals['closing_balance'], expected['closing_balance'],
                "Wrong closing balance for account(s) of {} SAF-T report.".format(self.country_name))

    def execute_common_tests(self, values):
        self.assertEqual(self.company_data['company'].country_id.code, values['country_code'],
            "Selected company is not one from {}! SAF-T report can't be generated.".format(self.country_name))

        # Test exported customers/suppliers
        self.assertEqual(len(values['customers']), 1,
            "{} SAF-T report should have 1 customer in master data.".format(self.country_name))
        self.assertEqual(values['customers'][0]['id'], self.partner_a.id,
            "{} SAF-T report should have {} as customer in master data.".format(self.country_name, self.partner_a.name))
        self.assertEqual(len(values['suppliers']), 1,
            "{} SAF-T report should have 1 supplier in master data.".format(self.country_name))
        self.assertEqual(values['suppliers'][0]['id'], self.partner_b.id,
            "{} SAF-T report should have {} as supplier in master data.".format(self.country_name, self.partner_b.name))

        # Test exported taxes
        taxes = self.tax_sale_a + self.tax_sale_b + self.tax_purchase_a + self.tax_purchase_b
        taxes_values = {vals['id']: vals for vals in taxes.read(['name', 'amount_type', 'amount'])}

        # Check the report.
        report_taxes = list(values['taxes'].values())
        for report_vals in report_taxes:
            self.assertDictEqual(report_vals, taxes_values.get(report_vals['id']))
