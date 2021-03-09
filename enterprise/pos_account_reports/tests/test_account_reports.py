# -*- coding: utf-8 -*-

from odoo import fields
from odoo.tests import tagged
from odoo.tools.misc import formatLang

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon

import datetime
from contextlib import contextmanager
from unittest.mock import patch


@tagged('post_install', '-at_install')
class POSTestTaxReport(TestAccountReportsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        test_country = cls.env['res.country'].create({
            'name': "Hassaleh",
            'code': 'HH',
        })

        cls.company_parent.country_id = test_country

        # Create some tax report
        cls.pos_tax_report_line_invoice_base = cls._create_tax_report_line(cls, name="Invoice Base", country=test_country, tag_name='pos_invoice_base', sequence=0)
        cls.pos_tax_report_line_invoice_tax = cls._create_tax_report_line(cls, name="Invoice Tax", country=test_country, tag_name='pos_invoice_tax', sequence=1)
        cls.pos_tax_report_line_refund_base = cls._create_tax_report_line(cls, name="Refund Base", country=test_country, tag_name='pos_refund_base', sequence=2)
        cls.pos_tax_report_line_refund_tax = cls._create_tax_report_line(cls, name="Refund Tax", country=test_country, tag_name='pos_refund_tax', sequence=3)

        # Create a tax using the created report
        tax_template = cls.env['account.tax.template'].create({
            'name': 'Impôt recto',
            'amount': '10',
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'chart_template_id': cls.company_parent.chart_template_id.id,
            'invoice_repartition_line_ids': [
                (0,0, {
                    'factor_percent': 100,
                    'repartition_type': 'base',
                    'plus_report_line_ids': [cls.pos_tax_report_line_invoice_base.id],
                }),

                (0,0, {
                    'factor_percent': 100,
                    'repartition_type': 'tax',
                    'plus_report_line_ids': [cls.pos_tax_report_line_invoice_tax.id],
                }),
            ],
            'refund_repartition_line_ids': [
                (0,0, {
                    'factor_percent': 100,
                    'repartition_type': 'base',
                    'plus_report_line_ids': [cls.pos_tax_report_line_refund_base.id],
                }),

                (0,0, {
                    'factor_percent': 100,
                    'repartition_type': 'tax',
                    'plus_report_line_ids': [cls.pos_tax_report_line_refund_tax.id],
                }),
            ],
        })
        # Needed in order to be able to instantiate the template
        cls.env['ir.model.data'].create({
            'name': 'pos_account_reports.test_tax',
            'module': 'account_reports',
            'res_id': tax_template.id,
            'model': 'account.tax.template',
        })
        pos_tax_id = tax_template._generate_tax(cls.company_parent)['tax_template_to_tax'][tax_template.id]
        cls.pos_tax = cls.env['account.tax'].browse(pos_tax_id)

        pos_tax_account = cls.env['account.account'].create({
            'name': 'POS tax account',
            'code': 'POS tax test',
            'user_type_id': cls.env.ref('account.data_account_type_current_assets').id,
            'company_id': cls.company_parent.id,
        })

        rep_ln_tax = cls.pos_tax.invoice_repartition_line_ids + cls.pos_tax.refund_repartition_line_ids
        rep_ln_tax.filtered(lambda x: x.repartition_type == 'tax').write({'account_id': pos_tax_account.id})

        # Create POS objects
        cls.pos_config = cls.env['pos.config'].create({
            'name': 'Crab Shop',
            'company_id': cls.company_parent.id,
        })

        cls.pos_product = cls.env['product.product'].create({
            'name': 'Crab',
            'type': 'consu',
        })


    def _create_and_pay_pos_order(self, qty, price_unit):
        tax_amount = (self.pos_tax.amount / 100) * qty * price_unit # Only possible because the tax is 'percent' and price excluded. Don't do this at home !
        rounded_total = self.company_parent.currency_id.round(tax_amount + price_unit * qty)

        order = self.env['pos.order'].create({
            'company_id': self.company_parent.id,
            'partner_id': self.partner_a.id,
            'session_id': self.pos_config.current_session_id.id,
            'lines': [(0, 0, {
                'name': "OL/0001",
                'product_id': self.pos_product.id,
                'price_unit': price_unit,
                'qty': qty,
                'tax_ids': [(6, 0, self.pos_tax.ids)],
                'price_subtotal': qty * price_unit,
                'price_subtotal_incl': rounded_total,
            })],
            'amount_total': rounded_total,
            'amount_tax': self.company_parent.currency_id.round(tax_amount),
            'amount_paid': 0,
            'amount_return': 0,
        })

        # Pay the order
        context_payment = {
            "active_ids": [order.id],
            "active_id": order.id
        }
        pos_make_payment = self.env['pos.make.payment'].with_context(context_payment).create({
            'amount': rounded_total,
        })
        pos_make_payment.with_context(context_payment).check()

    def test_pos_tax_report(self):
        self.pos_config.module_account = False
        self._check_tax_report_content()

    def test_pos_tax_report_invoice(self):
        self.pos_config.module_account = True
        self._check_tax_report_content()

    def _check_tax_report_content(self):
        with self.mocked_today('2020-01-01'):
            today = fields.Date.today()
            self.pos_config.open_session_cb()
            self._create_and_pay_pos_order(1, 30)
            self._create_and_pay_pos_order(-1, 40)
            self.pos_config.current_session_id.action_pos_session_closing_control()

            report = self.env['account.generic.tax.report']
            report_opt = report._get_options({'date': {'period_type': 'custom', 'filter': 'custom', 'date_to': today, 'mode': 'range', 'date_from': today}})
            new_context = report._set_context(report_opt)
            inv_report_lines = report.with_context(new_context)._get_lines(report_opt)
            self.assertLinesValues(
                inv_report_lines,
                #   Name                                                Balance
                [   0,                                                  1],
                [
                    (self.pos_tax_report_line_invoice_base.name,        30),
                    (self.pos_tax_report_line_invoice_tax.name,         3),
                    (self.pos_tax_report_line_refund_base.name,         40),
                    (self.pos_tax_report_line_refund_tax.name,          4),
                ],
            )

    # ===========================================================================================================================
    # Methods copy-pasted from other modules or future versions; to be removed when forward-porting

    @contextmanager
    def mocked_today(self, forced_today):
        ''' Helper to make easily a python "with statement" mocking the "today" date.
        :param forced_today:    The expected "today" date as a str or Date object.
        :return:                An object to be used like 'with self.mocked_today(<today>):'.
        '''

        if isinstance(forced_today, str):
            forced_today_date = fields.Date.from_string(forced_today)
            forced_today_datetime = fields.Datetime.from_string(forced_today)
        elif isinstance(forced_today, datetime.datetime):
            forced_today_datetime = forced_today
            forced_today_date = forced_today_datetime.date()
        else:
            forced_today_date = forced_today
            forced_today_datetime = datetime.datetime.combine(forced_today_date, datetime.time())

        def today(*args, **kwargs):
            return forced_today_date

        with patch.object(fields.Date, 'today', today):
            with patch.object(fields.Date, 'context_today', today):
                with patch.object(fields.Datetime, 'now', return_value=forced_today_datetime):
                    yield
