# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import re
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from datetime import date
from lxml import etree

from odoo import api, fields, models, _
from odoo.tools import date_utils
from odoo.exceptions import ValidationError
from odoo.modules.module import get_resource_path


def format_amount(amount, width=11, hundredth=True):
    """
    Fill a constant 11 characters string with 0
    """
    if hundredth:
        amount *= 100
    return str(int(amount)).zfill(width)


WORKER_CODE = 495  # CP200?


class DMFANode:

    def __init__(self, env, sequence=1):
        self.env = env
        self.sequence = sequence

    @classmethod
    def init_multi(cls, args_list):
        """
        Create multiple instances, each with a consecutive sequence number
        :param args_list: list of __init__ parameters
        :return: list of instances
        """
        sequence = 1
        instances = []
        for args in args_list:
            instances.append(cls(*args, sequence=sequence))
            sequence += 1
        return instances


class DMFANaturalPerson(DMFANode):
    """
    Represents an employee
    """
    def __init__(self, employee, quarter_start, quarter_end, sequence=1):
        super().__init__(employee.env, sequence=sequence)
        self.employee = employee
        if not employee.identification_id:
            raise ValidationError(_("National Number not specified for %s") % employee.name)
        self.identification_id = re.sub('[^0-9]', '', employee.identification_id)
        if len(self.identification_id) != 11:
            raise ValidationError(_("Invalid National Number for %s (It must contains eleven digits)") % employee.name)
        contracts = employee._get_contracts(quarter_start, quarter_end, states=['open', 'pending', 'close'])
        self.worker_records = DMFAWorker.init_multi([(contracts, quarter_start, quarter_end)])


class DMFAWorker(DMFANode):
    """
    Represents the employee contracts
    """
    def __init__(self, contracts, quarter_start, quarter_end, sequence=1):
        super().__init__(contracts.env, sequence=sequence)
        self.frontier_worker = 0  # not supported
        self.worker_code = WORKER_CODE
        self.payslips = self.env['hr.payslip'].search([
            ('contract_id', 'in', contracts.ids),
            ('date_to', '>=', quarter_start),
            ('date_to', '<=', quarter_end),
            ('state', '=', 'done'),
        ])
        self.occupations = self._prepare_occupations(contracts)
        self.deductions = self._prepare_deductions()
        self.contributions = self._prepare_contributions()

    def _prepare_contributions(self):
        lines = self.env['hr.payslip.line']
        contribution_rules = (
            self.env.ref('l10n_be_hr_payroll.cp200_employees_salary_onss_rule'),
            self.env.ref('l10n_be_hr_payroll.cp200_employees_termination_fees_termination_ONSS'),
            self.env.ref('l10n_be_hr_payroll.cp200_employees_termination_n_rules_onss_termination'),
            self.env.ref('l10n_be_hr_payroll.cp200_employees_termination_n1_rules_onss_termination'),
            self.env.ref('l10n_be_hr_payroll.cp200_employees_thirteen_month_onss_rule'),
        )
        for line in self.payslips.mapped('line_ids'):
            if line.salary_rule_id in contribution_rules:
                lines |= line
        return [DMFAWorkerContribution(lines)]

    def _prepare_occupations(self, contracts):
        values = []
        for contract in contracts:
            payslips = self.payslips.filtered(lambda p: p.contract_id == contract)
            values.append((contract, payslips))
        return DMFAOccupation.init_multi(values)

    def _prepare_deductions(self):
        """ Only employement bonus deduction is currently supported """
        employement_bonus_rule = self.env.ref('l10n_be_hr_payroll.cp200_employees_salary_employment_bonus_employees')
        employement_deduction_lines = self.payslips.mapped('line_ids').filtered(lambda l: l.salary_rule_id == employement_bonus_rule)
        if employement_deduction_lines:
            return [DMFAWorkerDeduction(employement_deduction_lines, code=1)]
        return []


class DMFAWorkerContribution(DMFANode):
    """
    Represents the paid amounts on the employee payslips
    """

    def __init__(self, payslip_lines, sequence=None):
        super().__init__(payslip_lines.env, sequence=sequence)
        self.worker_code = WORKER_CODE
        self.contribution_type = 2  # only code for worker 495; see annexe 3
        self.amount = format_amount(- sum(payslip_lines.mapped('total')))


class DMFAOccupation(DMFANode):
    """
    Represents the contract
    """
    def __init__(self, contract, payslips, sequence=1):
        super().__init__(contract.env, sequence=sequence)
        calendar = contract.resource_calendar_id
        self.contract = contract
        self.payslips = payslips
        self.date_start = contract.date_start
        days_per_week = len(set(calendar.mapped('attendance_ids.dayofweek')))
        self.days_per_week = format_amount(days_per_week, width=3)
        self.mean_working_hours = int(days_per_week * calendar.hours_per_day)
        self.is_parttime = 1 if calendar.is_fulltime else 0
        self.commission = 200  # only CP200 currently supported
        self.services = self._prepare_services()
        self.remunerations = self._prepare_remunerations()
        work_address = contract.employee_id.address_id
        if not work_address:
            raise ValidationError(_("%s does not have a working address") % contract.employee_id.name)
        location_unit = self.env['l10n_be.dmfa.location.unit'].search([('partner_id', '=', work_address.id)])
        if not location_unit:
            raise ValidationError(_("Address of %s does not have any ONSS code. Please provide one in the company.") % work_address.name)
        self.work_place = format_amount(location_unit.code, width=10, hundredth=False)

    def _prepare_services(self):
        services_by_type = defaultdict(lambda: self.env['hr.payslip.worked_days'])
        for work_days in self.payslips.mapped('worked_days_line_ids'):
            services_by_type[work_days.code] |= work_days
        return DMFAService.init_multi([(work_days,) for work_days in services_by_type.values()])

    def _prepare_remunerations(self):
        # Please, this should not be hardcoded if we want a decent DMFA support
        regular_gross = self.env.ref('l10n_be_hr_payroll.cp200_employees_salary_gross_salary')
        regular_car = self.env.ref('l10n_be_hr_payroll.cp200_employees_salary_company_car')
        rule_13th_month_gross = self.env.ref('l10n_be_hr_payroll.cp200_employees_thirteen_month_gross_salary')
        termniation_n = self.env.ref('l10n_be_hr_payroll.cp200_employees_termination_n_pay_simple')
        termniation_n1 = self.env.ref('l10n_be_hr_payroll.cp200_employees_termination_n1_pay_simple')
        codes = {
            regular_gross: 1,
            rule_13th_month_gross: 2,
            termniation_n: 7,
            termniation_n1: 7,
            regular_car: 10,
            # Double holidays?
        }
        frequencies = {
            rule_13th_month_gross: 12
        }
        lines_by_code = defaultdict(lambda: self.env['hr.payslip.line'])
        for line in self.payslips.mapped('line_ids'):
            code = codes.get(line.salary_rule_id)
            if code:
                frequency = frequencies.get(line.salary_rule_id)
                lines_by_code[code, frequency] |= line
        return DMFARemuneration.init_multi([(lines, code, frequency) for (code, frequency), lines in lines_by_code.items()])


class DMFARemuneration(DMFANode):
    """
    Represents the paid amounts on payslips
    """
    def __init__(self, payslip_lines, code, frequency=None, sequence=1):
        super().__init__(payslip_lines.env, sequence=sequence)
        self.code = code
        self.frequency = frequency
        self.amount = format_amount(sum(payslip_lines.mapped('total')))


class DMFAService(DMFANode):
    """
    Represents the worked hours/days
    """
    def __init__(self, work_days, sequence=1):
        super().__init__(work_days.env, sequence=sequence)
        if len(work_days.mapped('work_entry_type_id')) > 1:
            raise ValueError("Cannot mix work of different types.")
        work_entry_type = work_days[0].work_entry_type_id
        self.code = work_entry_type.dmfa_code
        if not self.code:
            raise ValidationError(_("Work entry type %s does not have a DMFA code") % work_entry_type.name)
        self.nbr_days = format_amount(sum(work_days.mapped('number_of_days')), width=5)


class DMFAWorkerDeduction(DMFANode):

    def __init__(self, payslip_lines, code, sequence=1):
        super().__init__(payslip_lines.env, sequence=sequence)
        self.code = code
        self.amount = format_amount(sum(payslip_lines.mapped('total')))


class HrDMFAReport(models.Model):
    _name = 'l10n_be.dmfa'
    _description = 'DMFA xml report'
    _order = "year desc, quarter desc"

    name = fields.Char(compute='_compute_name', store=True)
    reference = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    year = fields.Char(required=True, default=lambda self: fields.Date.today().year)
    quarter = fields.Selection([
        ('1', '1st'),
        ('2', '2nd'),
        ('3', '3rd'),
        ('4', '4th'),
    ], required=True, default=lambda self: str(date_utils.get_quarter_number(fields.Date.today())))
    dmfa_xml = fields.Binary(string="XML file")
    dmfa_xml_filename = fields.Char(compute='_compute_filename', store=True)
    quarter_start = fields.Date(compute='_compute_dates')
    quarter_end = fields.Date(compute='_compute_dates')
    validation_state = fields.Selection([
        ('normal', "N/A"),
        ('done', "Valid"),
        ('invalid', "Invalid"),
    ], default='normal', compute='_compute_validation_state', store=True)
    error_message = fields.Char(store=True, compute='_compute_validation_state', help="Technical error message")

    _sql_constraints = [
        ('_unique', 'unique (company_id, year, quarter)', "Only one DMFA per year and per quarter is allowed. Another one already exists."),
    ]

    @api.depends('reference', 'quarter', 'year')
    def _compute_name(self):
        for dmfa in self:
            dmfa.name = _('%s %s quarter %s') % (dmfa.reference, dmfa.quarter, dmfa.year)

    @api.constrains('year')
    def _check_year(self):
        for dmfa in self:
            try:
                int(dmfa.year)
            except ValueError:
                raise ValidationError(_("Field Year does not seem to be a year. It must be an integer."))

    @api.depends('dmfa_xml')
    def _compute_validation_state(self):
        dmfa_schema_file_path = get_resource_path(
            'l10n_be_hr_payroll',
            'data',
            'DmfAOriginal_20191.xsd',
        )
        xsd_root = etree.parse(dmfa_schema_file_path)
        schema = etree.XMLSchema(xsd_root)
        for dmfa in self:
            if not dmfa.dmfa_xml:
                dmfa.validation_state = 'normal'
                dmfa.error_message = False
            else:
                xml_root = etree.fromstring(base64.b64decode(dmfa.dmfa_xml))
                try:
                    schema.assertValid(xml_root)
                    dmfa.validation_state = 'done'
                except etree.DocumentInvalid as err:
                    dmfa.validation_state = 'invalid'
                    dmfa.error_message = str(err)

    @api.depends('dmfa_xml')
    def _compute_filename(self):
        # https://www.socialsecurity.be/site_fr/general/helpcentre/batch/files/directives.htm
        num_expedition = '000000'  # ?
        num_suite = '00001'
        now = fields.Date.today()
        filename = 'FI.DMFA.%s.%s.%s.R.1.1.xml' % (num_expedition, now.strftime('%Y%m%d'), num_suite)
        for dmfa in self:
            dmfa.dmfa_xml_filename = filename

    @api.depends('year', 'quarter')
    def _compute_dates(self):
        for dmfa in self:
            year = int(dmfa.year)
            month = int(dmfa.quarter) * 3
            self.quarter_start, self.quarter_end = date_utils.get_quarter(date(year, month, 1))

    def generate_dmfa_report(self):
        xml_str = self.env.ref('l10n_be_hr_payroll.dmfa_xml_report').render(self._get_rendering_data())

        # Prettify xml string
        root = etree.fromstring(xml_str, parser=etree.XMLParser(remove_blank_text=True))
        xml_formatted_str = etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=True)

        self.dmfa_xml = base64.encodebytes(xml_formatted_str)

    def _get_rendering_data(self):
        contracts = self.env['hr.employee']._get_all_contracts(self.quarter_start, self.quarter_end)
        contracts = contracts.filtered(lambda c: c.company_id == self.company_id)
        employees = contracts.mapped('employee_id')
        payslips = self.env['hr.payslip'].search([
            ('employee_id', 'in', employees.ids),
            ('date_to', '>=', self.quarter_start),
            ('date_to', '<=', self.quarter_end),
            ('state', '=', 'done')
        ])
        if not self.company_id.dmfa_employer_class:
            raise ValidationError(_("Please provide an employer class for company %s. The employer class is given by the ONSS and should be encoded in the Payroll setting.") % self.company_id.name)
        if not self.company_id.onss_registration_number and not self.company_id.onss_company_id:
            raise ValidationError(_("No ONSS registration number nor company ID was found for company %s. Please provide at least one.") % self.company_id.name)
        return {
            'employer_class': self.company_id.dmfa_employer_class,
            'onss_company_id': format_amount(self.company_id.onss_company_id or 0, width=10, hundredth=False),
            'onss_registration_number': format_amount(self.company_id.onss_registration_number or 0, width=9, hundredth=False),
            'quarter_repr': '%s%s' % (self.year, self.quarter),
            'quarter_start': self.quarter_start,
            'quarter_end': self.quarter_end,
            'data': self,
            'global_contribution': format_amount(self._get_global_contribution(payslips)),
            'natural_persons': DMFANaturalPerson.init_multi([(employee, self.quarter_start, self.quarter_end) for employee in employees]),
        }

    def _get_global_contribution(self, payslips):
        """ Some contribution are not specified at the worker level but globally for the whole company """
        onss_double_holidays = self.env.ref('l10n_be_hr_payroll.cp200_employees_double_holiday_onss_rule')
        lines = payslips.mapped('line_ids').filtered(lambda l: l.salary_rule_id == onss_double_holidays)
        return sum(lines.mapped('total'))


class HrDMFALocationUnit(models.Model):
    _name = 'l10n_be.dmfa.location.unit'
    _description = 'Work Place defined by ONSS'
    _rec_name = 'code'

    code = fields.Integer(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    partner_id = fields.Many2one('res.partner', string="Working Address", required=True)

    _sql_constraints = [
        ('_unique', 'unique (company_id, partner_id)', "A DMFA location cannot be set more than once for the same company and partner."),
    ]
