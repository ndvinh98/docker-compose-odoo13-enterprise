# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    vehicle_id = fields.Many2one('fleet.vehicle', string='Company Car', domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]", help="Employee's company car.")

    @api.onchange('employee_id', 'struct_id', 'contract_id', 'date_from', 'date_to')
    def _onchange_employee(self):
        res = super(HrPayslip, self)._onchange_employee()
        if self.contract_id.car_id:
            self.vehicle_id = self.contract_id.car_id
        return res