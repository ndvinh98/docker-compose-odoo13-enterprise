#-*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class HrWorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'

    meal_voucher = fields.Boolean(
        string="Meal Voucher", default=False,
        help="Work entries counts for meal vouchers")
    dmfa_code = fields.Char(string="DMFA code")
    leave_right = fields.Boolean(
        string="Keep Time Off Right", default=False,
        help="Work entries counts for time off right for next year.")
