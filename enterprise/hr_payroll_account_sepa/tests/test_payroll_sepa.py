# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from datetime import datetime, timedelta
from lxml import etree

from odoo.fields import Date
from odoo.modules.module import get_module_resource
from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestPayrollSEPACreditTransfer(common.TransactionCase):

    def setUp(self):
        super(TestPayrollSEPACreditTransfer, self).setUp()

        self.partner_john = self.env['res.partner'].create({
            'name': 'John Dex',
        })

        self.res_partner_bank = self.env['res.partner.bank'].create({
            'acc_number': 'BE32707171912447',
            'partner_id': self.partner_john.id,
            'acc_type': 'bank',
            'bank_id': self.ref('base.bank_bnp'),
        })

        self.ir_sequence = self.env['ir.sequence'].create({
            'name' : 'SEQ',
            'padding' : 4,
            'number_increment' : 1,
        })

        self.bank_partner = self.env['res.partner.bank'].create({
            'acc_number' : 'BE84567968814145',
            'acc_type': 'iban',
            'partner_id': self.env.ref('base.main_company').partner_id.id,
        })

        self.bank = self.env['res.bank'].create({
            'name':'BNP',
            'bic': 'GEBABEBB',
        })

        self.hr_employee_john = self.env['hr.employee'].create({
            'address_home_id': self.partner_john.id,
            'birthday': '1984-05-01',
            'children': 0.0,
            'country_id': self.ref('base.in'),
            'department_id': self.ref('hr.dep_rd'),
            'gender': 'male',
            'marital': 'single',
            'name': 'John',
            'bank_account_id': self.res_partner_bank.id,
        })

        self.account_journal = self.env['account.journal'].create({
            'name' : 'MISC',
            'code' : 'MSC',
            'type' : 'general',
            'sequence_id' : self.ir_sequence.id,
        })

        self.bank_journal = self.env['account.journal'].create({
            'name' : 'Bank',
            'code' : 'BNK',
            'type' : 'bank',
            'sequence_id' : self.ir_sequence.id,
            'bank_id' : self.bank.id,
            'bank_account_id': self.bank_partner.id,
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
            'date_end': Date.to_string(datetime.now() + timedelta(days=365)),
            'date_start': Date.today(),
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
        self.hr_payslip_john.compute_sheet()

        self.payslip_run = self.env['hr.payslip.run'].create({
            'date_end': '2011-09-30',
            'date_start': '2011-09-01',
            'name': 'Payslip for Employee'
        })

        # Get a pain.001.001.03 schema validator
        schema_file_path = get_module_resource('account_sepa', 'schemas', 'pain.001.001.03.xsd')
        self.xmlschema = etree.XMLSchema(etree.parse(open(schema_file_path)))

    def test_00_hr_payroll_account_sepa(self):
        """ Checking the process of payslip when you create a SEPA payment. """

        # I verify if the payslip has not already a payslip run.
        self.assertFalse(self.hr_payslip_john.payslip_run_id, 'There is already a payslip run!')

        # I validate the payslip.
        self.hr_payslip_john.action_payslip_done()

        # I verify the payslip is in done state.
        self.assertEqual(self.hr_payslip_john.state, 'done', 'State not changed!')

        # I make the SEPA payment.
        self.hr_payslip_john._create_xml_file(self.bank_journal)

        # I verify if a file is created.
        self.assertTrue(self.hr_payslip_john.sepa_export, 'SEPA payment has not been created!')

        # I verify the xml.
        sct_doc = etree.fromstring(base64.b64decode(self.hr_payslip_john.sepa_export))
        self.assertTrue(self.xmlschema.validate(sct_doc), self.xmlschema.error_log.last_error)

        # I verify the payslip is in paid state.
        self.assertEqual(self.hr_payslip_john.state, 'paid', 'State not changed!')

    def test_01_hr_payroll_account_sepa(self):
        """ Checking the process of payslip run when you create a SEPA payment. """

        # I verify the payslip run is in draft state.
        self.assertEqual(self.payslip_run.state, 'draft', 'State not changed!')

        # I create a payslip employee.
        payslip_employee = self.env['hr.payslip.employees'].create({
            'employee_ids': [(4, self.hr_employee_john.id)]
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

        # I verify the payslip run is in close state.
        self.assertEqual(self.payslip_run.state, 'close', 'State not changed!')

        # I make the SEPA payment.
        self.payslip_run.mapped('slip_ids')._create_xml_file(self.bank_journal)

        # I verify if a file is created for the payslip run.
        self.assertTrue(self.payslip_run.sepa_export, 'SEPA payment has not been created!')

        # I verify the xml.
        sct_doc = etree.fromstring(base64.b64decode(self.payslip_run.sepa_export))
        self.assertTrue(self.xmlschema.validate(sct_doc), self.xmlschema.error_log.last_error)

        # I verify the payslip is in paid state.
        self.assertEqual(self.payslip_run.state, 'paid', 'State not changed!')
