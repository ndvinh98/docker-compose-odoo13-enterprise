# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta


from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

WORK_RATE = [('0.5', '1/2'), ('0.8', '4/5'), ('0.9', '9/10')]

class L10nBeHrPayrollCreditTime(models.TransientModel):
    _name = 'l10n_be.hr.payroll.credit.time.wizard'
    _description = 'Manage Belgian Credit Time'

    @api.model
    def default_get(self, field_list):
        if self.env.company.country_id != self.env.ref('base.be'):
            raise UserError(_('You must be logged in a Belgian company to use this feature'))
        return super().default_get(field_list)

    contract_id = fields.Many2one('hr.contract', string='Contract', default=lambda self: self.env.context.get('active_id'))
    date_start = fields.Date('Start Date Credit Time', help="Start date of the credit time contract.", required=True)
    date_end = fields.Date('End Date Credit Time', required=True,
        help="Last day included of the credit time contract.")

    resource_calendar_id = fields.Many2one(
        'resource.calendar', 'New Working Schedule', required=True,
        default=lambda self: self.env.company.resource_calendar_id.id)
    wage = fields.Monetary('New Wage', digits=(16, 2), required=True, help="Employee's monthly gross wage in credit time.")
    currency_id = fields.Many2one(string="Currency", related='contract_id.company_id.currency_id', readonly=True)

    work_time = fields.Selection(WORK_RATE, string='Work Time Rate',
        required=True, help='Work time rate versus full time working schedule.')

    @api.onchange('work_time')
    def _onchange_work_time(self):
        self.wage = self.contract_id.wage_with_holidays * float(self.work_time)

    def validate_credit_time(self):
        if self.date_start > self.date_end:
            raise ValidationError(_('Start date must be earlier than end date.'))
        if self.contract_id.date_end and self.contract_id.date_end < self.date_start:
            raise ValidationError(_('Current contract is finished before the start of credit time period.'))
        if self.contract_id.date_end and self.contract_id.date_end < self.date_end:
            raise ValidationError(_('Current contract is finished before the end of credit time period.'))

        credit_time_contract = self.contract_id.copy({
            'name': _('%s - Credit Time %s') % (self.contract_id.name, dict(WORK_RATE)[self.work_time]),
            'date_start': self.date_start,
            'date_end': self.date_end,
            'wage_with_holidays': self.wage,
            'resource_calendar_id': self.resource_calendar_id.id,
            'time_credit' : True,
            'work_time_rate' : self.work_time,
            'state': 'draft',
        })

        self.contract_id.date_end = self.date_start + timedelta(days=-1)

        return {
            'name': _('Credit time contract'),
            'domain': [('id', 'in', [credit_time_contract.id, self.contract_id.id])],
            'res_model': 'hr.contract',
            'view_id': False,
            'view_mode': 'tree,form',
            'type': 'ir.actions.act_window',
        }

class L10nBeHrPayrollExitCreditTime(models.TransientModel):
    _name = 'l10n_be.hr.payroll.exit.credit.time.wizard'
    _description = 'Manage Belgian Exit Credit Time'

    @api.model
    def default_get(self, field_list):
        if self.env.company.country_id != self.env.ref('base.be'):
            raise UserError(_('You must be logged in a Belgian company to use this feature'))
        res = super(L10nBeHrPayrollExitCreditTime, self).default_get(field_list)
        current_credit_time = self.env['hr.contract'].browse(self.env.context.get('active_id'))
        last_full_time = self.env['hr.contract'].search([('employee_id', '=', current_credit_time.employee_id.id),
            ('time_credit', '=', False), ('date_end', '!=', False), ('state', '!=', 'cancel')],
            order="date_end desc", limit=1)
        if last_full_time:
            res['contract_id'] = last_full_time.id
            res['resource_calendar_id'] = last_full_time.resource_calendar_id.id
            res['wage'] = last_full_time.wage
        res['date_start'] = current_credit_time.date_end + timedelta(days=1)
        return res

    credit_time_contract_id = fields.Many2one('hr.contract', string='Credit Time Contract', default=lambda self: self.env.context.get('active_id'))
    contract_id = fields.Many2one('hr.contract', string='Contract')
    date_start = fields.Date('Start Date', help="Start date of the normal time contract.", required=True)
    date_end = fields.Date('End Date', help="End date of the normal time contract (if it's a fixed-term contract).")

    resource_calendar_id = fields.Many2one(
        'resource.calendar', 'New Working Schedule', required=True)
    wage = fields.Monetary('New Wage', digits=(16, 2), required=True, help="Employee's monthly gross wage.")
    currency_id = fields.Many2one(string="Currency", related='contract_id.company_id.currency_id', readonly=True)

    def validate_full_time(self):
        if self.date_end and self.date_start > self.date_end:
            raise ValidationError(_('Start date must be earlier than end date.'))
        if self.date_start < self.credit_time_contract_id.date_end:
            raise ValidationError(_('Start date must be later than end date of credit time contract.'))

        full_time_contract = self.contract_id.copy({
            'date_start': self.date_start,
            'date_end': self.date_end,
            'wage_with_holidays': self.wage,
            'resource_calendar_id': self.resource_calendar_id.id,
            'time_credit' : False,
            'state': 'draft',
            })

        return {
            'name': _('Full time contract'),
            'res_id': full_time_contract.id,
            'res_model': 'hr.contract',
            'view_id': False,
            'view_mode': 'form',
            'type': 'ir.actions.act_window',
        }
