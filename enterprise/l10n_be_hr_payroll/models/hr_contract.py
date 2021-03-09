# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _

from odoo.exceptions import ValidationError

EMPLOYER_ONSS = 0.2714


class HrContract(models.Model):
    _inherit = 'hr.contract'

    transport_mode_car = fields.Boolean('Uses company car')
    transport_mode_private_car = fields.Boolean('Uses private car')
    transport_mode_public = fields.Boolean('Uses public transportation')
    transport_mode_others = fields.Boolean('Uses another transport mode')
    car_atn = fields.Monetary(string='ATN Company Car')
    public_transport_employee_amount = fields.Monetary('Paid by the employee (Monthly)')
    warrant_value_employee = fields.Monetary(compute='_compute_commission_cost', string="Warrant monthly value for the employee")

    # Employer costs fields
    final_yearly_costs = fields.Monetary(compute='_compute_final_yearly_costs',
        readonly=False, store=True,
        string="Employee Budget",
        tracking=True,
        help="Total yearly cost of the employee for the employer.")
    monthly_yearly_costs = fields.Monetary(compute='_compute_monthly_yearly_costs', string='Monthly Equivalent Cost', readonly=True,
        help="Total monthly cost of the employee for the employer.")
    ucm_insurance = fields.Monetary(compute='_compute_ucm_insurance', string="Social Secretary Costs")
    meal_voucher_paid_by_employer = fields.Monetary(compute='_compute_meal_voucher_paid_by_employer', string="Meal Voucher Paid by Employer")
    company_car_total_depreciated_cost = fields.Monetary()
    private_car_reimbursed_amount = fields.Monetary(compute='_compute_private_car_reimbursed_amount')
    km_home_work = fields.Integer(related="employee_id.km_home_work", related_sudo=True, readonly=False)
    public_transport_reimbursed_amount = fields.Monetary(string='Reimbursed amount',
        compute='_compute_public_transport_reimbursed_amount', readonly=False, store=True)
    others_reimbursed_amount = fields.Monetary(string='Other Reimbursed amount')
    transport_employer_cost = fields.Monetary(compute='_compute_transport_employer_cost', string="Employer cost from employee transports")
    warrants_cost = fields.Monetary(compute='_compute_commission_cost', string="Warrant monthly cost for the employer")
    yearly_commission_cost = fields.Monetary(compute='_compute_commission_cost')

    # Advantages
    commission_on_target = fields.Monetary(string="Commission on Target",
        tracking=True,
        help="Monthly gross amount that the employee receives if the target is reached.")
    fuel_card = fields.Monetary(string="Fuel Card",
        tracking=True,
        help="Monthly amount the employee receives on his fuel card.")
    internet = fields.Monetary(string="Internet",
        tracking=True,
        help="The employee's internet subcription will be paid up to this amount.")
    representation_fees = fields.Monetary(string="Representation Fees",
        tracking=True,
        help="Monthly net amount the employee receives to cover his representation fees.")
    mobile = fields.Monetary(string="Mobile",
        tracking=True,
        help="The employee's mobile subscription will be paid up to this amount.")
    meal_voucher_amount = fields.Monetary(string="Meal Vouchers",
        tracking=True,
        help="Amount the employee receives in the form of meal vouchers per worked day.")
    holidays = fields.Float(string='Paid Time Off',
        help="Number of days of paid leaves the employee gets per year.")
    wage_with_holidays = fields.Monetary(compute='_compute_wage_with_holidays', inverse='_inverse_wage_with_holidays',
        tracking=True, string="Wage update with holidays retenues")
    eco_checks = fields.Monetary("Eco Vouchers",
        help="Yearly amount the employee receives in the form of eco vouchers.")
    ip = fields.Boolean(default=False, tracking=True)
    ip_wage_rate = fields.Float(string="IP percentage", help="Should be between 0 and 100 %")
    time_credit = fields.Boolean('Credit time', readonly=True, help='This is a credit time contract.')
    work_time_rate = fields.Selection([('0.5', '1/2'), ('0.8', '4/5'), ('0.9', '9/10')], string='Work time rate',
        readonly=True, help='Work time rate versus full time working schedule.')
    fiscal_voluntarism = fields.Boolean(
        string="Fiscal Voluntarism", default=False, tracking=True,
        help="Voluntarily increase withholding tax rate.")
    fiscal_voluntary_rate = fields.Float(string="Fiscal Voluntary Rate", help="Should be between 0 and 100 %")
    attachment_salary_ids = fields.One2many('l10n_be.attachment.salary', 'contract_id')

    _sql_constraints = [
        ('check_percentage_ip_rate', 'CHECK(ip_wage_rate >= 0 AND ip_wage_rate <= 100)', 'The IP rate on wage should be between 0 and 100.'),
        ('check_percentage_fiscal_voluntary_rate', 'CHECK(fiscal_voluntary_rate >= 0 AND fiscal_voluntary_rate <= 100)', 'The Fiscal Voluntary rate on wage should be between 0 and 100.')
    ]

    @api.depends('holidays', 'wage', 'final_yearly_costs')
    def _compute_wage_with_holidays(self):
        for contract in self:
            if contract.holidays:
                yearly_cost = contract.final_yearly_costs * (1.0 - contract.holidays / 231.0)
                contract.wage_with_holidays = contract._get_gross_from_employer_costs(yearly_cost)
            else:
                contract.wage_with_holidays = contract.wage

    def _inverse_wage_with_holidays(self):
        for contract in self:
            if contract.holidays:
                yearly_cost = contract._get_advantages_costs() + (13.92 + 13.0 * EMPLOYER_ONSS) * contract.wage_with_holidays
                contract.final_yearly_costs = yearly_cost / (1.0 - contract.holidays / 231.0)
                contract.wage = contract._get_gross_from_employer_costs(contract.final_yearly_costs)
            else:
                contract.wage = contract.wage_with_holidays

    @api.depends('transport_mode_car', 'transport_mode_public', 'transport_mode_private_car', 'transport_mode_others',
        'company_car_total_depreciated_cost', 'public_transport_reimbursed_amount', 'others_reimbursed_amount', 'km_home_work')
    def _compute_transport_employer_cost(self):
        for contract in self:
            transport_employer_cost = 0.0
            if contract.transport_mode_car:
                transport_employer_cost += contract.company_car_total_depreciated_cost
            if contract.transport_mode_public:
                transport_employer_cost += contract.public_transport_reimbursed_amount
            if contract.transport_mode_others:
                transport_employer_cost += contract.others_reimbursed_amount
            if contract.transport_mode_private_car:
                transport_employer_cost += self._get_private_car_reimbursed_amount(contract.km_home_work)
            contract.transport_employer_cost = transport_employer_cost

    @api.depends('commission_on_target')
    def _compute_commission_cost(self):
        for contract in self:
            contract.warrants_cost = contract.commission_on_target * 1.326 / 1.05
            contract.yearly_commission_cost = contract.warrants_cost * 3.0 + contract.commission_on_target * 9.0 * (1 + EMPLOYER_ONSS)
            contract.warrant_value_employee = contract.commission_on_target * 1.326 * (1.00 - 0.535)

    @api.depends(
        'wage', 'fuel_card', 'representation_fees', 'transport_employer_cost',
        'internet', 'mobile', 'yearly_commission_cost',
        'meal_voucher_paid_by_employer')
    def _compute_final_yearly_costs(self):
        for contract in self:
            contract.final_yearly_costs = contract._get_advantages_costs() + (13.92 + 13.0 * EMPLOYER_ONSS) * contract.wage

    @api.onchange('final_yearly_costs')
    def _onchange_final_yearly_costs(self):
        self.wage = self._get_gross_from_employer_costs(self.final_yearly_costs)

    @api.depends('meal_voucher_amount')
    def _compute_meal_voucher_paid_by_employer(self):
        for contract in self:
            contract.meal_voucher_paid_by_employer = contract.meal_voucher_amount * (1 - 0.1463)

    @api.depends('wage')
    def _compute_ucm_insurance(self):
        for contract in self:
            contract.ucm_insurance = (contract.wage * 12.0) * 0.05

    @api.depends('public_transport_employee_amount')
    def _compute_public_transport_reimbursed_amount(self):
        for contract in self:
            contract.public_transport_reimbursed_amount = contract._get_public_transport_reimbursed_amount(contract.public_transport_employee_amount)

    def _get_public_transport_reimbursed_amount(self, amount):
        return amount * 0.68

    @api.depends('final_yearly_costs')
    def _compute_monthly_yearly_costs(self):
        for contract in self:
            contract.monthly_yearly_costs = contract.final_yearly_costs / 12.0

    @api.depends('km_home_work', 'transport_mode_private_car')
    def _compute_private_car_reimbursed_amount(self):
        for contract in self:
            if contract.transport_mode_private_car:
                amount = self._get_private_car_reimbursed_amount(contract.km_home_work)
            else:
                amount = 0.0
            contract.private_car_reimbursed_amount = amount

    @api.onchange('transport_mode_car', 'transport_mode_public', 'transport_mode_others')
    def _onchange_transport_mode(self):
        if not self.transport_mode_car:
            self.fuel_card = 0
            self.company_car_total_depreciated_cost = 0
        if not self.transport_mode_others:
            self.others_reimbursed_amount = 0
        if not self.transport_mode_public:
            self.public_transport_reimbursed_amount = 0

    def _get_advantages_costs(self):
        self.ensure_one()
        return (
            12.0 * self.representation_fees +
            12.0 * self.fuel_card +
            12.0 * self.internet +
            12.0 * self.mobile +
            12.0 * self.transport_employer_cost +
            self.yearly_commission_cost +
            220.0 * self.meal_voucher_paid_by_employer
        )

    def _get_mobile_amount(self, has_mobile):
        if has_mobile:
            return self.env['ir.default'].sudo().get('hr.contract', 'mobile')
        return 0.0

    def _get_gross_from_employer_costs(self, yearly_cost):
        self.ensure_one()
        remaining_for_gross = yearly_cost - self._get_advantages_costs()
        return remaining_for_gross / (13.92 + 13.0 * EMPLOYER_ONSS)

    @api.model
    def _get_private_car_reimbursed_amount(self, distance):
        amounts_train = [
            (0, 0.0),
            (3, 22.3), (4, 24.4), (5, 26), (6, 28),
            (7, 30), (8, 31), (9, 33), (10, 35),
            (11, 37), (12, 38.5), (13, 40), (14, 42),
            (15, 43.5), (16, 45), (17, 47.5), (18, 49),
            (19, 51), (20, 53), (21, 54), (22, 56),
            (23, 58), (24, 59), (25, 62), (26, 63),
            (27, 65), (28, 67), (29, 68), (30, 70),
            (33, 73), (36, 78), (39, 82), (42, 87),
            (45, 91), (48, 96), (51, 101),
            (54, 104), (57, 107), (60, 111), (65, 115),
            (70, 120), (75, 126), (80, 132), (85, 137),
            (90, 143), (95, 148), (100, 153), (105, 160),
            (110, 165), (115, 171), (120, 177), (125, 181),
            (130, 187), (135, 192), (140, 198), (145, 203),
            (None, 211),
        ]

        for distance_boundary, amount in amounts_train:
            if distance_boundary is None or distance <= distance_boundary:
                return amount

    @api.model
    def update_state(self):
        # Called by a cron
        # It schedules an activity before the expiration of a credit time contract
        date_today = fields.Date.from_string(fields.Date.today())
        outdated_days = fields.Date.to_string(date_today + relativedelta(days=+14))
        nearly_expired_contracts = self.search([('state', '=', 'open'), ('time_credit', '=', True), ('date_end', '<', outdated_days)])
        nearly_expired_contracts.write({'kanban_state': 'blocked'})

        for contract in nearly_expired_contracts.filtered(lambda contract: contract.hr_responsible_id):
            contract.activity_schedule(
                'mail.mail_activity_data_todo', contract.date_end,
                user_id=contract.hr_responsible_id.id)

        return super(HrContract, self).update_state()
