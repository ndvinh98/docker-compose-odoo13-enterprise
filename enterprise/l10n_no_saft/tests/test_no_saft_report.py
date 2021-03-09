# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.account_saft.tests.saft_test_common import SAFTReportTest
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class NorwaySAFTReportTest(SAFTReportTest):

    @classmethod
    def setUpClass(cls, chart_template_ref='l10n_no.no_chart_template'):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.company_data['company'].write({
            'city': 'OSLO',
            'zip': 'N-0104',
            'company_registry': '123456',
            'phone': '+47 11 11 11 11',
            'country_id': cls.env.ref('base.no').id,
        })

        cls.check_or_create_xsd_attachment('l10n_no_saft')

    def test_saft_report_values(self):
        values = self.get_report_values()

        # Test exported header data
        self.assertHeaderData(values['header_data'], {
            'country': 'NO',
            'file_version': '1.10',
            'accounting_basis': 'A'
        })
        # Test to see if there aren't any missing/additional master data
        self.execute_common_tests(values)
        # Below seven accounts should have reflected with three invoices and one refund(untaxed amount: 1200kr, tax: 300kr @ 25% rate for each invoice/refund)
        # and one bill(untaxed amount: 960kr, tax: 240.00kr @ 25% rate) in current year and one invoice in previous year
        self.assertAccountBalance(values['accounts'], {
            self.company_data['company'].get_unaffected_earnings_account().id: {
                'opening_balance': {'debit': '0.00', 'credit': '1200.00'},
                'closing_balance': {'debit': '0.00', 'credit': '0.00'}
            },
            self.company_data['default_account_receivable'].id:    {
                'opening_balance': {'debit': '1500.00', 'credit': '0.00'},
                'closing_balance': {'debit': '4500.00', 'credit': '0.00'}
            },
            self.company_data['default_account_revenue'].id:       {
                'opening_balance': {'debit': '0.00', 'credit': '0.00'},
                'closing_balance': {'debit': '0.00', 'credit': '2400.00'}
            },
            self.company_data['default_account_tax_sale'].id:      {
                'opening_balance': {'debit': '0.00', 'credit': '300.00'},
                'closing_balance': {'debit': '0.00', 'credit': '900.00'}
            },
            self.company_data['default_account_payable'].id:       {
                'opening_balance': {'debit': '0.00', 'credit': '0.00'},
                'closing_balance': {'debit': '0.00', 'credit': '1200.00'}
            },
            self.company_data['default_account_expense'].id:       {
                'opening_balance': {'debit': '0.00', 'credit': '0.00'},
                'closing_balance': {'debit': '960.00', 'credit': '0.00'}
            },
            self.company_data['default_account_tax_purchase'].id:  {
                'opening_balance': {'debit': '0.00', 'credit': '0.00'},
                'closing_balance': {'debit': '240.00', 'credit': '0.00'}
            },
        })
        # Test to see XML is generated without any errors
        self.generate_saft_report()
