# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _
from odoo.tools.date_utils import start_of, end_of, add
from odoo.tools.misc import format_date


class Company(models.Model):
    _inherit = "res.company"

    manufacturing_period = fields.Selection([
        ('month', 'Monthly'),
        ('week', 'Weekly'),
        ('day', 'Daily')], string="Manufacturing Period",
        default='week', required=True,
        help="Default value for the time ranges in Master Production Schedule report.")

    manufacturing_period_to_display = fields.Integer('Number of columns for the\
        given period to display in Master Production Schedule', default=12)
    mrp_mps_show_starting_inventory = fields.Boolean(
        'Display Starting Inventory', default=True)
    mrp_mps_show_demand_forecast = fields.Boolean(
        'Display Demand Forecast', default=True)
    mrp_mps_show_actual_demand = fields.Boolean(
        'Display Actual Demand', default=False)
    mrp_mps_show_indirect_demand = fields.Boolean(
        'Display Indirect Demand', default=True)
    mrp_mps_show_to_replenish = fields.Boolean(
        'Display To Replenish', default=True)
    mrp_mps_show_actual_replenishment = fields.Boolean(
        'Display Actual Replenishment', default=False)
    mrp_mps_show_safety_stock = fields.Boolean(
        'Display Safety Stock', default=True)
    mrp_mps_show_available_to_promise = fields.Boolean(
        'Display Available to Promise', default=False)

    def _get_date_range(self):
        """ Return the date range for a production schedude depending the
        manufacturing period and the number of columns to display specify by the
        user. It returns a list of tuple that contains the timestamp for each
        column.
        """
        self.ensure_one()
        date_range = []
        first_day = start_of(fields.Date.today(), self.manufacturing_period)
        for columns in range(self.manufacturing_period_to_display):
            last_day = end_of(first_day, self.manufacturing_period)
            date_range.append((first_day, last_day))
            first_day = add(last_day, days=1)
        return date_range

    def _date_range_to_str(self):
        date_range = self._get_date_range()
        dates_as_str = []
        lang = self.env.context.get('lang')
        for date_start, date_stop in date_range:
            if self.manufacturing_period == 'month':
                dates_as_str.append(format_date(self.env, date_start, date_format='MMM YYYY'))
            elif self.manufacturing_period == 'week':
                dates_as_str.append(_('Week %s') % format_date(self.env, date_start, date_format='w'))
            else:
                dates_as_str.append(format_date(self.env, date_start, date_format='MMM d'))
        return dates_as_str
