# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.addons.account_consolidation.tests.account_consolidation_test_classes import AccountConsolidationTestCase
from odoo.exceptions import UserError
from unittest.mock import Mock
from odoo.models import ValidationError


@tagged('post_install', '-at_install')
class TestAccountConsolidationJournalLine(AccountConsolidationTestCase):
    def setUp(self):
        super().setUp()
        self.dummy_account = self.env['consolidation.account'].create({'name': 'DUMMY'})

    # TESTS
    def test__check_conditional_unicity(self):
        account = self._create_consolidation_account()
        account2 = self._create_consolidation_account()
        editable_journal = self.env['consolidation.journal'].create({'name': 'BLAH', 'chart_id': self.chart.id})
        not_editable_journal = self.env['consolidation.journal'].create({
            'name': 'BLAH',
            'auto_generated': True,
            'chart_id': self.chart.id
        })

        self.env['consolidation.journal.line'].create({
            'journal_id': editable_journal.id,
            'account_id': account.id,
            'amount': 42,
        })
        # Can create multiple lines in an editable journal with the same account
        self.env['consolidation.journal.line'].create({
            'journal_id': editable_journal.id,
            'account_id': account.id,
            'amount': 42,
        })
        editable_journal_line = self.env['consolidation.journal.line'].create({
            'journal_id': editable_journal.id,
            'account_id': account2.id,
            'amount': 42,
        })
        # Can update a journal line to set same account and not editable journal
        editable_journal_line.write({'account_id': account.id})

        self.env['consolidation.journal.line'].create({
            'journal_id': not_editable_journal.id,
            'account_id': account.id,
            'amount': 42,
        })

        # Cannot create a journal line for same account and not editable journal
        with self.assertRaises(ValidationError):
            self.env['consolidation.journal.line'].create({
                'journal_id': not_editable_journal.id,
                'account_id': account.id,
                'amount': 84,
            })

        not_editable_journal_line = self.env['consolidation.journal.line'].create({
            'journal_id': not_editable_journal.id,
            'account_id': account2.id,
            'amount': 126
        })

        # Cannot update a journal line to set same account and not editable journal
        with self.assertRaises(UserError):
            not_editable_journal_line.write({'account_id': account.id})

    def test_adjust_grid_editable_journal(self):
        journal = self.env['consolidation.journal'].create({'name': 'blah', 'chart_id': self.chart.id})
        account = self._create_consolidation_account()
        initial_amount = 42.0
        change_amount = 14.0
        journal_line = self.env['consolidation.journal.line'].create({
            'journal_id': journal.id,
            'account_id': account.id,
            'amount': initial_amount
        })
        params = {
            'row_domain': [('id', '=', journal_line.id)],
            'column_field': 'journal_id',
            'column_value': journal.id,
            'cell_field': 'amount',
            'change': change_amount
        }
        created_lines = journal_line.adjust_grid(*params.values())
        self.assertAlmostEqual(journal_line.amount, initial_amount)
        self.assertAlmostEqual(journal.balance, initial_amount + change_amount)
        self.assertEqual(len(created_lines), 1)

        self.assertAlmostEqual(created_lines.amount, change_amount)
        self.assertEqual(created_lines.note, 'Trial balance adjustment')
        self.assertEqual(created_lines.account_id.id, account.id)
        self.assertEqual(created_lines.journal_id.id, journal.id)

    def test_adjust_grid(self):
        JournalLine = self.env['consolidation.journal.line']
        journal_line = self._create_journal_line(True)
        params = {
            'domain': [('id', '=', journal_line.id)],
            'column_field': 'journal_id',
            'column_value': journal_line.journal_id.id,
            'cell_field': 'amount',
            'change': 14.0
        }

        # JUST EDITED (no journal line created)
        # GIVEN
        # WHEN
        created_journal_line = journal_line.adjust_grid(*params.values())
        # THEN
        self.assertEqual(len(created_journal_line), 1, 'A journal line has been created')
        self.assertAlmostEqual(created_journal_line.amount, params['change'],
                               msg='Newly create journal line has the change amount as amount')

        # CANNOT EDIT AS LINKED TO COMPANY
        # GIVEN
        self._make_journal_line_not_editable(journal_line)
        amount_before = journal_line.amount
        # WHEN
        with self.assertRaises(UserError):
            journal_line.adjust_grid(*params.values())
        # THEN
        self.assertAlmostEqual(journal_line.amount, amount_before, msg='Old journal line did not change')

        # CANNOT CREATE AS JOURNAL LINKED TO COMPANY (no journal line created)
        # GIVEN
        journal = self.env['consolidation.journal'].create({'name': 'bluh', 'auto_generated': True, 'chart_id': self.chart.id})
        params['column_value'] = journal.id

        # THEN
        with self.assertRaises(UserError):
            journal_line.adjust_grid(*params.values())

        # CAN CREATE AS JOURNAL NOT AUTO-GENERATED
        # GIVEN
        journal.write({'auto_generated': False})
        params['change'] = 999.42
        amount_before = journal_line.amount
        # WHEN
        created_journal_line = journal_line.adjust_grid(*params.values())
        # THEN
        self.assertAlmostEqual(journal_line.amount, amount_before, msg='Old journal line did not change')
        self.assertEqual(len(created_journal_line), 1, 'A journal line has been created')
        self.assertAlmostEqual(created_journal_line.amount, params['change'],
                               msg='Newly create journal line has the change amount as amount')

    def test_write(self):
        account = self._create_consolidation_account()
        journal = self.env['consolidation.journal'].create({'name': 'BLAH', 'auto_generated': True, 'chart_id': self.chart.id})
        journal_line = self.env['consolidation.journal.line'].create({
            'journal_id': journal.id,
            'account_id': account.id,
            'amount': 42
        })
        with self.assertRaises(UserError):
            journal_line.write({'amount': 84})
        journal.write({'auto_generated': False})
        journal_line.write({'amount': 84})

    def test_unlink(self):
        account = self._create_consolidation_account()
        journal = self.env['consolidation.journal'].create({'name': 'BLAH', 'auto_generated': True, 'chart_id': self.chart.id})
        journal_line = self.env['consolidation.journal.line'].create({
            'journal_id': journal.id,
            'account_id': account.id,
            'amount': 42
        })
        with self.assertRaises(UserError):
            journal_line.unlink()
        journal.write({'auto_generated': False})
        journal_line.unlink()

    def test__grid_column_info(self):
        JournalLine = self.env['consolidation.journal.line']
        Journal = self.env['consolidation.journal']
        aperiod = self._create_analysis_period()
        journal_in = Journal.create({'name': 'blah', 'period_id': aperiod.id, 'chart_id': self.chart.id,})
        journal_out = Journal.create({'name': 'bluh', 'chart_id': self.chart.id,})
        manager = JournalLine.with_context(default_period_id=aperiod.id)
        cinfo = manager._grid_column_info('journal_id', 'dummyrange')
        self.assertEqual(len(cinfo.values), 1)
        self.assertEqual(cinfo.values[0]['values']['journal_id'], (journal_in.id, journal_in.name))
        self.assertEqual(cinfo.values[0]['domain'], [('journal_id', '=', journal_in.id)], )

        journal_out.write({'period_id': aperiod.id})
        manager = JournalLine.with_context(default_period_id=aperiod.id)
        cinfo = manager._grid_column_info('journal_id', 'dummyrange')
        self.assertEqual(len(cinfo.values), 2)
        for i, journal in enumerate((journal_in, journal_out)):
            self.assertEqual(cinfo.values[i]['values']['journal_id'], (journal.id, journal.name))
            self.assertEqual(cinfo.values[i]['domain'], [('journal_id', '=', journal.id)], )

    def test__grid_make_empty_cell(self):
        # Needed to call method
        ml = self._create_journal_line()
        row_domain = []
        column_domain = []
        view_domain = []

        cell = ml._grid_make_empty_cell(row_domain, column_domain, view_domain)
        self.assertFalse(cell['readonly'], 'Created empty cell in a column with no journal should not be readonly')

        m = self.env['consolidation.journal'].create({'name': 'bluh', 'chart_id': self.chart.id})
        column_domain.append(('journal_id', '=', m.id))

        cell = ml._grid_make_empty_cell(row_domain, column_domain, view_domain)
        self.assertFalse(cell['readonly'],
                         'Created empty cell in the column of a non-readonly journal should not be readonly')

        m.write({'auto_generated': True})
        cell = ml._grid_make_empty_cell(row_domain, column_domain, view_domain)
        self.assertTrue(cell['readonly'], 'Created empty cell in the column of a readonly journal should be readonly')

    def test__journal_is_editable(self):
        journal = self.env['consolidation.journal'].create({'name': 'blah', 'chart_id': self.chart.id})
        journal_line = self.env['consolidation.journal.line'].create({
            'journal_id': journal.id,
            'account_id': self.dummy_account.id
        })
        params = {
            'domain': [('id', '=', journal_line.id)],
            'column_field': 'journal_id',
            'column_value': journal.id
        }
        # Should be True as journal created
        self.assertTrue(journal_line._journal_is_editable(*params.values()))

        # Should be False as journal is linked to a company
        journal.auto_generated = True
        self.assertFalse(journal_line._journal_is_editable(*params.values()))

    # PRIVATES

    def _create_journal_line(self, editable=True):
        journal = self.env['consolidation.journal'].create({'name': 'blah', 'chart_id': self.chart.id})
        record = self.env['consolidation.journal.line'].create({
            'journal_id': journal.id,
            'account_id': self.dummy_account.id
        })
        if not editable:
            self._make_journal_line_not_editable(record)
        return record

    def _make_journal_line_not_editable(self, journal_line):
        journal_line.journal_id.write({'auto_generated': True})
