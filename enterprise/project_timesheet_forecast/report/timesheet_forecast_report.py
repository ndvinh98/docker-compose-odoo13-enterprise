# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import tools
from odoo import fields, models


class TimesheetForecastReport(models.Model):

    _name = "project.timesheet.forecast.report.analysis"
    _description = "Timesheet & Planning Statistics"
    _auto = False
    _rec_name = 'entry_date'
    _order = 'entry_date desc'

    entry_date = fields.Date('Date', readonly=True)
    employee_id = fields.Many2one('hr.employee', 'Employee', readonly=True)
    company_id = fields.Many2one('res.company', string="Company", related='employee_id.company_id', readonly=True)
    task_id = fields.Many2one('project.task', string='Task', readonly=True)
    project_id = fields.Many2one('project.project', string='Project', readonly=True)
    number_hours = fields.Float('Number of hours', readonly=True)
    line_type = fields.Selection([('forecast', 'Forecast'), ('timesheet', 'Timesheet')], string='Type', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE or REPLACE VIEW %s as (
                (
                    SELECT
                        d::date AS entry_date,
                        F.employee_id AS employee_id,
                        F.task_id AS task_id,
                        F.project_id AS project_id,
                        F.allocated_hours / NULLIF(F.working_days_count, 0) AS number_hours,
                        'forecast' AS line_type,
                        F.id AS id
                    FROM generate_series(
                        (SELECT min(start_datetime) FROM planning_slot)::date,
                        (SELECT max(end_datetime) FROM planning_slot)::date,
                        '1 day'::interval
                    ) d
                        LEFT JOIN planning_slot F ON d.date >= F.start_datetime AND d.date <= end_datetime
                        LEFT JOIN hr_employee E ON F.employee_id = E.id
                        LEFT JOIN resource_resource R ON E.resource_id = R.id
                    WHERE
                        EXTRACT(ISODOW FROM d.date) IN (
                            SELECT A.dayofweek::integer+1 FROM resource_calendar_attendance A WHERE A.calendar_id = R.calendar_id
                        )
                ) UNION (
                    SELECT
                        A.date AS entry_date,
                        E.id AS employee_id,
                        A.task_id AS task_id,
                        A.project_id AS project_id,
                        A.unit_amount AS number_hours,
                        'timesheet' AS line_type,
                        -A.id AS id
                    FROM account_analytic_line A, hr_employee E
                    WHERE A.project_id IS NOT NULL
                        AND A.employee_id = E.id
                )
            )
        """ % (self._table,))
