# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.osv import expression
from odoo.addons.sale_timesheet_enterprise.models.sale import DEFAULT_INVOICED_TIMESHEET


class AnalyticLine(models.Model):

    _inherit = 'account.analytic.line'

    def _get_adjust_grid_domain(self, column_value):
        """ Don't adjust already invoiced timesheet """
        domain = super(AnalyticLine, self)._get_adjust_grid_domain(column_value)
        return expression.AND([domain, [('timesheet_invoice_id', '=', False)]])

    def _timesheet_get_portal_domain(self):
        domain = super(AnalyticLine, self)._timesheet_get_portal_domain()
        param_invoiced_timesheet = self.env['ir.config_parameter'].sudo().get_param('sale.invoiced_timesheet', DEFAULT_INVOICED_TIMESHEET)
        if param_invoiced_timesheet == 'approved':
            domain = expression.AND([domain, [('validated', '=', True)]])
        return domain
