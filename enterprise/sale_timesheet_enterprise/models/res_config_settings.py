# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields

from odoo.addons.sale_timesheet_enterprise.models.sale import DEFAULT_INVOICED_TIMESHEET


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    invoiced_timesheet = fields.Selection([
        ('all', "All recorded timesheets"),
        ('approved', "Approved timesheets only"),
    ], default=DEFAULT_INVOICED_TIMESHEET, string="Timesheets Invoicing", config_parameter='sale.invoiced_timesheet')
    timesheet_min_duration = fields.Integer('Minimal duration', default=15, config_parameter='sale_timesheet_enterprise.timesheet_min_duration')
    timesheet_rounding = fields.Integer('Rounding up', default=15, config_parameter='sale_timesheet_enterprise.timesheet_rounding')
