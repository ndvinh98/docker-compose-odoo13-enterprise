# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.account.tests.account_test_savepoint import AccountTestInvoicingCommon
from odoo.addons.account_reports.tests.common import _init_options
from odoo.tests import tagged
from odoo.tests.common import Form
from odoo import fields
from odoo.tools import date_utils
from dateutil.relativedelta import relativedelta


@tagged('post_install', '-at_install')
class LuxembourgElectronicReportTest(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref='l10n_lu.lu_2011_chart_1'):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.env.company.write({
            'ecdf_prefix': '1234AB',
            'country_id': cls.env.ref('base.lu').id
        })

        # ==== Partner ====
        cls.partner_a = cls.env['res.partner'].create({
            'name': 'Partner A'
        })
        # ==== Products ====
        cls.product_a = cls.env['product.product'].create({
            'name': 'product_a',
            'lst_price': 1000.0,
            'standard_price': 800.0,
        })
        cls.product_b = cls.env['product.product'].create({
            'name': 'product_b',
            'lst_price': 200.0,
            'standard_price': 160.0,
        })

    def get_report_options(self, report):
        year_df, year_dt = date_utils.get_fiscal_year(fields.Date.today())
        report.filter_date = {'mode': 'range', 'filter': 'this_year'}
        # Generate `options` to feed to financial report
        options = _init_options(report, year_df, year_dt)
        # Below method generates `filename` in specific format required for XML report
        report.get_report_filename(options)
        return options

    def get_report_values(self, report, options):
        report_values = report._get_lu_electronic_report_values(options)
        values = []
        # Here, we filtered out zero amount values so that `expected_*_report_values` can have lesser items.
        for code, value in report_values['forms'][0]['field_values'].items():
            if value['field_type'] == 'number' and value['value'] != '0,00':
                values.append((code, value['value']))
        return values

    def test_electronic_reports(self):
        # Create one invoice and one bill in current year
        date_today = fields.Date.today()
        lu_invoice = self.init_invoice('out_invoice')
        lu_bill = self.init_invoice('in_invoice')
        # init_invoice() has hardcoded 2019 year's date, we need to reset invoices' dates to current
        # year's date as BS/PL financial reports needs to have previous year's balance in exported file.
        (lu_invoice | lu_bill).write({'invoice_date': date_today, 'date': date_today})
        lu_invoice.post()
        lu_bill.post()

        # Below tuples are having code and it's amount respectively which would go to exported Balance Sheet report
        # if exported with the same invoice and bill as created above
        expected_bs_report_values = [
            ('151', '1567,20'), ('163', '1567,20'), ('165', '1404,00'), ('167', '1404,00'), ('183', '163,20'), ('185', '163,20'),
            ('201', '1567,20'), ('301', '240,00'), ('321', '240,00'), ('435', '1327,20'), ('367', '1123,20'), ('369', '1123,20'),
            ('451', '204,00'), ('393', '204,00'), ('405', '1567,20')
        ]
        bs_report = self.env.ref('l10n_lu_reports.account_financial_report_l10n_lu_bs')
        bs_report_options = self.get_report_options(bs_report)
        bs_report_field_values = self.get_report_values(bs_report, bs_report_options)
        self.assertEqual(expected_bs_report_values, bs_report_field_values, "Wrong values of Luxembourg Balance Sheet report.")
        # test to see if there is any error in XML generation
        bs_report.get_xml(bs_report_options)

        expected_pl_report_values = [('701', '1200,00'), ('671', '-960,00'), ('601', '-960,00'), ('667', '240,00'), ('669', '240,00')]
        pl_report = self.env.ref('l10n_lu_reports.account_financial_report_l10n_lu_pl')
        pl_report_options = self.get_report_options(pl_report)
        pl_report_field_values = self.get_report_values(pl_report, pl_report_options)
        self.assertEqual(expected_pl_report_values, pl_report_field_values, "Wrong values of Luxembourg Profit & Loss report.")
        pl_report.get_xml(pl_report_options)

        expected_tax_report_values = [('012', '1200,00'), ('454', '1200,00'), ('472', '1200,00'), ('022', '1200,00'), ('037', '1200,00'), ('701', '1200,00'), ('046', '204,00'), ('702', '204,00'), ('076', '204,00'), ('093', '163,20'), ('458', '163,20'), ('102', '163,20'), ('103', '204,00'), ('104', '163,20'), ('105', '40,80')]
        TaxReport = self.env['account.generic.tax.report']
        tax_report_options = self.get_report_options(TaxReport)
        tax_report_field_values = self.get_report_values(TaxReport, tax_report_options)
        self.assertEqual(expected_tax_report_values, tax_report_field_values, "Wrong values of Luxembourg Tax report.")
        TaxReport.get_xml(tax_report_options)

    def test_intrastat_report(self):
        l_tax = self.env['account.tax'].search([('company_id', '=', self.company_data['company'].id), ('name', '=', '0-IC-S-G'), '|', ("active", "=", True), ("active", "=", False)])
        t_tax = self.env['account.tax'].search([('company_id', '=', self.company_data['company'].id), ('name', '=', '0-ICT-S-G'), '|', ("active", "=", True), ("active", "=", False)])
        s_tax = self.env['account.tax'].search([('company_id', '=', self.company_data['company'].id), ('name', '=', '0-IC-S-S'), '|', ("active", "=", True), ("active", "=", False)])
        l_tax.active = t_tax.active = s_tax.active = True

        product_1 = self.env['product.product'].create({'name': 'product_1', 'lst_price': 300.0})
        product_2 = self.env['product.product'].create({'name': 'product_2', 'lst_price': 500.0})
        product_3 = self.env['product.product'].create({'name': 'product_3', 'lst_price': 700.0})
        partner_be = self.env['res.partner'].create({
            'name': 'Partner BE',
            'country_id': self.env.ref('base.be').id,
            'vat': 'BE0477472701',
        })
        partner_fr = self.env['res.partner'].create({
            'name': 'Partner FR',
            'country_id': self.env.ref('base.fr').id,
            'vat': 'FR00000000190',
        })
        partner_lu = self.env['res.partner'].create({
            'name': 'Partner LU',
            'country_id': self.env.ref('base.lu').id,
            'vat': 'LU12345613',
        })
        partner_us = self.env['res.partner'].create({
            'name': 'Partner US',
            'country_id': self.env.ref('base.us').id
        })
        date_today = fields.Date.today()

        invoices = [
            {'partner': partner_be, 'product': product_1, 'tax': l_tax},
            {'partner': partner_be, 'product': product_1, 'tax': l_tax},
            {'partner': partner_be, 'product': product_2, 'tax': t_tax},
            {'partner': partner_be, 'product': product_3, 'tax': s_tax},
            {'partner': partner_fr, 'product': product_2, 'tax': t_tax},
            {'partner': partner_fr, 'product': product_3, 'tax': s_tax},
            {'partner': partner_lu, 'product': product_3, 'tax': s_tax},
            {'partner': partner_us, 'product': product_3, 'tax': s_tax},
        ]

        for inv in invoices:
            move_form = Form(self.env['account.move'].with_context(default_type='out_invoice'))
            move_form.invoice_date = date_today
            move_form.partner_id = inv['partner']
            with move_form.invoice_line_ids.new() as line_form:
                line_form.product_id = inv['product']
            move = move_form.save()
            move.line_ids[0].tax_ids = [inv['tax'].id]
            move.post()

        report = self.env['l10n.lu.report.partner.vat.intra']
        report = report.with_context(
            date_from=date_today.strftime('%Y-%m-01'),
            date_to=(date_today + relativedelta(day=31)).strftime('%Y-%m-%d')
        )
        options = report._get_options(None)

        options['intrastat_code'] = [
            {'id': '0-IC-S-G', 'name': 'L', 'selected': True},
            {'id': '0-ICT-S-G', 'name': 'T', 'selected': True},
            {'id': '0-IC-S-S', 'name': 'S', 'selected': True}
        ]
        lines = report._get_lines(options)
        result = []
        for line in lines:
            result.append([line['name']] + [col['name'] for col in line['columns']])

        expected = [
            ['Partner BE', 'BE', '0477472701', 'L', '600.00 €'],
            ['Partner BE', 'BE', '0477472701', 'T', '500.00 €'],
            ['Partner FR', 'FR', '00000000190', 'T', '500.00 €'],
            ['Partner BE', 'BE', '0477472701', 'S', '700.00 €'],
            ['Partner FR', 'FR', '00000000190', 'S', '700.00 €'],
            ['Partner LU', 'LU', '12345613', 'S', '700.00 €'],
            ['Partner US', '', '', 'S', '700.00 €']
        ]
        self.assertListEqual(expected, result, 'Wrong values for Luxembourg intrastat report.')
