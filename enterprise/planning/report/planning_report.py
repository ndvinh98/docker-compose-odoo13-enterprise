# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import tools
from odoo import fields, models


class PlanningReport(models.Model):
    _name = "planning.slot.report.analysis"
    _description = "Planning Statistics"
    _auto = False
    _rec_name = 'entry_date'
    _order = 'entry_date desc'

    entry_date = fields.Date('Date', readonly=True)
    employee_id = fields.Many2one('hr.employee', 'Employee', readonly=True)
    role_id = fields.Many2one('planning.role', string='Role', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    number_hours = fields.Float("Allocated Hours", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        # We dont take ressource into account as we would need to move
        # the generate_series() in the FROM and use a condition on the
        # join to exclude holidays like it's done in timesheet.
        self.env.cr.execute("""
            CREATE or REPLACE VIEW %s as (
                (
                    SELECT
                        p.id,
                        generate_series(start_datetime,end_datetime,'1 day'::interval) entry_date,
                        p.role_id AS role_id,
                        p.company_id AS company_id,
                        p.employee_id AS employee_id,
                        p.allocated_hours / ((p.end_datetime::date - p.start_datetime::date)+1) AS number_hours
                    FROM
                        planning_slot p
                )
            )
        """ % (self._table,))
