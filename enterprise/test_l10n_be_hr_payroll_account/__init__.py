# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID
from odoo.fields import Datetime
from dateutil.relativedelta import relativedelta


def _generate_payslips(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Do this only when demo data is activated
    if env.ref('l10n_be_hr_payroll.res_company_be', raise_if_not_found=False):
        if not env['hr.payslip'].sudo().search_count([('employee_id.name', '=', 'Marian Weaver')]):

            employees = env['hr.employee'].search([('company_id', '=', env.ref('l10n_be_hr_payroll.res_company_be').id)])
            wizard_vals = {
                'employee_ids': [(4, employee.id) for employee in employees],
                'structure_id': env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id
            }
            cids = env.ref('l10n_be_hr_payroll.res_company_be').ids

            for i in range(2, 20):
                date_start = Datetime.today() - relativedelta(months=i, day=1)
                date_end = Datetime.today() - relativedelta(months=i, day=31)
                payslip_run = env['hr.payslip.run'].create({
                    'name': date_start.strftime('%B %Y'),
                    'date_start': date_start,
                    'date_end': date_end,
                    'company_id': env.ref('l10n_be_hr_payroll.res_company_be').id,
                })
                wizard = env['hr.payslip.employees'].create(wizard_vals)
                wizard.with_context(active_id=payslip_run.id, allowed_company_ids=cids).compute_sheet()
                payslip_run.with_context(allowed_company_ids=cids).action_validate()
