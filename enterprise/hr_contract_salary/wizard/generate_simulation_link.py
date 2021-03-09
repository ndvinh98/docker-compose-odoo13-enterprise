# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import uuid

from odoo import api, fields, models, _
from odoo.fields import Date
from odoo.exceptions import ValidationError

from werkzeug.urls import url_encode


class GenerateSimulationLink(models.TransientModel):
    _name = 'generate.simulation.link'
    _description = 'Gamification Simulation Link'

    @api.model
    def default_get(self, fields):
        result = super(GenerateSimulationLink, self).default_get(fields)
        model = self.env.context.get('active_model')
        if model == 'hr.contract':
            contract_id = self.env.context.get('active_id')
            contract = self.env['hr.contract'].sudo().browse(contract_id)
            if not contract.employee_id:
                result['contract_id'] = contract_id
            else:
                result['employee_id'] = contract.employee_id.id
                result['employee_contract_id'] = contract.id
                result['contract_id'] = contract.id
        elif model == 'hr.applicant':
            applicant_id = self.env.context.get('active_id')
            applicant = self.env['hr.applicant'].sudo().browse(applicant_id)
            if not applicant.access_token or applicant.access_token_end_date < Date.today():
                applicant.access_token = uuid.uuid4().hex
                applicant.access_token_end_date = self.env['hr.contract']._get_access_token_end_date()
            result['applicant_id'] = applicant_id
            result['contract_id'] = applicant.job_id.default_contract_id.id
        return result

    def get_contract_domain(self):
        return [
            '|',
            ('employee_id', '=', False),
            ('employee_id', '=', self.employee_contract_id.employee_id.id)]

    vehicle_id = fields.Many2one('fleet.vehicle', store=True)
    new_car = fields.Boolean('Can request a new car')
    new_car_model_id = fields.Many2one('fleet.vehicle.model', string="Model",
        domain=lambda self: self.env['hr.contract']._get_possible_model_domain())
    contract_id = fields.Many2one('hr.contract', string="Contract Template", required=True, store=True,
        domain=[('employee_id', '=', False)])
    contract_type = fields.Selection([
        ('PFI', 'PFI'),
        ('CDI', 'CDI'),
        ('CDD', 'CDD')], string="Contract Type", default="PFI")
    employee_contract_id = fields.Many2one('hr.contract')
    employee_id = fields.Many2one('hr.employee')
    final_yearly_costs = fields.Float(string="Employee Budget", store=True, required=True)
    applicant_id = fields.Many2one('hr.applicant')
    customer_relation = fields.Boolean("In relations with customers", default=True)
    job_title = fields.Char("Job Title")

    email_to = fields.Char('Email To', compute='_compute_email_to', store=True, readonly=False)
    url = fields.Char('Simulation link', compute='_compute_url')

    @api.depends('employee_id.address_home_id.email', 'applicant_id.email_from')
    def _compute_email_to(self):
        for wizard in self:
            if wizard.employee_id:
                wizard.email_to = wizard.employee_id.address_home_id.email
            elif wizard.applicant_id:
                wizard.email_to = wizard.applicant_id.email_from

    @api.depends('new_car', 'vehicle_id', 'new_car_model_id', 'contract_id',
                 'final_yearly_costs', 'applicant_id', 'customer_relation',
                 'contract_type', 'job_title')
    def _compute_url(self):
        for wizard in self:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            url = base_url + '/salary_package/simulation/contract/%s?' % (self.contract_id.id)
            params = {}
            if wizard.vehicle_id:
                params['car_id'] = wizard.vehicle_id.id
            if wizard.new_car and wizard.new_car_model_id:
                params['new_car_model_id'] = wizard.new_car_model_id.id
            if wizard.applicant_id:
                params['applicant_id'] = wizard.applicant_id.id
                params['token'] = wizard.applicant_id.access_token
            if wizard.customer_relation:
                params['customer_relation'] = 1
            if wizard.final_yearly_costs:
                params['final_yearly_costs'] = wizard.final_yearly_costs
            if wizard.contract_type:
                params['contract_type'] = wizard.contract_type
            if wizard.employee_contract_id:
                params['employee_contract_id'] = wizard.employee_contract_id.id
            if wizard.job_title:
                params['job_title'] = wizard.job_title
            if wizard.new_car:
                params['new_car'] = 1
            if params:
                url = url + url_encode(params)
            wizard.url = url

    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        self.final_yearly_costs = self.contract_id.final_yearly_costs
        self.job_title = self.contract_id.employee_id.job_title or self.contract_id.job_id.name
        self.contract_type = self.contract_id.contract_type
        if self.contract_id.car_id:
            self.vehicle_id = self.contract_id.car_id
        return {'domain': {'contract_id': self.get_contract_domain()}}

    def send_offer(self):
        try:
            template_id = self.env.ref('hr_contract_salary.mail_template_send_offer').id
        except ValueError:
            template_id = False
        try:
            template_applicant_id = self.env.ref('hr_contract_salary.mail_template_send_offer_applicant').id
        except ValueError:
            template_applicant_id = False
        try:
            compose_form_id = self.env.ref('mail.email_compose_message_wizard_form').id
        except ValueError:
            compose_form_id = False
        partner_to = False
        if self.employee_id:
            partner_to = self.employee_id.address_home_id
            if not partner_to:
                raise ValidationError(_("No private address defined on the employee!"))
        elif self.applicant_id:
            partner_to = self.applicant_id.partner_id
            if not partner_to:
                partner_to = self.env['res.partner'].create({
                    'is_company': False,
                    'name': self.applicant_id.partner_name,
                    'email': self.applicant_id.email_from,
                    'phone': self.applicant_id.partner_phone,
                    'mobile': self.applicant_id.partner_mobile
                })
                self.applicant_id.partner_id = partner_to

        if self.applicant_id:
            default_model = 'hr.applicant'
            default_res_id = self.applicant_id.id
            default_use_template = bool(template_applicant_id)
            default_template_id = template_applicant_id
        elif self.employee_contract_id:
            default_model = 'hr.contract'
            default_res_id = self.employee_contract_id.id
            default_use_template = bool(template_id)
            default_template_id = template_id
        else:
            default_model = 'hr.contract'
            default_res_id = self.contract_id.id
            default_use_template = bool(template_id)
            default_template_id = template_id

        ctx = {
            'default_model': default_model,
            'default_res_id': default_res_id,
            'default_use_template': default_use_template,
            'default_template_id': default_template_id,
            'default_composition_mode': 'comment',
            'salary_package_url': self.url,
            'custom_layout': "mail.mail_notification_light",
            'partner_to': partner_to and partner_to.id or False,
            'mail_post_autofollow': False,
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
