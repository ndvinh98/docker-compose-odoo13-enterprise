# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools

from odoo.addons.hr_appraisal.models.hr_appraisal import HrAppraisal

COLORS_BY_STATE = {
    'new': 0,
    'cancel': 1,
    'pending': 2,
    'done': 3,
}

class HrAppraisalReport(models.Model):
    _name = "hr.appraisal.report"
    _description = "Appraisal Statistics"
    _auto = False

    name = fields.Char(related='employee_id.name')
    create_date = fields.Date(string='Create Date', readonly=True)
    department_id = fields.Many2one('hr.department', string='Department', readonly=True)
    deadline = fields.Date(string="Deadline", readonly=True)
    final_interview = fields.Date(string="Interview", readonly=True)
    employee_id = fields.Many2one('hr.employee', string="Employee", readonly=True)
    state = fields.Selection([
        ('new', 'To Start'),
        ('pending', 'Appraisal Sent'),
        ('done', 'Done'),
        ('cancel', "Cancelled"),
    ], 'Status', readonly=True)
    color = fields.Integer(compute='_compute_color')

    def _compute_color(self):
        for record in self:
            record.color = COLORS_BY_STATE[record.state]

    _order = 'create_date desc'

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'hr_appraisal_report')
        self.env.cr.execute("""
            create or replace view hr_appraisal_report as (
                 select
                     min(a.id) as id,
                     date(a.create_date) as create_date,
                     a.employee_id,
                     e.department_id as department_id,
                     a.date_close as deadline,
                     a.date_final_interview as final_interview,
                     a.state
                     from hr_appraisal a
                        left join hr_employee e on (e.id=a.employee_id)
                 GROUP BY
                     a.id,
                     a.create_date,
                     a.state,
                     a.employee_id,
                     a.date_close,
                     a.date_final_interview,
                     e.department_id
                )
            """)
