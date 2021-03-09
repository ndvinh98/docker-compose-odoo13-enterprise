# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayroll28145Wizard(models.TransientModel):
    _name = 'hr.payroll.281.45.wizard'
    _description = 'HR Payroll 281.45 Wizard'

    @api.model
    def default_get(self, field_list=None):
        if self.env.company.country_id != self.env.ref('base.be'):
            raise UserError(_('You must be logged in a Belgian company to use this feature'))
        return super().default_get(field_list)

    year = fields.Integer(default=lambda self: date.today().year)

    def action_generate_file_281_45(self):
        employees = self.env['hr.employee'].browse(self.env.context.get('active_ids'))
        self._check_valid_281_45_configuration(employees)
        # Each fiche has a number (starting at 1).
        # Order employees as follows:
        # 1. Resident in Belgium
        #   > Ordered by zip code (smallest first)
        #       >> Ordered by alphabetical order for same zip
        # 2. Not resident in Belgium
        #   > Ordered by country (alhpa. order)
        #       >> Ordered by alphabetical order for same country
        be = self.env.ref('base.be')
        be_employees = employees.filtered(lambda e: e.address_home_id.country_id == be)
        foreign_employees = employees - be_employees

        be_employees = be_employees.sorted(key=lambda e: e.name)
        be_employees = be_employees.sorted(key=lambda e: e.address_home_id.zip)
        foreign_employees = foreign_employees.sorted(key=lambda e: e.name)
        foreign_employees = foreign_employees.sorted(key=lambda e: e.address_home_id.country_id.name)
        employees = be_employees + foreign_employees

        employees_data = self._get_employee_281_45_values(employees, self.year)

        for employee in employees:
            filename = '281.45-%s.pdf' % employee.name
            data = dict(employees_data[employee], employee=employee)
            pdf, ext = self.env.ref('l10n_be_hr_payroll.action_report_employee_281_45').render_qweb_pdf(employee.ids, data)
            employee.message_post(body=_("The 281.45 sheet has been generated"), attachments=[(filename, pdf)])

    @api.model
    def _get_employee_281_45_values(self, employees, year):
        data = {}
        start = date(self.year, 1, 1)
        end = date(self.year, 12, 31)
        payslips = self.env['hr.payslip'].search([
            ('employee_id', 'in', employees.ids),
            ('date_from', '>=', start),
            ('date_to', '<=', end),
            ('state', '=', 'done'),
        ])
        payslips_by_employees = defaultdict(lambda: self.env['hr.payslip'])
        for payslip in payslips:
            payslips_by_employees[payslip.employee_id] |= payslip

        ip_deduction_bracket_1 = self.env['hr.rule.parameter']._get_parameter_from_code('ip_deduction_bracket_1', start)
        ip_deduction_bracket_2 = self.env['hr.rule.parameter']._get_parameter_from_code('ip_deduction_bracket_2', start)

        sequence = 1
        for employee in employees:
            gross_amount = payslips_by_employees[employee]._get_salary_line_total('IP')
            lump_sum_deduction = min(gross_amount, ip_deduction_bracket_1) * 0.5
            if gross_amount > ip_deduction_bracket_1:
                lump_sum_deduction += min(gross_amount - lump_sum_deduction, ip_deduction_bracket_2) * 0.25

            data[employee] = {
                'year': self.year,
                'sequence': sequence,
                'gross_amout': gross_amount,
                'real_deduction': 0,
                'lump_sum_deduction': lump_sum_deduction,
                'onss_amount': - payslips_by_employees[employee]._get_salary_line_total('IP.DED'),
            }
            sequence += 1
        return data

    @api.model
    def _check_valid_281_45_configuration(self, employees):
        if not all(emp.company_id and emp.company_id.street and emp.company_id.zip and emp.company_id.city and emp.company_id.company_registry for emp in employees):
            raise UserError(_("The company is not correctly configured on your employees. Please be sure that the following pieces of information are set: street, zip, city and registration number"))

        if not all(emp.address_home_id and emp.address_home_id.street and emp.address_home_id.zip and emp.address_home_id.city for emp in employees):
            raise UserError(_('Some employee home address is missing or not completed!'))

        if not all(emp.contract_ids and emp.contract_id for emp in employees):
            raise UserError(_('Some employee has no contract.'))

        if not all(emp.identification_id for emp in employees):
            raise UserError(_('Some employee has no identification id.'))

        if not all(emp.language_code for emp in employees):
            raise UserError(_('Some employee has no language.'))
