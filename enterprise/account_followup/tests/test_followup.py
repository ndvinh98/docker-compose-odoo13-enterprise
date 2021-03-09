# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged, common
from odoo.tools.misc import formatLang
import time
from odoo import fields
from odoo.addons.account.tests.account_test_no_chart import TestAccountNoChartCommon
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon
from dateutil.relativedelta import relativedelta


@tagged('post_install', '-at_install')
class TestAccountFollowup(TestAccountNoChartCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        super().setUpAdditionalAccounts()
        super().setUpAccountJournal()

        mock_date = time.strftime('%Y') + '-06-26'
        cls.minimal_options = {
            'date': {
                'date_from': mock_date,
                'date_to': mock_date,
            },
        }

    def test_05_followup_multicompany(self):
        date_sale = fields.Date.today()

        # Company 0
        invoice_move = self.env['account.move'].with_context(default_type='out_invoice').create({
            'partner_id': self.partner_customer_usd.id,
            'date': date_sale,
            'journal_id': self.journal_sale.id,
            'invoice_line_ids': [
                (0, 0, {'quantity': 1, 'price_unit': 30}),
            ],
        })


        # Company 1
        company1 = self.env['res.company'].create({'name': 'company1'})

        account_sale1 = self.account_revenue.copy({'company_id': company1.id})
        account_rec1 = self.account_receivable.copy({'company_id': company1.id})
        sale_journal1 = self.journal_sale.copy({
            'company_id': company1.id,
            'default_debit_account_id': account_sale1.id,
            'default_credit_account_id': account_sale1.id,
        })
        self.partner_customer_usd.with_context(force_company=company1.id).property_account_receivable_id = account_rec1

        invoice_move1 = self.env['account.move'].with_context(default_type='out_invoice').create({
            'partner_id': self.partner_customer_usd.id,
            'date': date_sale,
            'journal_id': sale_journal1.id,
            'invoice_line_ids': [
                (0, 0, {'quantity': 1, 'price_unit': 60}),
            ],
        })

        invoice_move.post()
        invoice_move1.post()

        # For company 0
        main_company = self.env.ref('base.main_company')
        currency = main_company.currency_id
        self.assertEqual(self.partner_customer_usd.credit, 30.0)

        options = dict(self.minimal_options)
        options['partner_id'] = self.partner_customer_usd.id

        lines = self.env['account.followup.report']._get_lines(options)

        # Title line + actual business line
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[1]['class'], 'total')
        self.assertEqual(len(lines[1]['columns']), 7)

        self.assertEqual(lines[1]['columns'][5]['name'], 'Total Due')
        self.assertEqual(lines[1]['columns'][6]['name'], formatLang(self.env, 30.00, currency_obj=currency))

        # For company 1
        currency = company1.currency_id
        self.assertEqual(self.partner_customer_usd.with_context(allowed_company_ids=company1.ids).credit, 60.0)

        lines = self.env['account.followup.report'].with_context(allowed_company_ids=company1.ids)._get_lines(options)

        # Title line + actual business line
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[1]['class'], 'total')
        self.assertEqual(len(lines[1]['columns']), 7)

        self.assertEqual(lines[1]['columns'][5]['name'], 'Total Due')
        self.assertEqual(lines[1]['columns'][6]['name'], formatLang(self.env, 60.00, currency_obj=currency))

    def test_followup_mail_attachments(self):
        '''Test that join_invoices options is working: sending attachment from multiple invoices'''
        test_followup_level = self.env['account_followup.followup.line'].create({
            'name': 'test_followup_level',
            'delay': 4,
            'description': 'Test Followup Level',
            'send_email': True,
            'print_letter': False,
            'join_invoices': True,
        })

        test_partner = self.env['res.partner'].create({
            'name': 'Pinco Pallino',
            'email': 'test@example.com',
        })
        test_partner.property_account_receivable_id = self.account_receivable

        today = fields.Date.today()

        # generating invoices
        invoices = self.env['account.move'].create([
            {
                'partner_id': test_partner.id,
                'invoice_date': today + relativedelta(days=-10),
                'type': 'out_invoice',
                'invoice_line_ids': [(0, 0, {'quantity': 1, 'price_unit': 40})],
            },
            {
                'partner_id': test_partner.id,
                'invoice_date': today + relativedelta(days=-11),
                'type': 'out_invoice',
                'invoice_line_ids': [(0, 0, {'quantity': 2, 'price_unit': 40})],
            },
        ])
        invoices.post()

        some_attachments = self.env['ir.attachment']

        # creating and linking attachment with invoices
        for inv in invoices:
            att_id = self.env['ir.attachment'].create({
                'name': 'some_attachment.pdf',
                'res_id': inv.id,
                'res_model': 'account.move',
                'datas': 'test',
                'type': 'binary',
            })
            some_attachments += att_id
            inv._message_set_main_attachment_id([(4, att_id.id)])

        # triggering followup report notice
        test_partner._compute_unpaid_invoices()
        options = dict(self.minimal_options)
        options['partner_id'] = test_partner.id

        # sending email with attachments
        self.env['account.followup.report'].send_email(options)

        # retrieving attachments from the last sent mail
        sent_attachments = self.env['mail.message'].search([('partner_ids', '=', test_partner.id)]).attachment_ids

        self.assertEqual(some_attachments, sent_attachments)

    def test_followup_level_and_status(self):
        self.env['account_followup.followup.line'].search([]).unlink()
        (first_followup_level, second_followup_level) = self.env['account_followup.followup.line'].create([
            {
                'name': 'first_followup_level',
                'delay': 15,
                'description': 'First Followup Level',
                'send_email': False,
                'print_letter': False,
            },
            {
                'name': 'second_followup_level',
                'delay': 25,
                'description': 'Second Followup Level',
                'send_email': False,
                'print_letter': False,
            },
        ])
        test_partner = self.env['res.partner'].create({
            'name': 'Mr Bluesky',
        })
        test_partner.property_account_receivable_id = self.account_receivable

        today = fields.Date.today()
        tomorrow = today + relativedelta(days=1)
        ten_days_ago = today + relativedelta(days=-10)
        forty_days_ago = today + relativedelta(days=-40)

        self.assertNotIn(test_partner.id, test_partner._query_followup_level())
        today_invoice = self.env['account.move'].create({
            'partner_id': test_partner.id,
            'invoice_date': tomorrow,
            'type': 'out_invoice',
            'invoice_line_ids': [(0, 0, {'quantity': 1, 'price_unit': 40})]
        })
        today_invoice.post()

        # only a recent invoice, nothing to do
        self.assertEqual(test_partner._query_followup_level()[test_partner.id]['followup_level'], None)
        self.assertEqual(test_partner._query_followup_level()[test_partner.id]['followup_status'], 'no_action_needed')

        ten_days_ago_invoice = self.env['account.move'].create({
            'partner_id': test_partner.id,
            'invoice_date': ten_days_ago,
            'type': 'out_invoice',
            'invoice_line_ids': [(0, 0, {'quantity': 1, 'price_unit': 30})]
        })
        ten_days_ago_invoice.post()

        # there is an overdue invoice, but it is not taken in the delay
        self.assertEqual(test_partner._query_followup_level()[test_partner.id]['followup_level'], None)
        self.assertEqual(test_partner._query_followup_level()[test_partner.id]['followup_status'], 'with_overdue_invoices')

        forty_days_ago_invoice = self.env['account.move'].create({
            'partner_id': test_partner.id,
            'invoice_date': forty_days_ago,
            'type': 'out_invoice',
            'invoice_line_ids': [(0, 0, {'quantity': 1, 'price_unit': 20})]
        })
        forty_days_ago_invoice.post()

        # the last invoice was due for longer than the delay
        self.assertEqual(test_partner._query_followup_level()[test_partner.id]['followup_level'], first_followup_level.id)
        self.assertEqual(test_partner._query_followup_level()[test_partner.id]['followup_status'], 'in_need_of_action')

        # execute followup needed
        test_partner._execute_followup_partner()

        # no action needed because the date for next followup is in the future
        self.assertEqual(test_partner.payment_next_action_date, today + relativedelta(days=10))
        self.assertEqual(test_partner._query_followup_level()[test_partner.id]['followup_level'], second_followup_level.id)
        self.assertEqual(test_partner._query_followup_level()[test_partner.id]['followup_status'], 'with_overdue_invoices')

        # no action needed because followup of level 1 has already been done for all the lines
        test_partner.payment_next_action_date = today + relativedelta(days=-1)
        self.assertEqual(test_partner._query_followup_level()[test_partner.id]['followup_level'], second_followup_level.id)
        self.assertEqual(test_partner._query_followup_level()[test_partner.id]['followup_status'], 'in_need_of_action')

        # execute followup needed
        test_partner._execute_followup_partner()

        # stay on level 2, but the date should be set to later
        self.assertEqual(test_partner._query_followup_level()[test_partner.id]['followup_level'], second_followup_level.id)
        self.assertEqual(test_partner._query_followup_level()[test_partner.id]['followup_status'], 'with_overdue_invoices')

        # register a payment for the older invoice
        self.env['account.payment.register'].with_context(active_model='account.move', active_ids=forty_days_ago_invoice.ids).create({
            'payment_date': today,
            'journal_id': self.journal_sale.id,
        }).create_payments()

        # nothing more to see as the first invoice was earlier than the delay
        self.assertEqual(test_partner._query_followup_level()[test_partner.id]['followup_level'], None)
        self.assertEqual(test_partner._query_followup_level()[test_partner.id]['followup_status'], 'with_overdue_invoices')


@tagged('post_install', '-at_install')
class TestAccountFollowupReports(TestAccountReportsCommon):
    @classmethod
    def setUpClass(cls):
        super(TestAccountFollowupReports, cls).setUpClass()
        cls.env['account_followup.followup.line'].search([]).unlink()
        cls.first_followup_level = cls.env['account_followup.followup.line'].create({
            'name': 'first_followup_level',
            'delay': 10,
            'description': 'First Followup Level',
        })
        cls.second_followup_level = cls.env['account_followup.followup.line'].create({
            'name': 'second_followup_level',
            'delay': 20,
            'description': 'Second Followup Level',
        })

        cls.partner_a.write({
            'email': 'partner_a@mypartners.xyz',
        })

    def test_followup_report_initial_state(self):
        ''' Test folded/unfolded lines. '''
        # Init options.
        report = self.env['account.followup.report']
        options = report._get_options(None)
        options['partner_id'] = self.partner_a.id
        report = report.with_context(report._set_context(options))

        self.assertLinesValues(
            report._get_lines(options),
            #   Name                                    Date,           Due Date,       Doc.    Comm.                Exp. Date   Blocked             Total Due
            [   0,                                      1,              2,              3,      4,                   5,          6,                  7],
            [
                ('INV/2017/0001',                       '01/01/2017',   '01/01/2017',   '',     'INV/2017/0001',     '',         '',                 115.00),
                ('INV/2016/0001',                       '12/01/2016',   '12/01/2016',   '',     'INV/2016/0001',     '',         '',                 780.00),
                ('',                                    '',             '',             '',     '',                  '',         'Total Due',        895.00),
                ('',                                    '',             '',             '',     '',                  '',         'Total Overdue',    895.00),
            ],
        )
