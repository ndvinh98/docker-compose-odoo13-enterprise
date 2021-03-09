# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayroll28110Wizard(models.TransientModel):
    _name = 'hr.payroll.281.10.wizard'
    _description = 'HR Payroll 281.10 Wizard'

    @api.model
    def default_get(self, field_list=None):
        if self.env.company.country_id != self.env.ref('base.be'):
            raise UserError(_('You must be logged in a Belgian company to use this feature'))
        return super().default_get(field_list)

    def _get_years(self):
        return [(str(i), i) for i in range(fields.Date.today().year - 1, 2009, -1)]

    reference_year = fields.Selection(
        selection='_get_years', string='Reference Year', required=True,
        default=lambda x: str(fields.Date.today().year - 1))
    is_test = fields.Boolean(string="Is It a test ?", default=False)
    type_sending = fields.Selection([
        ('0', 'Original send'),
        ('1', 'Send grouped corrections'),
        ], string="Sending Type", default='0', required=True)
    type_treatment = fields.Selection([
        ('0', 'Original'),
        ('1', 'Modification'),
        ('2', 'Add'),
        ('3', 'Cancel'),
        ], string="Treatment Type", default='0', required=True)

    def action_generate_files(self, file_type=['pdf', 'xml']):
        basic_info = {
            'year': self.reference_year,
            'is_test': self.is_test,
            'type_sending': self.type_sending,
            'type_treatment': self.type_treatment,
        }
        employees = self.env['hr.employee'].browse(self.env.context.get('active_ids'))
        employees._generate_281_10_form(basic_info, file_type)

    def action_generate_xml(self):
        self.action_generate_files(file_type=['xml'])

    def action_generate_pdf(self):
        self.action_generate_files(file_type=['pdf'])
