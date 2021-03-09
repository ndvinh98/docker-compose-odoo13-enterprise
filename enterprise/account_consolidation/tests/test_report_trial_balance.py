# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.addons.account_consolidation.tests.account_consolidation_test_classes import AccountConsolidationTestCase


@tagged('post_install', '-at_install', 'trial_balance_report')
class TestTrialBalanceReport(AccountConsolidationTestCase):
    def setUp(self):
        super().setUp()  # providing self.default_company, self.us_company and self.chart
        # Fix test when running on runbot as demo data are loaded and collide with the data of this test
        self.env['consolidation.period'].search([]).unlink()
        self._create_chart_of_accounts(self.chart)
        self._generate_default_periods_and_journals(self.chart)
        self._generate_default_lines()

    def test_default_options(self):
        report = self.env['account.consolidation.trial_balance_report']
        options = report._get_options(None)
        self.assertTrue(options['unfold_all'])
        self.assertTrue(options['hierarchy'])
        self.assertTrue(options['show_zero_balance_accounts'])
        self.assertEquals(0, len(options['unfolded_lines']))

        selected_period_index = 1 # the last created is selected
        # TEST ANALYSIS PERIOD FILTER
        periods = options.get('periods', [])
        # Only one period is similar to base_period
        self.assertEqual(1, len(periods))
        self.assertEqual(periods[0]['id'], self.periods[0].id)

        consolidation_journals = options.get('consolidation_journals', None)
        # TEST CONSOLIDATION JOURNAL FILTER
        self.assertEquals(len(consolidation_journals), len(self.journals))
        self.assertFalse(any([j['selected'] for j in consolidation_journals]))
        expected_journals = (
            self.journals['be'][selected_period_index],
            self.journals['us'][selected_period_index]
        )
        for journal in expected_journals:
            found = False
            for consolidation_journal in consolidation_journals:
                found = consolidation_journal['id'] == journal.id
                if found:
                    break
            self.assertTrue(found, 'Journal %s should be in the filters' % journal.name)

    def test_plain_all_journals(self):
        report = self.env['account.consolidation.trial_balance_report']
        report = report.with_context(default_period_id=self.periods[0].id)
        options = report._get_options(None)
        options['hierarchy'] = False

        lines = report._get_lines(options)
        matrix = self._report_lines_to_matrix(lines)
        expected_matrix = [
            ['Revenue', 5000.0, 4242.0, 9242.0],
            ['Finance Income', 0, 500000.0, 500000.0],
            ['Cost of Sales', -4000.0, -400000.0, -404000.0],
            ['Alone in the dark', 0, 0, 0],
            ['Total', 1000.0, 104242.0, 105242.0]
        ]
        self.assertListEqual(expected_matrix, matrix, 'Report amounts are not all corrects')
        for line in lines:
            line_id = line['id']
            parent_id = line.get('parent_id', None)
            self.assertFalse(line.get('unfoldable', False), 'Account line should not be unfoldable')
            if line.get('class', None) != 'total':
                account = self.env['consolidation.account'].browse(int(line_id))
                self.assertEquals(len(account), 1)
                if line_id != self.consolidation_accounts['alone in the dark'].id:
                    self.assertIsNotNone(line.get('parent_id', None),
                                         'Account line should have a parent_id but does not (%s)' % line)
                    self.assertEquals(parent_id, 'section-%s' % account.group_id.id)
                else:
                    self.assertIsNone(line.get('parent_id', None),
                                      'Account line alone in the dark should not have a parent_id but does (%s)' % line)

        levels = [row['level'] for row in lines]
        expected_levels = [3, 3, 3, 3, 1]
        self.assertListEqual(expected_levels, levels, 'Levels are not all corrects')

    def test_hierarchy_all_journals(self):
        report = self.env['account.consolidation.trial_balance_report']
        report = report.with_context(default_period_id=self.periods[0].id)
        options = report._get_options(None)
        headers = report._get_columns_name(options)
        self.assertEquals(len(headers), len(self.journals) + 2,
                          'Report should have a header by journal + a total column and a first blank column')
        real_headers = headers[1:-1]
        self.assertEquals(real_headers[0]['name'], report._get_journal_title(self.journals['be'][0], options),
                          'First column should be the column of "BE company" journal')
        self.assertEquals(real_headers[1]['name'], report._get_journal_title(self.journals['us'][0], options),
                          'First column should be the column of "US company" journal')

        lines = report._get_lines(options)
        # first line is the orphan
        self.assertEquals(lines[0]['id'], self.consolidation_accounts['alone in the dark'].id)
        # second line is the root section
        self.assertEquals(lines[1]['id'], 'section-%s' % self.sections[0].id)
        self.assertEquals(lines[1]['level'], 1)
        self.assertTrue(lines[1]['unfoldable'])
        self.assertTrue(lines[1]['unfolded'])
        self.assertEquals(len(lines[1]['columns']), 3)
        matrix = self._report_lines_to_matrix(lines)
        expected_matrix = [
            ['Alone in the dark', 0, 0, 0],
            ['Balance sheet', 0, 0, 0],
            ['Profit and loss', 1000.0, 104242.0, 105242.0],
            ['Expense', -4000.0, -400000.0, -404000.0],
            ['Cost of Sales', -4000.0, -400000.0, -404000.0],
            ['Income', 5000.0, 504242.0, 509242.0],
            ['Revenue', 5000.0, 4242.0, 9242.0],
            ['Finance Income', 0, 500000.0, 500000.0],
            ['Total', 1000.0, 104242.0, 105242.0]
        ]
        self.assertListEqual(expected_matrix, matrix, 'Report amounts are not all corrects')
        for line in lines:
            line_id = line['id']
            parent_id = line.get('parent_id', None)
            if str(line_id).startswith('section'):
                section = self.env['consolidation.group'].browse(int(line_id.split('-')[1]))
                self.assertEquals(len(section), 1)
                self.assertTrue(line['unfoldable'], 'Section line should be unfoldable')
                self.assertTrue(line['unfolded'], 'Section line should be unfolded')
                if section.parent_id:
                    self.assertEquals(parent_id, 'section-%s' % section.parent_id.id)
                else:
                    self.assertIsNone(parent_id)
            elif line.get('class', None) != 'total':
                self.assertFalse(line.get('unfoldable', False), 'Account line should not be unfoldable')

                account = self.env['consolidation.account'].browse(int(line_id))
                self.assertEquals(len(account), 1)
                if line_id != self.consolidation_accounts['alone in the dark'].id:
                    self.assertIsNotNone(line.get('parent_id', None),
                                         'Account line should have a parent_id but does not (%s)' % line)
                    self.assertEquals(parent_id, 'section-%s' % account.group_id.id)
                else:
                    self.assertIsNone(line.get('parent_id', None),
                                      'Account line alone in the dark should not have a parent_id but does (%s)' % line)

        levels = [row['level'] for row in lines]
        expected_levels = [1, 1, 1, 2, 3, 2, 3, 3, 1]
        self.assertListEqual(expected_levels, levels, 'Levels are not all corrects')

    def test_hierarchy_one_journal_selected(self):
        report = self.env['account.consolidation.trial_balance_report']
        report = report.with_context(default_period_id=self.periods[0].id)
        options = report._get_options(None)
        options['consolidation_journals'][0]['selected'] = True
        headers = report._get_columns_name(options)
        self.assertEquals(len(headers), len(self.journals) + 1,
                          'Report should have a header by selected journal + a total column and a first blank column')
        real_headers = headers[1:-1]
        self.assertEquals(real_headers[0]['name'], report._get_journal_title(self.journals['be'][0], options),
                          '"%s" journal should be in headers' % self.journals['be'][0].name)

        for real_header in real_headers:
            self.assertNotEquals(real_header['name'], report._get_journal_title(self.journals['us'][0], options),
                                 '"US Company" journal should be in headers')

        lines = report._get_lines(options)
        self.assertEquals(lines[0]['id'], self.consolidation_accounts['alone in the dark'].id)
        self.assertEquals(lines[1]['id'], 'section-%s' % self.sections[0].id)
        self.assertEquals(lines[1]['level'], 1)
        self.assertTrue(lines[1]['unfoldable'])
        self.assertTrue(lines[1]['unfolded'])
        self.assertEquals(len(lines[1]['columns']), 2)
        matrix = self._report_lines_to_matrix(lines)
        expected_matrix = [
            ['Alone in the dark', 0, 0],
            ['Balance sheet', 0, 0],
            ['Profit and loss', 1000.0, 1000.0],
            ['Expense', -4000.0, -4000.0],
            ['Cost of Sales', -4000.0, -4000.0],
            ['Income', 5000.0, 5000.0],
            ['Revenue', 5000.0, 5000.0],
            ['Finance Income', 0, 0],
            ['Total', 1000.0, 1000.0]
        ]
        self.assertListEqual(expected_matrix, matrix, 'Report amounts are not all corrects')
        for line in lines:
            line_id = line['id']
            parent_id = line.get('parent_id', None)
            if str(line_id).startswith('section'):
                section = self.env['consolidation.group'].browse(int(line_id.split('-')[1]))
                self.assertEquals(len(section), 1)
                self.assertTrue(line['unfoldable'], 'Section line should be unfoldable')
                self.assertTrue(line['unfolded'], 'Section line should be unfolded')
                if section.parent_id:
                    self.assertEquals(parent_id, 'section-%s' % section.parent_id.id)
                else:
                    self.assertIsNone(parent_id)
            elif line.get('class', None) != 'total':
                self.assertFalse(line.get('unfoldable', False), 'Account line should not be unfoldable')
                account = self.env['consolidation.account'].browse(int(line_id))
                self.assertEquals(len(account), 1)
                if line_id != self.consolidation_accounts['alone in the dark'].id:
                    self.assertIsNotNone(line.get('parent_id', None),
                                         'Account line should have a parent_id but does not (%s)' % line)
                    self.assertEquals(parent_id, 'section-%s' % account.group_id.id)
                else:
                    self.assertIsNone(line.get('parent_id', None),
                                      'Account line alone in the dark should not have a parent_id but does (%s)' % line)

        levels = [row['level'] for row in lines]
        expected_levels = [1, 1, 1, 2, 3, 2, 3, 3, 1]
        self.assertListEqual(expected_levels, levels, 'Levels are not all corrects')

    # HELPERS
    def _report_lines_to_matrix(self, lines):
        matrix = []
        for line in lines:
            matrix_line = [line['name']] + [col['no_format_name'] for col in line['columns']]
            matrix.append(matrix_line)
        return matrix

    def _generate_default_periods_and_journals(self, chart):
        chart = chart or self.chart
        Journal = self.env['consolidation.journal']
        self.periods = [
            self._create_analysis_period('2019-01-01', '2019-12-31', chart),
            self._create_analysis_period('2020-01-01', '2020-12-31', chart)
        ]
        self.journals = {'be': [], 'us': []}
        for period in self.periods:
            cp_be = self._create_company_period(period=period, company=self.default_company,
                                                start_date=period.date_analysis_begin,
                                                end_date=period.date_analysis_end)
            cp_us = self._create_company_period(period=period, company=self.us_company,
                                                start_date=period.date_analysis_begin,
                                                end_date=period.date_analysis_end)
            self.journals['be'].append(Journal.create({
                'name': cp_be.company_name,
                'period_id': period.id,
                'chart_id': self.chart.id,
                'company_period_id': cp_be.id,
            }))
            self.journals['us'].append(Journal.create({
                'name': cp_us.company_name,
                'period_id': period.id,
                'chart_id': self.chart.id,
                'company_period_id': cp_us.id,
            }))

    def _generate_default_lines(self):
        JournalLine = self.env['consolidation.journal.line']
        # PERIOD 0
        #### COST OF SALES
        JournalLine.create({
            'journal_id': self.journals['be'][0].id,
            'account_id': self.consolidation_accounts['cost of sales'].id,
            'amount': -4000
        })
        JournalLine.create({
            'journal_id': self.journals['us'][0].id,
            'account_id': self.consolidation_accounts['cost of sales'].id,
            'amount': -400000
        })
        #### REVENUE
        JournalLine.create({
            'journal_id': self.journals['be'][0].id,
            'account_id': self.consolidation_accounts['revenue'].id,
            'amount': 5000
        })
        JournalLine.create({
            'journal_id': self.journals['us'][0].id,
            'account_id': self.consolidation_accounts['revenue'].id,
            'amount': 4242
        })

        #### FINANCE INCOME
        JournalLine.create({
            'journal_id': self.journals['us'][0].id,
            'account_id': self.consolidation_accounts['finance income'].id,
            'amount': 500000
        })

        # PERIOD 1
        JournalLine.create({
            'journal_id': self.journals['be'][1].id,
            'account_id': self.consolidation_accounts['revenue'].id,
            'amount': 15000
        })
        JournalLine.create({
            'journal_id': self.journals['be'][1].id,
            'account_id': self.consolidation_accounts['cost of sales'].id,
            'amount': -12000
        })
        JournalLine.create({
            'journal_id': self.journals['us'][1].id,
            'account_id': self.consolidation_accounts['finance income'].id,
            'amount': 1500000
        })

    def _create_chart_of_accounts(self, chart):
        Section = self.env['consolidation.group']
        chart = chart or self.chart
        bst = Section.create({
            'name': "Balance sheet",
            'chart_id': chart.id}
        )
        pal = Section.create({
            'name': "Profit and loss",
            'chart_id': chart.id
        })
        exp = Section.create({
            'name': "Expense",
            'parent_id': pal.id,
            'chart_id': chart.id
        })
        inc = Section.create({
            'name': "Income",
            'parent_id': pal.id,
            'chart_id': chart.id
        })
        self.sections = [bst, pal, exp, inc]

        self.consolidation_accounts = {
            'revenue': self._create_consolidation_account('Revenue', chart=chart, section=inc.id),
            'finance income': self._create_consolidation_account('Finance Income', chart=chart, section=inc.id),
            'cost of sales': self._create_consolidation_account('Cost of Sales', chart=chart, section=exp.id),
            'alone in the dark': self._create_consolidation_account('Alone in the dark', chart=chart, section=None)
        }
