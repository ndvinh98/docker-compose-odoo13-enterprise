# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import babel
from dateutil.relativedelta import relativedelta

from odoo import fields, models, _
from odoo.tools.misc import get_lang
from odoo.addons.web.controllers.main import clean_action
from ast import literal_eval

DEFAULT_MONTH_RANGE = 3


class ProjectOverview(models.Model):
    _inherit = 'project.project'

    def _plan_prepare_values(self):
        values = super()._plan_prepare_values()
        values.update({'with_forecasts': any(self.mapped('allow_forecast'))})
        return values

    def _table_get_line_values(self):
        result = super(ProjectOverview, self)._table_get_line_values()

        if any(self.mapped('allow_forecast')):
            # add headers
            result['header'] += [{
                'label': _('Remaining \n (Forecasts incl.)'),
                'tooltip': _('What is still to deliver based on sold hours, hours already done and forecasted hours. Equals to sold hours - done hours - forecasted hours.'),
            }]

            # add last column to compute the second remaining with forecast
            for row in result['rows']:
                # Sold - Done (current month excl.) - MAX (Done and Forecasted for this month) - Forecasted (current month excl.)
                row += [row[-2] - (row[5] - row[4]) - max(row[4], row[6]) - (row[10] - row[6])]
        return result

    def _table_header(self):
        header = super(ProjectOverview, self)._table_header()

        def _to_short_month_name(date):
            month_index = fields.Date.from_string(date).month
            return babel.dates.get_month_names('abbreviated', locale=get_lang(self.env).code)[month_index]

        if any(self.mapped('allow_forecast')):
            initial_date = fields.Date.from_string(fields.Date.today())
            fc_months = sorted([fields.Date.to_string(initial_date + relativedelta(months=i, day=1)) for i in range(0, DEFAULT_MONTH_RANGE)])  # M3, M4, M5

            new_header = header[0:-2]
            for header_name in [_to_short_month_name(date) for date in fc_months] + [_('After'), _('Total')]:
                new_header.append({
                    'label': header_name,
                    'tooltip': '',
                })
            header = new_header + header[-2:]

        return header

    def _table_row_default(self):
        default_row = super(ProjectOverview, self)._table_row_default()
        if any(self.mapped('allow_forecast')):
            return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # before, M1, M2, M3, Done, M3, M4, M5, After, Forecasted, Sold, Remaining
        return default_row  # before, M1, M2, M3, Done, Sold, Remaining

    def _table_rows_sql_query(self):
        query, query_params = super(ProjectOverview, self)._table_rows_sql_query()

        initial_date = fields.Date.from_string(fields.Date.today())
        fc_months = sorted([fields.Date.to_string(initial_date + relativedelta(months=i, day=1)) for i in range(0, DEFAULT_MONTH_RANGE)])  # M3, M4, M5

        if any(self.mapped('allow_forecast')):
            query += """
                UNION
                SELECT
                    'forecast' AS type,
                    date_trunc('month', date)::date AS month_date,
                    F.employee_id AS employee_id,
                    S.order_id AS sale_order_id,
                    F.order_line_id AS sale_line_id,
                    SUM(F.allocated_hours) / NULLIF(SUM(F.working_days_count), 0) * count(*) AS number_hours
                FROM generate_series(
                    (SELECT min(start_datetime) FROM planning_slot)::date,
                    (SELECT max(end_datetime) FROM planning_slot)::date,
                    '1 day'::interval
                ) date
                    LEFT JOIN planning_slot F ON date >= F.start_datetime::date AND date <= end_datetime::date
                    LEFT JOIN hr_employee E ON F.employee_id = E.id
                    LEFT JOIN resource_resource R ON E.resource_id = R.id
                    LEFT JOIN sale_order_line S ON F.order_line_id = S.id
                WHERE
                    EXTRACT(ISODOW FROM date) IN (
                        SELECT A.dayofweek::integer+1 FROM resource_calendar_attendance A WHERE A.calendar_id = R.calendar_id
                    )
                    AND F.project_id IN %s
                    AND date_trunc('month', date)::date >= %s
                    AND F.allocated_hours > 0
                    AND F.employee_id IS NOT NULL
                GROUP BY F.project_id, F.task_id, date_trunc('month', date)::date, F.employee_id, S.order_id, F.order_line_id
            """
            query_params += (tuple(self.ids), fc_months[0])
        return query, query_params

    def _table_rows_get_employee_lines(self, data_from_db):
        rows_employee = super(ProjectOverview, self)._table_rows_get_employee_lines(data_from_db)
        if not any(self.mapped('allow_forecast')):
            return rows_employee

        initial_date = fields.Date.today()
        fc_months = sorted([initial_date + relativedelta(months=i, day=1) for i in range(0, DEFAULT_MONTH_RANGE)])  # M3, M4, M5
        default_row_vals = self._table_row_default()

        # extract employee names
        employee_ids = set()
        for data in data_from_db:
            employee_ids.add(data['employee_id'])
        map_empl_names = {empl.id: empl.name for empl in self.env['hr.employee'].sudo().browse(employee_ids)}

        # extract rows data for employee, sol and so rows
        for data in data_from_db:
            sale_line_id = data['sale_line_id']
            sale_order_id = data['sale_order_id']
            # employee row
            row_key = (data['sale_order_id'], sale_line_id, data['employee_id'])
            if row_key not in rows_employee:
                meta_vals = {
                    'label': map_empl_names.get(row_key[2]),
                    'sale_line_id': sale_line_id,
                    'sale_order_id': sale_order_id,
                    'res_id': row_key[2],
                    'res_model': 'hr.employee',
                    'type': 'hr_employee'
                }
                rows_employee[row_key] = [meta_vals] + default_row_vals[:]  # INFO, before, M1, M2, M3, Done, M3, M4, M5, After, Forecasted

            index = False
            if data['type'] == 'forecast':
                if data['month_date'] in fc_months:
                    index = fc_months.index(data['month_date']) + 6
                elif data['month_date'] > fc_months[-1]:
                    index = 9
                rows_employee[row_key][index] += data['number_hours'] if data['number_hours'] else 0
                rows_employee[row_key][10] += data['number_hours'] if data['number_hours'] else 0
        return rows_employee

    def _table_get_empty_so_lines(self):
        """ get the Sale Order Lines having no forecast but having generated a task or a project """
        empty_line_ids, empty_order_ids = super(ProjectOverview, self)._table_get_empty_so_lines()
        sale_line_ids = self.env['project.task'].sudo().search_read([('project_id', 'in', self.ids), ('sale_line_id', '!=', False)], ['sale_line_id'])
        sale_line_ids = [line_id['sale_line_id'][0] for line_id in sale_line_ids]
        order_ids = self.env['sale.order.line'].sudo().search_read([('id', 'in', sale_line_ids)], ['order_id'])
        order_ids = [order_id['order_id'][0] for order_id in order_ids]
        so_line_data = self.env['sale.order.line'].sudo().search_read([('order_id', 'in', order_ids), '|', ('task_id', '!=', False), ('project_id', '!=', False), ('analytic_line_ids', '=', False)], ['id', 'order_id'])
        so_line_ids = [so_line['id'] for so_line in so_line_data]
        order_ids = [so_line['order_id'][0] for so_line in so_line_data]
        return empty_line_ids | set(so_line_ids), empty_order_ids | set(order_ids)

    # --------------------------------------------------
    # Actions: Stat buttons, ...
    # --------------------------------------------------

    def _plan_get_stat_button(self):
        stat_buttons = super()._plan_get_stat_button()
        if not any(self.mapped('allow_forecast')):
            return stat_buttons

        action = clean_action(self.env.ref('project_forecast.project_forecast_action_by_project').read()[0])
        context = literal_eval(action['context'])

        if len(self) == 1:
            context.update({'default_project_id': self.id})
        context.update({'search_default_future': 0})
        action['context'] = context

        stat_buttons.append({
            'name': _('Planning'),
            'icon': 'fa fa-tasks',
            'action': {
                'data-model': 'planning.slot',
                'data-domain': json.dumps([('project_id', 'in', self.ids)]),
                'data-context': json.dumps(action['context']),
                'data-views': json.dumps(action['views'])
            }
        })
        return stat_buttons
