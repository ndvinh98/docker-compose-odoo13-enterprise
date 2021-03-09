# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import tools
from odoo import api, fields, models


class HrPayrollReport(models.Model):
    _name = "hr.payroll.report"
    _description = "Payroll Analysis Report"
    _auto = False
    _rec_name = 'date_from'
    _order = 'date_from desc'


    count = fields.Integer('# Payslip', group_operator="sum", readonly=True)
    count_work = fields.Integer('Work Days', group_operator="sum", readonly=True)
    count_work_hours = fields.Integer('Work Hours', group_operator="sum", readonly=True)
    count_leave = fields.Integer('Days of Paid Time Off', group_operator="sum", readonly=True)
    count_leave_unpaid = fields.Integer('Days of Unpaid Time Off', group_operator="sum", readonly=True)
    count_unforeseen_absence = fields.Integer('Days of Unforeseen Absence', group_operator="sum", readonly=True)

    name = fields.Char('Payslip Name', readonly=True)
    date_from = fields.Date('Start Date', readonly=True)
    date_to = fields.Date('End Date', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True)

    employee_id = fields.Many2one('hr.employee', 'Employee', readonly=True)
    department_id = fields.Many2one('hr.department', 'Department', readonly=True)
    job_id = fields.Many2one('hr.job', 'Job Position', readonly=True)
    number_of_days = fields.Float('Number of Days', readonly=True)
    number_of_hours = fields.Float('Number of Hours', readonly=True)
    net_wage = fields.Float('Net Wage', readonly=True)
    basic_wage = fields.Float('Basic Wage', readonly=True)
    gross_wage = fields.Float('Gross Wage', readonly=True)
    leave_basic_wage = fields.Float('Basic Wage for Time Off', readonly=True)

    work_code = fields.Many2one('hr.work.entry.type', 'Work type', readonly=True)
    work_type = fields.Selection([
        ('1', 'Regular Working Day'),
        ('2', 'Paid Time Off'),
        ('3', 'Unpaid Time Off')], string='Work, (un)paid Time Off', readonly=True)

    def init(self):
        query = """
            SELECT
                p.id as id,
                CASE WHEN wd.id = min_id.min_line THEN 1 ELSE 0 END as count,
                CASE WHEN wet.is_leave THEN 0 ELSE wd.number_of_days END as count_work,
                CASE WHEN wet.is_leave THEN 0 ELSE wd.number_of_hours END as count_work_hours,
                CASE WHEN wet.is_leave and wd.amount <> 0 THEN wd.number_of_days ELSE 0 END as count_leave,
                CASE WHEN wet.is_leave and wd.amount = 0 THEN wd.number_of_days ELSE 0 END as count_leave_unpaid,
                CASE WHEN wet.is_unforeseen THEN wd.number_of_days ELSE 0 END as count_unforeseen_absence,
                CASE WHEN wet.is_leave THEN wd.amount ELSE 0 END as leave_basic_wage,
                p.name as name,
                p.date_from as date_from,
                p.date_to as date_to,
                e.id as employee_id,
                e.department_id as department_id,
                c.job_id as job_id,
                e.company_id as company_id,
                wet.id as work_code,
                CASE WHEN wet.is_leave IS NOT TRUE THEN '1' WHEN wd.amount = 0 THEN '3' ELSE '2' END as work_type,
                wd.number_of_days as number_of_days,
                wd.number_of_hours as number_of_hours,
                CASE WHEN wd.id = min_id.min_line THEN pln.total ELSE 0 END as net_wage,
                CASE WHEN wd.id = min_id.min_line THEN plb.total ELSE 0 END as basic_wage,
                CASE WHEN wd.id = min_id.min_line THEN plg.total ELSE 0 END as gross_wage
            FROM
                (SELECT * FROM hr_payslip WHERE state IN ('done', 'paid')) p
                    left join hr_employee e on (p.employee_id = e.id)
                    left join hr_payslip_worked_days wd on (wd.payslip_id = p.id)
                    left join hr_work_entry_type wet on (wet.id = wd.work_entry_type_id)
                    left join (select payslip_id, min(id) as min_line from hr_payslip_worked_days group by payslip_id) min_id on (min_id.payslip_id = p.id)
                    left join hr_payslip_line pln on (pln.slip_id = p.id and  pln.code = 'NET')
                    left join hr_payslip_line plb on (plb.slip_id = p.id and plb.code = 'BASIC')
                    left join hr_payslip_line plg on (plg.slip_id = p.id and plg.code = 'GROSS')
                    left join hr_contract c on (p.contract_id = c.id)
            GROUP BY
                e.id,
                e.department_id,
                e.company_id,
                wd.id,
                wet.id,
                p.id,
                p.name,
                p.date_from,
                p.date_to,
                pln.total,
                plb.total,
                plg.total,
                min_id.min_line,
                c.id"""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (%s)""" % (self._table, query))
