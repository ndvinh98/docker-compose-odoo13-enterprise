# -*- coding: utf-8 -*-
from odoo.tests import common
from datetime import date


class AccountConsolidationTestCase(common.TransactionCase):
    def setUp(self):
        super().setUp()
        # DEFAULT DEFAULT COMPANY
        self.default_company = self.env.ref('base.main_company')

        # DEFAULT US COMPANY
        self.us_company = self.env['res.company'].create({'name': 'Vincent Company', 'currency_id': 2})

        # DEFAULT CHART
        self.chart = self.env['consolidation.chart'].create({
            'name': 'Default chart',
            'currency_id': 1,
            'company_ids': [(6, 0, (self.us_company.id, self.default_company.id))]
        })

    def _create_consolidation_account(self, name='BLAH', currency_mode='end', chart=None, section=None):
        return self.env['consolidation.account'].create({
            'name': name,
            'currency_mode': currency_mode,
            'chart_id': (chart or self.chart).id,
            'group_id': section or None
        })

    def _create_analysis_period(self, start_date='2019-01-01', end_date='2019-12-31', chart=None):
        return self.env['consolidation.period'].create({
            'chart_id': (chart or self.chart).id,
            'date_analysis_begin': start_date,
            'date_analysis_end': end_date
        })

    def _create_company_period(self, period=None, company=None, start_date='2019-01-01', end_date='2019-12-31',
                               rate_consolidation=100):
        period = period or self._create_analysis_period(start_date=start_date, end_date=end_date)
        return self.env['consolidation.company_period'].create({
            'chart_id': self.chart.id,
            'date_company_begin': start_date,
            'date_company_end': end_date,
            'period_id': period.id,
            'company_id': (company or self.us_company).id,
            'rate_consolidation': rate_consolidation
        })

    def _create_basic_move(self, amount, journal=False, account_credit=False, account_debit=False, company=False,
                           move_date=False):
        company = company or self.default_company
        journal = journal or self._create_journal(company=company)
        account_credit = account_credit or self._create_account('XX1', 'Credit account', company=company)
        account_debit = account_debit or self._create_account('XX2', 'Debit account', company=company)
        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'date': move_date or date.today(),
            'line_ids': [
                (0, 0, {
                    'account_id': account_credit.id,
                    'credit': amount,
                    'company_id': company.id
                }),
                (0, 0, {
                    'account_id': account_debit.id,
                    'debit': amount,
                    'company_id': company.id
                })
            ]
        })
        move.post()
        return move

    def _create_account(self, code, name="Default account", type=False, company=False):
        type = type or self.env.ref('account.data_account_type_receivable')
        company = company or self.default_company
        return self.env['account.account'].create({
            'name': name,
            'code': code,
            'user_type_id': type.id,
            'company_id': company.id,
            'reconcile': type.type in ('receivable', 'payable'),
        })

    def _create_journal(self, name="Default journal", code="BNK67", company=False):
        company = company or self.default_company
        return self.env['account.journal'].create({'name': name, 'code': code, 'type': 'bank',
                                                   'bank_acc_number': '123456', 'company_id': company.id})
