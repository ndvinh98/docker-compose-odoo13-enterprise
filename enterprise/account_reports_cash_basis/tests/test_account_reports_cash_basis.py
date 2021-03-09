# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tools import date_utils

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install', '-at_install')
class TestAccountReports(TestAccountReportsCommon):
    def test_general_ledger_cash_basis(self):
        ''' Test folded/unfolded lines with the cash basis option. '''
        # Check the cash basis option.
        report = self.env['account.general.ledger']
        options = self._init_options(report, *date_utils.get_month(self.mar_year_minus_1))
        options['cash_basis'] = True
        report = report.with_context(report._set_context(options))

        lines = report._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                    Debit           Credit          Balance
            [   0,                                      5,              6,              7],
            [
                # Accounts.
                ('101401 Bank',                          800.00,        1750.00,     -950.00),
                ('121000 Account Receivable',            800.00,         800.00,        0.00),
                ('131000 Tax Paid',                      228.26,           0.00,      228.26),
                ('211000 Account Payable',              1750.00,        1750.00,        0.00),
                ('251000 Tax Received',                    0.00,         104.34,     -104.34),
                ('400000 Product Sales',                   0.00,         695.66,     -695.66),
                ('600000 Expenses',                      478.26,           0.00,      478.26),
                ('999999 Undistributed Profits/Losses', 1043.48,           0.00,     1043.48),
                # Report Total.
                ('Total',                               5100.00,        5100.00,        0.00),
            ],
        )

        # Mark the '101200 Account Receivable' line to be unfolded.
        line_id = lines[1]['id']
        options['unfolded_lines'] = [line_id]
        options['cash_basis'] = False  # Because we are in the same transaction, the table temp_account_move_line still exists
        report = report.with_context(report._set_context(options))
        lines = report._get_lines(options, line_id=line_id)
        self.assertLinesValues(
            lines,
            #   Name                                    Date            Partner         Currency    Debit           Credit          Balance
            [   0,                                      1,              3,              4,          5,              6,              7],
            [
                # Account.
                ('121000 Account Receivable',           '',             '',             '',         800.00,         800.00,         0.00),
                # Initial Balance.
                ('Initial Balance',                     '',             '',             '',         700.00,         700.00,         0.00),
                # Account Move Lines.
                ('INV/2017/0005',                       '03/01/2017',   'partner_c',    '',         100.00,             '',       100.00),
                ('BNK1/2017/0004',                      '03/01/2017',   'partner_c',    '',             '',         100.00,         0.00),
                # Account Total.
                ('Total',                               '',             '',             '',         800.00,         800.00,         0.00),
            ],
        )

    def test_trial_balance_cash_basis(self):
        ''' Test the cash basis option. '''
        # Check the cash basis option.
        report = self.env['account.coa.report']
        options = self._init_options(report, *date_utils.get_month(self.mar_year_minus_1))
        options['cash_basis'] = True
        report = report.with_context(report._set_context(options))
        company_ids = (self.company_parent + self.company_child_eur).ids

        lines = report.with_context(allowed_company_ids=company_ids)._get_lines(options)
        self.assertLinesValues(
            lines,
            #                                           [  Initial Balance   ]          [   Month Balance    ]          [       Total        ]
            #   Name                                    Debit           Credit          Debit           Credit          Debit           Credit
            [   0,                                      1,              2,              3,              4,              5,              6],
            [
                # Accounts.
                ('101401 Bank',                         '',             750.00,         100.00,         300.00,         '',             950.00),
                ('121000 Account Receivable',           '',             '',             100.00,         100.00,         '',             ''),
                ('131000 Tax Paid',                     189.13,         '',             39.13,          '',             228.26,         ''),
                ('211000 Account Payable',              '',             '',             300.00,         300.00,         '',             ''),
                ('251000 Tax Received',                 '',             91.30,          '',             13.04,          '',             104.34),
                ('400000 Product Sales',                '',             608.70,         '',             86.96,          '',             695.66),
                ('600000 Expenses',                     217.39,         '',             260.87,         '',             478.26,         ''),
                ('999999 Undistributed Profits/Losses', 1043.48,        '',             '',             '',             1043.48,        ''),
                # Report Total.
                ('Total',                               1450.00,        1450.00,        800.00,         800.00,         1750.00,        1750.00),
            ],
        )

    def test_balance_sheet_cash_basis(self):
        ''' Test folded/unfolded lines with the cash basis option. '''
        # Check the cash basis option.
        report = self.env.ref('account_reports.account_financial_report_balancesheet0')._with_correct_filters()
        options = self._init_options(report, *date_utils.get_month(self.mar_year_minus_1))
        options['cash_basis'] = True
        report = report.with_context(report._set_context(options))
        company_ids = (self.company_parent + self.company_child_eur).ids

        lines = report.with_context(allowed_company_ids=company_ids)._get_lines(options)
        self.assertLinesValues(
            lines,
            #   Name                                            Balance
            [   0,                                              1],
            [
                ('ASSETS',                                      ''),
                ('Current Assets',                              ''),
                ('Bank and Cash Accounts',                      -950.00),
                ('Receivables',                                 0.00),
                ('Current Assets',                              228.26),
                ('Prepayments',                                 0.00),
                ('Total Current Assets',                        -721.74),
                ('Plus Fixed Assets',                           0.00),
                ('Plus Non-current Assets',                     0.00),
                ('Total ASSETS',                                -721.74),

                ('LIABILITIES',                                 ''),
                ('Current Liabilities',                         ''),
                ('Current Liabilities',                         104.35),
                ('Payables',                                    0.00),
                ('Total Current Liabilities',                   104.35),
                ('Plus Non-current Liabilities',                0.00),
                ('Total LIABILITIES',                           104.35),

                ('EQUITY',                                      ''),
                ('Unallocated Earnings',                        ''),
                ('Current Year Unallocated Earnings',           ''),
                ('Current Year Earnings',                       217.39),
                ('Current Year Allocated Earnings',             0.00),
                ('Total Current Year Unallocated Earnings',     217.39),
                ('Previous Years Unallocated Earnings',         -1043.48),
                ('Total Unallocated Earnings',                  -826.09),
                ('Retained Earnings',                           0.00),
                ('Total EQUITY',                                -826.09),

                ('LIABILITIES + EQUITY',                        -721.74),
            ],
        )
