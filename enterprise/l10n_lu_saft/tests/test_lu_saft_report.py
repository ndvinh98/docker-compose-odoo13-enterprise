# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.account_saft.tests.saft_test_common import SAFTReportTest
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class LuxembourgSAFTReportTest(SAFTReportTest):

    @classmethod
    def setUpClass(cls, chart_template_ref='l10n_lu.lu_2011_chart_1'):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.company_data['company'].write({
            'city': 'Garnich',
            'zip': 'L-8353',
            'company_registry': '123456',
            'phone': '+352 11 11 11 11',
            'country_id': cls.env.ref('base.lu').id,
        })

        cls.check_or_create_xsd_attachment('l10n_lu_saft')

    def test_saft_report_values(self):
        values = self.get_report_values()

        # Test exported header data
        self.assertHeaderData(values['header_data'], {
            'country': 'LU',
            'file_version': '2.01',
            'accounting_basis': 'Invoice Accounting'
        })
        # Test to see if there aren't any missing/additional master data
        self.execute_common_tests(values)
        self.assertEqual(len(values['uom_data']), 2,
            "Luxembourg SAF-T report should have 2 Unit of Measures in master data.")
        self.assertEqual(len(values['product_data']), 2,
            "Luxembourg SAF-T report should have 2 products in master data.")
        # Below seven accounts should have reflected with three invoices and one refund(untaxed amount: 1200€, tax: 204€ @ 17% rate for each invoice/refund)
        # and one bill(untaxed amount: 960€, tax: 163.2€ @ 17% rate) in current year and one invoice in previous year
        self.assertAccountBalance(values['accounts'], {
            self.company_data['company'].get_unaffected_earnings_account().id: {
                'opening_balance': {'debit': '0.00', 'credit': '1200.00'},
                'closing_balance': {'debit': '0.00', 'credit': '0.00'}
            },
            self.company_data['default_account_receivable'].id:    {
                'opening_balance': {'debit': '1404.00', 'credit': '0.00'},
                'closing_balance': {'debit': '4212.00', 'credit': '0.00'}
            },
            self.company_data['default_account_revenue'].id:       {
                'opening_balance': {'debit': '0.00', 'credit': '0.00'},
                'closing_balance': {'debit': '0.00', 'credit': '2400.00'}
            },
            self.company_data['default_account_tax_sale'].id:      {
                'opening_balance': {'debit': '0.00', 'credit': '204.00'},
                'closing_balance': {'debit': '0.00', 'credit': '612.00'}
            },
            self.company_data['default_account_payable'].id:       {
                'opening_balance': {'debit': '0.00', 'credit': '0.00'},
                'closing_balance': {'debit': '0.00', 'credit': '1123.20'}
            },
            self.company_data['default_account_expense'].id:       {
                'opening_balance': {'debit': '0.00', 'credit': '0.00'},
                'closing_balance': {'debit': '960.00', 'credit': '0.00'}
            },
            self.company_data['default_account_tax_purchase'].id:  {
                'opening_balance': {'debit': '0.00', 'credit': '0.00'},
                'closing_balance': {'debit': '163.20', 'credit': '0.00'}
            },
        })
        # Test number of exported sales invoices
        self.assertEqual(len(values['invoice_data']['invoices']), 4,
            "Luxembourg SAF-T report should have 4 Sales Invoices.")
        # Test exported invoices' total debit/credit amounts
        self.assertEqual(values['invoice_data']['invoice_total_debit'], '1200.00',
            "Wrong debit total for Sales Invoices.")
        self.assertEqual(values['invoice_data']['invoice_total_credit'], '3600.00',
            "Wrong credit total for Sales Invoices.")
        # Test to see XML is generated without any errors
        self.generate_saft_report()
