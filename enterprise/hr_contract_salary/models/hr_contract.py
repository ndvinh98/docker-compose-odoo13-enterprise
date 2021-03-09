# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import uuid

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.fields import Date
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HrContract(models.Model):
    _inherit = 'hr.contract'

    origin_contract_id = fields.Many2one('hr.contract', string="Origin Contract", domain="[('company_id', '=', company_id)]", help="The contract from which this contract has been duplicated.")
    access_token = fields.Char('Security Token', copy=False)
    access_token_consumed = fields.Boolean('Consumed Access Token')
    access_token_end_date = fields.Date('Access Token Validity Date', copy=False)
    applicant_id = fields.Many2one('hr.applicant', domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    contract_reviews_count = fields.Integer(compute="_compute_contract_reviews_count", string="Proposed Contracts Count")
    contract_type = fields.Selection([
        ('PFI', 'PFI'),
        ('CDI', 'CDI'),
        ('CDD', 'CDD')], string="Contract Type", default="PFI")
    default_contract_id = fields.Many2one('hr.contract', string="Contract Template",
        domain="[('company_id', '=', company_id)]",
        help="Default contract used when making an offer to an applicant.")
    sign_template_id = fields.Many2one('sign.template', string="New Contract Document Template",
        help="Default document that the applicant will have to sign to accept a contract offer.")
    contract_update_template_id = fields.Many2one('sign.template', string="Contract Update Document Template",
        help="Default document that the employee will have to sign to update his contract.")
    signatures_count = fields.Integer(compute='_compute_signatures_count', string='# Signatures',
        help="The number of signatures on the pdf contract with the most signatures.")
    id_card = fields.Binary(related='employee_id.id_card', groups="hr_contract.group_hr_contract_manager")
    image_1920 = fields.Image(related='employee_id.image_1920', groups="hr_contract.group_hr_contract_manager")
    driving_license = fields.Binary(related='employee_id.driving_license', groups="hr_contract.group_hr_contract_manager")
    mobile_invoice = fields.Binary(related='employee_id.mobile_invoice', groups="hr_contract.group_hr_contract_manager")
    sim_card = fields.Binary(related='employee_id.sim_card', groups="hr_contract.group_hr_contract_manager")
    internet_invoice = fields.Binary(related="employee_id.internet_invoice", groups="hr_contract.group_hr_contract_manager")

    @api.depends('sign_request_ids.nb_closed')
    def _compute_signatures_count(self):
        for contract in self:
            contract.signatures_count = max(contract.sign_request_ids.mapped('nb_closed') or [0])

    @api.depends('origin_contract_id')
    def _compute_contract_reviews_count(self):
        for contract in self:
            contract.contract_reviews_count = self.with_context(active_test=False).search_count(
                [('origin_contract_id', '=', contract.id)])

    def _clean_redundant_salary_data(self):
        # Unlink archived draft contract older than 7 days linked to a signature
        # Unlink the related employee, partner, and new car (if any)
        seven_days_ago = date.today() + relativedelta(days=-7)
        contracts = self.search([
            ('state', '=', 'draft'),
            ('active', '=', False),
            ('sign_request_ids', '!=', False),
            ('create_date', '<=', Date.to_string(seven_days_ago))])
        employees = contracts.mapped('employee_id').filtered(lambda employee: not employee.active)
        partners = employees.mapped('address_home_id').filtered(
            lambda partner: not partner.active and partner.type == 'private')
        cars = contracts.mapped('car_id').filtered(lambda car: not car.active and not car.license_plate)
        vehicle_contracts = cars.with_context(active_test=False).mapped('log_contracts').filtered(
            lambda contract: not contract.active)
        costs = vehicle_contracts.mapped('cost_id')

        if contracts or employees or partners or cars or vehicle_contracts or costs:
            _logger.info('Salary: About to unlink vehicle costs %s, vehicle contracts %s, vehicles %s, partners %s, employees %s, contracts %s.',
                         costs.ids, vehicle_contracts.ids, cars.ids, partners.ids, employees.ids, contracts.ids)
            # Delete costs and vehicle contracts in cascade
            for cost in costs:
                try:
                    cost.unlink()
                except ValueError:
                    pass
            for car in cars:
                try:
                    car.unlink()
                except ValueError:
                    pass
            for partner in partners:
                try:
                    partner.unlink()
                except ValueError:
                    pass
            for employee in employees:
                try:
                    employee.unlink()
                except ValueError:
                    pass
            for contract in contracts:
                try:
                    contract.unlink()
                except ValueError:
                    pass

    def configure_access_token(self):
        for contract in self:
            contract.access_token = uuid.uuid4().hex
            contract.access_token_end_date = contract._get_access_token_end_date()

    def _get_access_token_end_date(self):
        today = fields.Date.today()
        validity = self.env['ir.config_parameter'].sudo().get_param('hr_contract_salary.access_token_validity', default=30)
        return fields.Date.to_string(fields.Date.from_string(today) + timedelta(days=int(validity)))

    def action_show_contract_reviews(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.contract",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [["origin_contract_id", "=", self.id], '|', ["active", "=", False], ["active", "=", True]],
            "name": "Contracts Reviews",
        }

    def send_offer(self):
        self.ensure_one()
        if self.employee_id.address_home_id:
            try:
                template_id = self.env.ref('hr_contract_salary.mail_template_send_offer').id
            except ValueError:
                template_id = False
            try:
                compose_form_id = self.env.ref('mail.email_compose_message_wizard_form').id
            except ValueError:
                compose_form_id = False
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            if self.employee_id.active:
                path = '/salary_package/contract/' + str(self.id)
            else:
                path = '/salary_package/contract/' + str(self.access_token)
            ctx = {
                'default_model': 'hr.contract',
                'default_res_id': self.ids[0],
                'default_use_template': bool(template_id),
                'default_template_id': template_id,
                'default_composition_mode': 'comment',
                'salary_package_url': base_url + path,
                'custom_layout': 'mail.mail_notification_light'
            }
            return {
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'mail.compose.message',
                'views': [(compose_form_id, 'form')],
                'view_id': compose_form_id,
                'target': 'new',
                'context': ctx,
            }
        else:
            raise ValidationError(_("No private address defined on the employee!"))
