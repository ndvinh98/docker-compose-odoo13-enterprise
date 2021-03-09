# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime

from odoo import api, fields, models, _
from odoo.tools import get_timedelta
from odoo.exceptions import ValidationError


class PlanningRecurrency(models.Model):
    _name = 'planning.recurrency'
    _description = "Planning Recurrence"

    slot_ids = fields.One2many('planning.slot', 'recurrency_id', string="Related planning entries")
    repeat_interval = fields.Integer("Repeat every", default=1, required=True)
    repeat_type = fields.Selection([('forever', 'Forever'), ('until', 'Until')], string='weeks', default='forever')
    repeat_until = fields.Datetime(string="Repeat until", help="Up to which date should the plannings be repeated")
    last_generated_end_datetime = fields.Datetime("Last Generated End Date", readonly=True)
    company_id = fields.Many2one('res.company', string="Company", readonly=True, required=True, default=lambda self: self.env.company)

    _sql_constraints = [
        ('check_repeat_interval_positive', 'CHECK(repeat_interval >= 1)', 'Recurrency repeat interval should be at least 1'),
        ('check_until_limit', "CHECK((repeat_type = 'until' AND repeat_until IS NOT NULL) OR (repeat_type != 'until'))", 'A recurrence repeating itself until a certain date must have its limit set'),
    ]

    @api.constrains('company_id', 'slot_ids')
    def _check_multi_company(self):
        for recurrency in self:
            if not all(recurrency.company_id == planning.company_id for planning in recurrency.slot_ids):
                raise ValidationError(_('An shift must be in the same company as its recurrency.'))

    def name_get(self):
        result = []
        for recurrency in self:
            if recurrency.repeat_type == 'forever':
                name = _('Forever, every %s week(s)') % (recurrency.repeat_interval,)
            else:
                name = _('Every %s week(s) until %s') % (recurrency.repeat_interval, recurrency.repeat_until)
            result.append([recurrency.id, name])
        return result

    @api.model
    def _cron_schedule_next(self):
        companies = self.env['res.company'].search([])
        now = fields.Datetime.now()
        stop_datetime = None
        for company in companies:
            delta = get_timedelta(company.planning_generation_interval, 'month')

            recurrencies = self.search([
                '&',
                '&',
                ('company_id', '=', company.id),
                ('last_generated_end_datetime', '<', now + delta),
                '|',
                ('repeat_until', '=', False),
                ('repeat_until', '>', now - delta),
            ])
            recurrencies._repeat_slot(now + delta)

    def _repeat_slot(self, stop_datetime=False):
        for recurrency in self:
            slot = self.env['planning.slot'].search([('recurrency_id', '=', recurrency.id)], limit=1, order='start_datetime DESC')

            if slot:
                # find the end of the recurrence
                recurrence_end_dt = False
                if recurrency.repeat_type == 'until':
                    recurrence_end_dt = recurrency.repeat_until

                # find end of generation period (either the end of recurrence (if this one ends before the cron period), or the given `stop_datetime` (usually the cron period))
                if not stop_datetime:
                    stop_datetime = fields.Datetime.now() + get_timedelta(recurrency.company_id.planning_generation_interval, 'month')
                range_limit = min([dt for dt in [recurrence_end_dt, stop_datetime] if dt])

                # generate recurring slots
                recurrency_delta = get_timedelta(recurrency.repeat_interval, 'week')
                next_start = slot.start_datetime + recurrency_delta

                slot_values_list = []
                while next_start < range_limit:
                    slot_values = slot.copy_data({
                        'start_datetime': next_start,
                        'end_datetime': next_start + (slot.end_datetime - slot.start_datetime),
                        'recurrency_id': recurrency.id,
                        'company_id': recurrency.company_id.id,
                        'repeat': True,
                        'is_published': False
                    })[0]
                    slot_values_list.append(slot_values)
                    next_start = next_start + recurrency_delta

                self.env['planning.slot'].create(slot_values_list)
                recurrency.write({'last_generated_end_datetime': next_start - recurrency_delta})

            else:
                recurrency.unlink()

    def _delete_slot(self, start_datetime):
        slots = self.env['planning.slot'].search([('recurrency_id', 'in', self.ids), ('start_datetime', '>=', start_datetime), ('is_published', '=', False)])
        slots.unlink()
