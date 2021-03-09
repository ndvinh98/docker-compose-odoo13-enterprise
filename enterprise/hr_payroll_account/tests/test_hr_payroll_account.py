# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
import odoo.tests

from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

from odoo import fields, models, tools
from odoo.modules.module import get_module_resource
from odoo.addons.hr_payroll.tests.common import TestPayslipContractBase


@odoo.tests.tagged('post_install', '-at_install')
class TestHrPayrollAccount(TestPayslipContractBase):

    def _load(self, module, *args):
        tools.convert_file(
            self.cr, 'hr_payroll_account',
            get_module_resource(module, *args), {}, 'init', False, 'test', self.registry._assertion_report)

    def setUp(self):
        super(TestHrPayrollAccount, self).setUp()

        self._load('account', 'test', 'account_minimal_test.xml')

        self.res_partner_bank = self.env['res.partner.bank'].create({
            'acc_number': '001-9876543-21',
            'partner_id': self.ref('base.res_partner_12'),
            'acc_type': 'bank',
            'bank_id': self.ref('base.res_bank_1'),
        })

        self.ir_sequence = self.env['ir.sequence'].create({
            'name' : 'SEQ',
            'padding' : 4,
            'number_increment' : 1,
        })

        self.hr_employee_john = self.env['hr.employee'].create({
            'address_home_id': self.ref('base.res_partner_address_2'),
            'address_id': self.ref('base.res_partner_address_27'),
            'birthday': '1984-05-01',
            'children': 0.0,
            'country_id': self.ref('base.in'),
            'department_id': self.ref('hr.dep_rd'),
            'gender': 'male',
            'marital': 'single',
            'name': 'John',
            'bank_account_id': self.res_partner_bank.bank_id.id,
        })

        self.hr_employee_mark = self.env['hr.employee'].create({
            'address_home_id': self.ref('base.res_partner_address_2'),
            'address_id': self.ref('base.res_partner_address_27'),
            'birthday': '1984-05-01',
            'children': 0.0,
            'country_id': self.ref('base.in'),
            'department_id': self.ref('hr.dep_rd'),
            'gender': 'male',
            'marital': 'single',
            'name': 'Mark',
            'bank_account_id': self.res_partner_bank.bank_id.id,
        })

        self.account_journal = self.env['account.journal'].create({
            'name' : 'MISC',
            'code' : 'MSC',
            'type' : 'general',
            'sequence_id' : self.ir_sequence.id,
        })

        self.hr_structure_softwaredeveloper = self.env['hr.payroll.structure'].create({
            'name': 'Salary Structure for Software Developer',
            'rule_ids': [(6, 0, [
                    self.ref('hr_payroll.hr_salary_rule_houserentallowance1'),
                    self.ref('hr_payroll.hr_salary_rule_convanceallowance1'),
                    self.ref('hr_payroll.hr_salary_rule_professionaltax1'),
                    self.ref('hr_payroll.hr_salary_rule_providentfund1'),
                    self.ref('hr_payroll.hr_salary_rule_meal_voucher'),
            ])],
            'journal_id' : self.account_journal.id,
            'type_id': self.env.ref('hr_payroll.structure_type_employee').id,
        })

        self.hr_structure_type = self.env['hr.payroll.structure.type'].create({
            'name': 'Salary Structure Type',
            'struct_ids': [(4, self.hr_structure_softwaredeveloper.id)],
        })

        self.hr_contract_john = self.env['hr.contract'].create({
            'date_end': fields.Date.to_string(datetime.now() + timedelta(days=365)),
            'date_start': date(2010, 1, 1),
            'name': 'Contract for John',
            'wage': 5000.0,
            'employee_id': self.hr_employee_john.id,
            'structure_type_id': self.hr_structure_type.id,
            'state': 'open',
        })

        self.hr_payslip_john = self.env['hr.payslip'].create({
            'employee_id': self.hr_employee_john.id,
            'struct_id' : self.hr_structure_softwaredeveloper.id,
            'contract_id': self.hr_contract_john.id,
            'journal_id': self.account_journal.id,
            'name': 'Test Payslip John',
        })

        self.hr_contract_mark = self.env['hr.contract'].create({
            'date_end': fields.Date.to_string(datetime.now() + timedelta(days=365)),
            'date_start': date(2010, 1, 1),
            'name': 'Contract for Mark',
            'wage': 5000.0,
            'employee_id': self.hr_employee_mark.id,
            'structure_type_id': self.hr_structure_type.id,
            'state': 'open',
        })

        self.hr_payslip_john.date_from = time.strftime('%Y-%m-01')
        # YTI Clean that brol
        self.hr_payslip_john.date_to = str(datetime.now() + relativedelta(months=+1, day=1, days=-1))[:10]

        self.hr_payslip_john._onchange_employee()


        self.payslip_run = self.env['hr.payslip.run'].create({
            'date_start': time.strftime('%Y-%m-01'),
            'date_end': str(datetime.now() + relativedelta(months=+1, day=1, days=-1))[:10],
            'name': 'Payslip for Employee'
        })

    def test_00_hr_payslip_run(self):
        """ Checking the process of payslip run when you create payslip(s) in a payslip run and you validate the payslip run. """

        # I verify the payslip run is in draft state.
        self.assertEqual(self.payslip_run.state, 'draft', 'State not changed!')

        # I create a payslip employee.
        payslip_employee = self.env['hr.payslip.employees'].create({
            'employee_ids': [(4, self.hr_employee_john.id), (4, self.hr_employee_mark.id)]
        })

        # I generate the payslip by clicking on Generate button wizard.
        payslip_employee.with_context(active_id=self.payslip_run.id).compute_sheet()

        # I add the payslip in the payslip run.
        self.payslip_run.slip_ids = payslip_employee.employee_ids.mapped('slip_ids')

        # I verify if the payslip run has payslip(s).
        self.assertTrue(len(self.payslip_run.slip_ids) > 0, 'Payslip(s) not added!')

        # I verify the payslip run is in verify state.
        self.assertEqual(self.payslip_run.state, 'verify', 'State not changed!')

        # I confirm the payslip run.
        self.payslip_run.action_validate()

        # I verify the payslips is in done state.
        for slip in self.payslip_run.slip_ids:
            self.assertEqual(slip.state, 'done', 'State not changed!')

        # I verify the payslip run is in close state.
        self.assertEqual(self.payslip_run.state, 'close', 'State not changed!')

        # I verify that the Accounting Entries are created.
        for slip in self.payslip_run.slip_ids:
            self.assertTrue(slip.move_id, 'Accounting Entries has not been created!')

    def test_01_hr_payslip_run(self):
        """ Checking the process of payslip run when you create payslip in a payslip run and you validate the payslip(s). """

        # I create a payslip employee.
        payslip_employee = self.env['hr.payslip.employees'].create({
            'employee_ids': [(4, self.hr_employee_john.id), (4, self.hr_employee_mark.id)]
        })

        # I generate the payslip by clicking on Generate button wizard.
        payslip_employee.with_context(active_id=self.payslip_run.id).compute_sheet()

        # I add the payslip in the payslip run.
        self.payslip_run.slip_ids = payslip_employee.employee_ids.mapped('slip_ids')

        # I verify if the payslip run has payslip(s).
        self.assertTrue(len(self.payslip_run.slip_ids) > 0, 'Payslip(s) not added!')

        # I verify the payslip run is in verify state.
        self.assertEqual(self.payslip_run.state, 'verify', 'State not changed!')

        # I confirm all payslip(s) in the payslip run.
        self.payslip_run.slip_ids.action_payslip_done()

        # I verify the payslip(s) is in done state.
        for slip in self.payslip_run.slip_ids:
            self.assertEqual(slip.state, 'done', 'State not changed!')

        # I verify the payslip run is in close state.
        self.assertEqual(self.payslip_run.state, 'close', 'State not changed!')

        # I verify that the Accounting Entries are created.
        for slip in self.payslip_run.slip_ids:
            self.assertTrue(slip.move_id, 'Accounting Entries has not been created!')

    def test_02_hr_payslip(self):
        """ Checking the process of payslip run when you create payslip in a payslip run and you cancel the payslip(s). """

        # I create a payslip employee.
        payslip_employee = self.env['hr.payslip.employees'].create({
            'employee_ids': [(4, self.hr_employee_john.id), (4, self.hr_employee_mark.id)]
        })

        # I generate the payslip by clicking on Generate button wizard.
        payslip_employee.with_context(active_id=self.payslip_run.id).compute_sheet()

        # I add the payslip in the payslip run.
        self.payslip_run.slip_ids = payslip_employee.employee_ids.mapped('slip_ids')

        # I verify if the payslip run has payslip(s).
        self.assertTrue(len(self.payslip_run.slip_ids) > 0, 'Payslip(s) not added!')

        # I verify the payslip run is in verify state.
        self.assertEqual(self.payslip_run.state, 'verify', 'State not changed!')

        # I confirm all payslip(s) in the payslip run.
        self.payslip_run.slip_ids.action_payslip_cancel()

        # I verify the payslip(s) is in cancel state.
        for slip in self.payslip_run.slip_ids:
            self.assertEqual(slip.state, 'cancel', 'State not changed!')

        # I verify the payslip run is in close state.
        self.assertEqual(self.payslip_run.state, 'close', 'State not changed!')

        # I verify that the Accounting Entries are not created.
        for slip in self.payslip_run.slip_ids:
            self.assertFalse(slip.move_id, 'Accounting Entries has been created!')

    def test_03_hr_payslip(self):
        """ Checking the process of payslip run when you create payslip in a payslip run and you cancel a payslip and confirm another. """

        # I create a payslip employee.
        payslip_employee = self.env['hr.payslip.employees'].create({
            'employee_ids': [(4, self.hr_employee_john.id), (4, self.hr_employee_mark.id)]
        })

        # I generate the payslip by clicking on Generate button wizard.
        payslip_employee.with_context(active_id=self.payslip_run.id).compute_sheet()

        # I add the payslip in the payslip run.
        self.payslip_run.slip_ids = payslip_employee.employee_ids.mapped('slip_ids')

        # Test only with payslip that were just generated. Remove the payslip from setup
        self.payslip_run.write({'slip_ids': [(3, self.hr_payslip_john.id)]})

        # I verify if the payslip run has payslip(s).
        self.assertTrue(len(self.payslip_run.slip_ids) > 0, 'Payslip(s) not added!')

        # I verify the payslip run is in verify state.
        self.assertEqual(self.payslip_run.state, 'verify', 'State not changed!')

        # I cancel one payslip and confirm another in the payslip run.
        payslip_1 = self.payslip_run.slip_ids[0]
        payslip_2 = self.payslip_run.slip_ids[1]
        payslip_1.action_payslip_cancel()
        payslip_2.action_payslip_done()

        # I verify the payslips' states.
        self.assertEqual(payslip_1.state, 'cancel', 'State not changed!')
        self.assertEqual(payslip_2.state, 'done', 'State not changed!')

        # I verify the payslip run is in close state.
        self.assertEqual(self.payslip_run.state, 'close', 'State not changed!')

        # I verify that the Accounting Entries are created or not.
        self.assertFalse(payslip_1.move_id, 'Accounting Entries has been created!')
        self.assertTrue(payslip_2.move_id, 'Accounting Entries has not been created!')

    def test_04_hr_payslip(self):
        """ Checking the process of payslip run when you create payslip in a payslip run and you cancel a payslip and after you confirm the payslip run. """

        # I create a payslip employee.
        payslip_employee = self.env['hr.payslip.employees'].create({
            'employee_ids': [(4, self.hr_employee_john.id), (4, self.hr_employee_mark.id)]
        })

        # I generate the payslip by clicking on Generate button wizard.
        payslip_employee.with_context(active_id=self.payslip_run.id).compute_sheet()

        # I add the payslip in the payslip run.
        self.payslip_run.slip_ids = payslip_employee.employee_ids.mapped('slip_ids')

        # I verify if the payslip run has payslip(s).
        self.assertTrue(len(self.payslip_run.slip_ids) > 0, 'Payslip(s) not added!')

        # I verify the payslip run is in verify state.
        self.assertEqual(self.payslip_run.state, 'verify', 'State not changed!')

        # Storing the references to slip_ids[0] and slip_ids[1]
        # for later use, because the order of the One2many is not guaranteed
        slip0 = self.payslip_run.slip_ids[0]
        slip1 = self.payslip_run.slip_ids[1]

        # I cancel one payslip and after i confirm the payslip run.
        slip0.action_payslip_cancel()
        self.payslip_run.action_validate()

        # I verify the payslips' states.
        self.assertEqual(slip0.state, 'cancel', 'State not changed!')
        self.assertEqual(slip1.state, 'done', 'State not changed!')

        # I verify the payslip run is in close state.
        self.assertEqual(self.payslip_run.state, 'close', 'State not changed!')

        # I verify that the Accounting Entries are created or not.
        self.assertFalse(slip0.move_id, 'Accounting Entries has been created!')
        self.assertTrue(slip1.move_id, 'Accounting Entries has not been created!')

    def test_05_hr_payslip(self):
        """ Checking the process of payslip run when you create payslip run from a payslip and you validate it. """

        # I verify if the payslip has not already a payslip run.
        self.assertFalse(self.hr_payslip_john.payslip_run_id, 'There is already a payslip run!')

        # I create and i add the payslip run to the payslip.
        self.hr_payslip_john.payslip_run_id = self.env['hr.payslip.run'].create({
            'date_end': '2011-09-30',
            'date_start': '2011-09-01',
            'name': 'Payslip for Employee'
        })

        # I validate the payslip.
        self.hr_payslip_john.action_payslip_done()

        # I verify the payslip is in done state.
        self.assertEqual(self.hr_payslip_john.state, 'done', 'State not changed!')

        # I verify the payslip run is in close state.
        self.assertEqual(self.hr_payslip_john.payslip_run_id.state, 'close', 'State not changed!')

        # I verify that the Accounting Entry is created.
        self.assertTrue(self.hr_payslip_john.move_id, 'Accounting entry has not been created!')

    def test_06_hr_payslip(self):
        """ Checking the process of payslip run when you create payslip run from a payslip and you validate the payslip run.  """

        # I verify if the payslip has not already a payslip run.
        self.assertFalse(self.hr_payslip_john.payslip_run_id, 'There is already a payslip run!')

        # I create and i add the payslip run to the payslip.
        self.hr_payslip_john.payslip_run_id = self.env['hr.payslip.run'].create({
            'date_end': '2011-09-30',
            'date_start': '2011-09-01',
            'name': 'Payslip for Employee'
        })

        # I validate the payslip run.
        self.hr_payslip_john.payslip_run_id.action_validate()

        # I verify the payslip is in done state.
        self.assertEqual(self.hr_payslip_john.state, 'done', 'State not changed!')

        # I verify the payslip run is in close state.
        self.assertEqual(self.hr_payslip_john.payslip_run_id.state, 'close', 'State not changed!')

        # I verify that the Accounting Entry is created.
        self.assertTrue(self.hr_payslip_john.move_id, 'Accounting entry has not been created!')

    def test_07_hr_payslip(self):
        """ Checking the process of payslip run when you create payslip run from a payslip and you cancel it.  """

        # I verify if the payslip has not already a payslip run.
        self.assertFalse(self.hr_payslip_john.payslip_run_id, 'There is already a payslip run!')

        # I create and i add the payslip run to the payslip.
        self.hr_payslip_john.payslip_run_id = self.env['hr.payslip.run'].create({
            'date_end': '2011-09-30',
            'date_start': '2011-09-01',
            'name': 'Payslip for Employee'
        })

        # I cancel the payslip.
        self.hr_payslip_john.action_payslip_cancel()

        # I verify the payslip is in cancel state.
        self.assertEqual(self.hr_payslip_john.state, 'cancel', 'State not changed!')

        # I verify the payslip run is in close state.
        self.assertEqual(self.hr_payslip_john.payslip_run_id.state, 'close', 'State not changed!')

        # I verify that the Accounting Entry is not created.
        self.assertFalse(self.hr_payslip_john.move_id, 'Accounting entry has been created!')

    def test_08_hr_payslip(self):
        """ Checking the process of a payslip when you validate it and it has not a payslip run.  """

        # I verify if the payslip has not already a payslip run.
        self.assertFalse(self.hr_payslip_john.payslip_run_id, 'There is already a payslip run!')

        # I validate the payslip.
        self.hr_payslip_john.action_payslip_done()

        # I verify the payslip is in done state.
        self.assertEqual(self.hr_payslip_john.state, 'done', 'State not changed!')

        # I verify that the Accounting Entry is created.
        self.assertTrue(self.hr_payslip_john.move_id, 'Accounting entry has not been created!')
