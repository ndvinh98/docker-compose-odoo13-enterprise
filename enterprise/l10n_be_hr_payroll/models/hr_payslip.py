#-*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields
from dateutil.relativedelta import relativedelta, MO, SU
from dateutil import rrule
from collections import defaultdict
from datetime import date
from odoo.tools import float_round


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    meal_voucher_count = fields.Integer(string='Meal Vouchers', compute='_compute_meal_voucher_count')
    has_attachment_salary = fields.Boolean(compute='_compute_has_attachment_salary', store=True)

    @api.onchange('employee_id', 'struct_id', 'contract_id', 'date_from', 'date_to')
    def _onchange_employee(self):
        res = super()._onchange_employee()
        attachment_types = {
            'attachment_salary': self.env.ref('l10n_be_hr_payroll.cp200_other_input_attachment_salary').id,
            'assignment_salary': self.env.ref('l10n_be_hr_payroll.cp200_other_input_assignment_salary').id,
            'child_support': self.env.ref('l10n_be_hr_payroll.cp200_other_input_child_support').id,
        }
        if not self.contract_id:
            lines_to_remove = self.input_line_ids.filtered(lambda x: x.input_type_id.id in attachment_types.values())
            self.update({'input_line_ids': [(3, line.id, False) for line in lines_to_remove]})
        if self.has_attachment_salary:
            lines_to_keep = self.input_line_ids.filtered(lambda x: x.input_type_id.id not in attachment_types.values())
            input_line_vals = [(5, 0, 0)] + [(4, line.id, False) for line in lines_to_keep]

            valid_attachments = self.contract_id.attachment_salary_ids.filtered(
                lambda a: a.date_from <= self.date_to and a.date_to >= self.date_from)

            for garnished_type in list(set(valid_attachments.mapped('garnished_type'))):
                amount = sum(valid_attachments.filtered(lambda a: a.garnished_type == garnished_type).mapped('amount'))
                input_type_id = attachment_types[garnished_type]
                input_line_vals.append((0, 0, {
                    'amount': amount,
                    'input_type_id': input_type_id,
                }))
            self.update({'input_line_ids': input_line_vals})
        return res

    @api.depends(
        'contract_id.attachment_salary_ids.date_from', 'contract_id.attachment_salary_ids.date_from',
        'date_from', 'date_to')
    def _compute_has_attachment_salary(self):
        for payslip in self:
            payslip.has_attachment_salary = any(
                a.date_from <= payslip.date_to and
                a.date_to >= payslip.date_from for a in payslip.contract_id.attachment_salary_ids)

    def _get_atn_remuneration(self):
        lines = self.line_ids.filtered(lambda line: 'ATN' in line.code and line.total > 0)
        return sum(line.total for line in lines)

    def _compute_meal_voucher_count(self):
        if self.env.context.get('salary_simulation'):
            for payslip in self:
                payslip.meal_voucher_count = 20
        else:
            vouchers = self.env['l10n_be.meal.voucher.report'].search([
                ('employee_id', 'in', self.mapped('employee_id').ids),
                ('day', '<=', max(self.mapped('date_to'))),
                ('day', '>=', min(self.mapped('date_from')))])
            for payslip in self:
                payslip.meal_voucher_count = len(vouchers.filtered(
                    lambda v: payslip.date_from <= v.day <= payslip.date_to and payslip.employee_id == v.employee_id))

    def _get_base_local_dict(self):
        res = super()._get_base_local_dict()
        res.update({
            'compute_ip': compute_ip,
            'compute_ip_deduction': compute_ip_deduction,
            'compute_withholding_taxes': compute_withholding_taxes,
            'compute_employment_bonus_employees': compute_employment_bonus_employees,
            'compute_special_social_cotisations': compute_special_social_cotisations,
            'compute_double_holiday_withholding_taxes': compute_double_holiday_withholding_taxes,
            'compute_thirteen_month_withholding_taxes': compute_thirteen_month_withholding_taxes,
            'compute_withholding_reduction': compute_withholding_reduction,
        })
        return res

    def _get_paid_amount_13th_month(self):
        # Counts the number of fully worked month
        # If any day in the month is not covered by the contract dates coverage
        # the entire month is not taken into account for the proratization
        contracts = self.employee_id.contract_ids.filtered(lambda c: c.state not in ['draft', 'cancel'] and c.structure_type_id == self.struct_id.type_id)
        if not contracts:
            return 0.0

        year = self.date_to.year

        # 1. Number of months
        invalid_days_by_months = defaultdict(dict)
        for day in rrule.rrule(rrule.DAILY, dtstart=date(year, 1, 1), until=date(year, 12, 31)):
            invalid_days_by_months[day.month][day.date()] = True

        for contract in contracts:
            work_days = {int(d) for d in contract.resource_calendar_id._get_global_attendances().mapped('dayofweek')}

            previous_week_start = max(contract.date_start + relativedelta(weeks=-1, weekday=MO(-1)), date(year, 1, 1))
            next_week_end = min(contract.date_end + relativedelta(weeks=+1, weekday=SU(+1)) if contract.date_end else date.max, date(year, 12, 31))
            days_to_check = rrule.rrule(rrule.DAILY, dtstart=previous_week_start, until=next_week_end)
            for day in days_to_check:
                day = day.date()
                out_of_schedule = True
                if contract.date_start <= day <= (contract.date_end or date.max):
                    out_of_schedule = False
                elif day.weekday() not in work_days:
                    out_of_schedule = False
                invalid_days_by_months[day.month][day] &= out_of_schedule

        complete_months = [
            month
            for month, days in invalid_days_by_months.items()
            if not any(days.values())
        ]
        n_months = len(complete_months)
        if n_months < 6:
            return 0

        # 2. Deduct absences
        unpaid_work_entry_types = self.struct_id.unpaid_work_entry_type_ids
        paid_work_entry_types = self.env['hr.work.entry.type'].search([]) - unpaid_work_entry_types
        hours = contracts._get_work_hours(date(year, 1, 1), date(year, 12, 31))
        paid_hours = sum(v for k, v in hours.items() if k in paid_work_entry_types.ids)
        unpaid_hours = sum(v for k, v in hours.items() if k in unpaid_work_entry_types.ids)

        presence_prorata = paid_hours / (paid_hours + unpaid_hours) if paid_hours or unpaid_hours else 0
        basic = self.contract_id.wage_with_holidays
        return basic * n_months / 12 * presence_prorata

    def _get_contract_wage(self):
        self.ensure_one()
        if self.struct_id.country_id == self.env.ref('base.be'):
            return self.contract_id.wage_with_holidays
        return super()._get_contract_wage()

    def _get_paid_amount(self):
        self.ensure_one()
        if self.struct_id.country_id == self.env.ref('base.be'):
            struct_13th_month = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_thirteen_month')
            if self.struct_id == struct_13th_month:
                return self._get_paid_amount_13th_month()
            if self.worked_days_line_ids:
                ratio = self._get_paid_unpaid_ratio()
                return self.contract_id.wage_with_holidays * ratio
        return super()._get_paid_amount()

    def _get_paid_unpaid_ratio(self):
        if self.env.context.get('salary_simulation'):
            return 1

        self.ensure_one()
        contract = self.contract_id
        hours_per_day = (self.contract_id.resource_calendar_id or self.employee_id.resource_calendar_id).hours_per_day
        mapped_data = contract._get_work_hours(self.date_from, self.date_to)
        unpaid_work_entry_types = self.struct_id.unpaid_work_entry_type_ids
        unpaid_hours = sum(mapped_data.get(entry_type.id, 0) for entry_type in unpaid_work_entry_types)
        unpaid_days = unpaid_hours / hours_per_day
        paid_work_entry_types = self.env['hr.work.entry.type'].search([]) - unpaid_work_entry_types
        paid_hours = sum(mapped_data.get(entry_type.id, 0) for entry_type in paid_work_entry_types)
        paid_days = paid_hours / hours_per_day
        return paid_days / (paid_days + unpaid_days)

def compute_withholding_taxes(payslip, categories, worked_days, inputs):

    def compute_basic_bareme(value):
        rates = payslip.rule_parameter('basic_bareme_rates')
        rates = [(limit or float('inf'), rate) for limit, rate in rates]  # float('inf') because limit equals None for last level
        rates = sorted(rates)

        basic_bareme = 0
        previous_limit = 0
        for limit, rate in rates:
            basic_bareme += max(min(value, limit) - previous_limit, 0) * rate
            previous_limit = limit
        return float_round(basic_bareme, precision_rounding=0.01)

    def convert_to_month(value):
        return float_round(value / 12.0, precision_rounding=0.01, rounding_method='DOWN')

    employee = payslip.contract_id.employee_id
    # PART 1: Withholding tax amount computation
    withholding_tax_amount = 0.0
    lower_bound = categories.GROSS - categories.GROSS % 15

    # yearly_gross_revenue = Revenu Annuel Brut
    yearly_gross_revenue = lower_bound * 12.0

    # yearly_net_taxable_amount = Revenu Annuel Net Imposable
    if yearly_gross_revenue <= payslip.rule_parameter('yearly_gross_revenue_bound_expense'):
        yearly_net_taxable_revenue = yearly_gross_revenue * (1.0 - 0.3)
    else:
        yearly_net_taxable_revenue = yearly_gross_revenue - payslip.rule_parameter('expense_deduction')

    # BAREME III: Non resident
    if employee.resident_bool:
        basic_bareme = compute_basic_bareme(yearly_net_taxable_revenue)
        withholding_tax_amount = convert_to_month(basic_bareme)
    else:
        # BAREME I: Isolated or spouse with income
        if employee.marital in ['divorced', 'single', 'widower'] or (employee.marital in ['married', 'cohabitant'] and employee.spouse_fiscal_status == 'with income'):
            basic_bareme = max(compute_basic_bareme(yearly_net_taxable_revenue) - payslip.rule_parameter('deduct_single_with_income'), 0.0)
            withholding_tax_amount = convert_to_month(basic_bareme)

        # BAREME II: spouse without income
        if employee.marital in ['married', 'cohabitant'] and employee.spouse_fiscal_status == 'without income':
            yearly_net_taxable_revenue_for_spouse = min(yearly_net_taxable_revenue * 0.3, payslip.rule_parameter('max_spouse_income'))
            basic_bareme_1 = compute_basic_bareme(yearly_net_taxable_revenue_for_spouse)
            basic_bareme_2 = compute_basic_bareme(yearly_net_taxable_revenue - yearly_net_taxable_revenue_for_spouse)
            withholding_tax_amount = convert_to_month(max(basic_bareme_1 + basic_bareme_2 - 2 * payslip.rule_parameter('deduct_single_with_income'), 0))

    # Reduction for isolated people and for other family charges
    if employee.marital in ['divorced', 'single', 'widower'] or (employee.spouse_net_revenue > 0.0 or employee.spouse_other_net_revenue > 0.0):
        if employee.marital in ['divorced', 'single', 'widower']:
            withholding_tax_amount -= payslip.rule_parameter('isolated_deduction')
        if employee.marital == 'widower' or (employee.marital in ['divorced', 'single', 'widower'] and employee.dependent_children):
            withholding_tax_amount -= payslip.rule_parameter('disabled_dependent_deduction')
        if employee.disabled:
            withholding_tax_amount -= payslip.rule_parameter('disabled_dependent_deduction')
        if employee.other_dependent_people and employee.dependent_seniors:
            withholding_tax_amount -= payslip.rule_parameter('dependent_senior_deduction') * employee.dependent_seniors
        if employee.other_dependent_people and employee.dependent_juniors:
            withholding_tax_amount -= payslip.rule_parameter('disabled_dependent_deduction') * employee.dependent_juniors
        if employee.marital in ['married', 'cohabitant'] and employee.spouse_fiscal_status=='with income' and employee.spouse_net_revenue <= payslip.rule_parameter('spouse_low_income_limit'):
            withholding_tax_amount -= payslip.rule_parameter('spouse_low_income_deduction')
        if employee.marital in ['married', 'cohabitant'] and employee.spouse_fiscal_status=='with income' and not employee.spouse_net_revenue and employee.spouse_other_net_revenue <= payslip.rule_parameter('spouse_other_income_limit'):
            withholding_tax_amount -= payslip.rule_parameter('spouse_other_income_deduction')
    if employee.marital in ['married', 'cohabitant'] and employee.spouse_net_revenue == 0.0 and employee.spouse_other_net_revenue == 0.0:
        if employee.disabled:
            withholding_tax_amount -= payslip.rule_parameter('disabled_dependent_deduction')
        if employee.disabled_spouse_bool:
            withholding_tax_amount -= payslip.rule_parameter('disabled_dependent_deduction')
        if employee.other_dependent_people and employee.dependent_seniors:
            withholding_tax_amount -= payslip.rule_parameter('dependent_senior_deduction') * employee.dependent_seniors
        if employee.other_dependent_people and employee.dependent_juniors:
            withholding_tax_amount -= payslip.rule_parameter('disabled_dependent_deduction') * employee.dependent_juniors

    # Child Allowances
    n_children = employee.dependent_children
    if n_children > 0:
        children_deduction = payslip.rule_parameter('dependent_basic_children_deduction')
        if n_children <= 8:
            withholding_tax_amount -= children_deduction.get(n_children, 0.0)
        if n_children > 8:
            withholding_tax_amount -= children_deduction.get(8, 0.0) + (n_children - 8) * payslip.rule_parameter('dependent_children_deduction')

    if payslip.contract_id.fiscal_voluntarism:
        voluntary_amount = categories.GROSS * payslip.contract_id.fiscal_voluntary_rate / 100
        if voluntary_amount > withholding_tax_amount:
            withholding_tax_amount = voluntary_amount

    return - max(withholding_tax_amount, 0.0)

def compute_special_social_cotisations(payslip, categories, worked_days, inputs):
    employee = payslip.contract_id.employee_id
    wage = categories.BASIC
    if employee.resident_bool:
        result = 0.0
    elif employee.marital in ['divorced', 'single', 'widower'] or (employee.marital in ['married', 'cohabitant'] and employee.spouse_fiscal_status=='without income'):
        if 0.01 <= wage <= 1095.09:
            result = 0.0
        elif 1095.10 <= wage <= 1945.38:
            result = 0.0
        elif 1945.39 <= wage <= 2190.18:
            result = -min((wage - 1945.38) * 0.076, 18.60)
        elif 2190.19 <= wage <= 6038.82:
            result = -min(18.60 + (wage - 2190.18) * 0.011, 60.94)
        else:
            result = -60.94
    elif employee.marital in ['married', 'cohabitant'] and employee.spouse_fiscal_status=='with income':
        if 0.01 <= wage <= 1095.09:
            result = 0.0
        elif 1095.10 <= wage <= 1945.38:
            result = -9.30
        elif 1945.39 <= wage <= 2190.18:
            result = -min(max((wage - 1945.38) * 0.076, 9.30), 18.60)
        elif 2190.19 <= wage <= 6038.82:
            result = -min(18.60 + (wage - 2190.18) * 0.011, 51.64)
        else:
            result = -51.64
    return result

def compute_ip(payslip, categories, worked_days, inputs):
    contract = payslip.contract_id
    basic_ip = contract.wage_with_holidays * contract.ip_wage_rate / 100.0
    ratio = payslip.dict._get_paid_unpaid_ratio()
    return basic_ip * ratio

def compute_ip_deduction(payslip, categories, worked_days, inputs):
    tax_rate = 0.15
    ip_amount = compute_ip(payslip, categories, worked_days, inputs) + categories.ONSS * payslip.contract_id.ip_wage_rate / 100.0
    ip_deduction_bracket_1 = payslip.rule_parameter('ip_deduction_bracket_1')
    ip_deduction_bracket_2 = payslip.rule_parameter('ip_deduction_bracket_2')
    if 0.0 <= ip_amount <= ip_deduction_bracket_1:
        tax_rate = tax_rate / 2.0
    elif ip_deduction_bracket_1 < ip_amount <= ip_deduction_bracket_2:
        tax_rate = tax_rate * 3.0 / 4.0
    return - min(ip_amount * tax_rate, 11745)

# ref: https://www.socialsecurity.be/employer/instructions/dmfa/fr/latest/instructions/deductions/workers_reductions/workbonus.html
def compute_employment_bonus_employees(payslip, categories, worked_days, inputs):
    bonus_basic_amount = payslip.rule_parameter('work_bonus_basic_amount')
    wage_lower_bound = payslip.rule_parameter('work_bonus_reference_wage_low')
    ratio = 1

    if payslip.worked_days_line_ids:
        rc = payslip.contract_id.resource_calendar_id
        worked_hours = sum(payslip.worked_days_line_ids.mapped('number_of_hours'))
        full_time_hours = sum(payslip.worked_days_line_ids.mapped('number_of_days')) * rc.full_time_required_hours / (rc.full_time_required_hours / rc.hours_per_day)
        ratio = worked_hours / full_time_hours

    salary = categories.BRUT * ratio

    if salary <= wage_lower_bound:
        result = bonus_basic_amount
    elif salary <= payslip.rule_parameter('work_bonus_reference_wage_high'):
        coeff = payslip.rule_parameter('work_bonus_coeff')
        result = bonus_basic_amount - (coeff * (salary - wage_lower_bound))
    return min(result, -categories.ONSS) * ratio

def compute_double_holiday_withholding_taxes(payslip, categories, worked_days, inputs):
    rates = [
        (8460.0, 0), (10830.0, 0.1917),
        (13775.0, 0.2120), (16520.0, 0.2625),
        (18690.0, 0.3130), (20870.0, 0.3433),
        (25230.0, 0.3634), (27450.0, 0.3937),
        (36360.0, 0.4239), (47480.0, 0.4744)]

    employee = payslip.contract_id.employee_id
    def find_rates(x):
        for a, b in rates:
            if x <= a:
                return b
        return 0.535

    # Up to 12 children
    children_exoneration = [0.0, 13329.0, 16680.0, 21820.0, 27560.0, 33300.0, 39040.0, 44780.0, 50520.0, 56260.0, 62000.0, 67740.0, 73480.0]
    # Only if no more than 5 children
    children_reduction = [(0, 0), (22940.0, 0.075), (22940.0, 0.2), (25235.0, 0.35), (29825.0, 0.55), (32120.0, 0.75)]

    n = employee.dependent_children
    yearly_revenue = categories.GROSS * 12.0

    if 0 < n < 13 and yearly_revenue <= children_exoneration[n]:
        yearly_revenue = yearly_revenue - (children_exoneration[n] - yearly_revenue)

    if n <= 5 and yearly_revenue <= children_reduction[n][0]:
        withholding_tax_amount = yearly_revenue * find_rates(yearly_revenue) * (1 - children_reduction[n][1])
    else:
        withholding_tax_amount = yearly_revenue * find_rates(yearly_revenue)
    return -withholding_tax_amount / 12.0

def compute_thirteen_month_withholding_taxes(payslip, categories, worked_days, inputs):
    employee = payslip.contract_id.employee_id
    rates = [
        (8460.0, 0), (10830.0, 0.2322),
        (13775.0, 0.2523), (16520.0, 0.3028),
        (18690.0, 0.2533), (20870.0, 0.3836),
        (25230.0, 0.4038), (27450.0, 0.4341),
        (36360.0, 0.4644), (47480.0, 0.5148)]

    def find_rates(x):
        for a, b in rates:
            if x <= a:
                return b
        return 0.535

    # Up to 12 children
    children_exoneration = [0.0, 13329.0, 16680.0, 21820.0, 27560.0, 33300.0, 39040.0, 44780.0, 50520.0, 56260.0, 62000.0, 67740.0, 73480.0]
    # Only if no more than 5 children
    children_reduction = [(0, 0), (22940.0, 0.075), (22940.0, 0.2), (25235.0, 0.35), (29825.0, 0.55), (32120.0, 0.75)]

    n = employee.dependent_children
    yearly_revenue = categories.GROSS * 12.0

    if 0 < n < 13 and yearly_revenue <= children_exoneration[n]:
        yearly_revenue = yearly_revenue - (children_exoneration[n] - yearly_revenue)

    if n <= 5 and yearly_revenue <= children_reduction[n][0]:
        withholding_tax_amount = yearly_revenue * find_rates(yearly_revenue) * (1 - children_reduction[n][1])
    else:
        withholding_tax_amount = yearly_revenue * find_rates(yearly_revenue)
    return -withholding_tax_amount / 12.0

def compute_withholding_reduction(payslip, categories, worked_days, inputs):
    if categories.EmpBonus:
        return min(abs(categories.PP), categories.EmpBonus * 0.3314)
    return 0.0
