# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from odoo import models, fields
from odoo.osv import expression


class PlanningSend(models.TransientModel):
    _name = 'planning.send'
    _description = "Send Planning"

    start_datetime = fields.Datetime("Start Date", required=True)
    end_datetime = fields.Datetime("Stop Date", required=True)
    include_unassigned = fields.Boolean("Includes Open shifts", default=True)
    note = fields.Text("Extra Message", help="Additional message displayed in the email sent to employees")
    company_id = fields.Many2one('res.company', "Company", required=True, default=lambda self: self.env.company)

    _sql_constraints = [
        ('check_start_date_lower_stop_date', 'CHECK(end_datetime > start_datetime)', 'Planning end date should be greater than its start date'),
    ]

    def action_send(self):
        # create the planning
        planning = self.env['planning.planning'].create({
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'include_unassigned': self.include_unassigned,
            'company_id': self.company_id.id,
        })
        return planning.send_planning(message=self.note)

    def action_publish(self):
        # get user tz here to accord start and end datetime ?
        domain = [
            ('start_datetime', '>=', datetime.combine(fields.Date.from_string(self.start_datetime), datetime.min.time())),
            ('end_datetime', '<=', datetime.combine(fields.Date.from_string(self.end_datetime), datetime.max.time())),
            ('company_id', '=', self.company_id.id),
        ]
        if not self.include_unassigned:
            domain = expression.AND([domain, [('employee_id', '!=', False)]])
        to_publish = self.env['planning.slot'].sudo().search(domain)
        to_publish.write({
            'is_published': True,
            'publication_warning': False
        })
        return True
