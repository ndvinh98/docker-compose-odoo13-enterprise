# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Copyright (c) 2005-2006 Axelor SARL. (http://www.axelor.com)

from odoo import api, fields, models
from datetime import timedelta


class HrLeave(models.Model):
    _inherit = "hr.leave"

    @api.model
    def gantt_unavailability(self, start_date, end_date, scale, group_bys=None, rows=None):
        start_datetime = fields.Datetime.from_string(start_date)
        end_datetime = fields.Datetime.from_string(end_date)
        employee_ids = set()

        # function to "mark" top level rows concerning employees
        # the propagation of that item to subrows is taken care of in the traverse function below
        def tag_employee_rows(rows):
            for row in rows:
                group_bys = row.get('groupedBy')
                res_id = row.get('resId')
                if group_bys:
                    # if employee_id is the first grouping attribute, we mark the row
                    if group_bys[0] == 'employee_id' and res_id:
                        employee_id = res_id
                        employee_ids.add(employee_id)
                        row['employee_id'] = employee_id
                    # else we recursively traverse the rows where employee_id appears in the group_by
                    elif 'employee_id' in group_bys:
                        tag_employee_rows(row.get('rows'))

        tag_employee_rows(rows)
        employees = self.env['hr.employee'].browse(employee_ids)
        leaves_mapping = employees.mapped('resource_id')._get_unavailable_intervals(start_datetime, end_datetime)

        # function to recursively replace subrows with the ones returned by func
        def traverse(func, row):
            new_row = dict(row)
            if new_row.get('employee_id'):
                for sub_row in new_row.get('rows'):
                    sub_row['employee_id'] = new_row['employee_id']
            new_row['rows'] = [traverse(func, row) for row in new_row.get('rows')]
            return func(new_row)

        cell_dt = timedelta(hours=1) if scale in ['day', 'week'] else timedelta(hours=12)

        # for a single row, inject unavailability data
        def inject_unvailabilty(row):
            new_row = dict(row)

            if row.get('employee_id'):
                employee_id = self.env['hr.employee'].browse(row.get('employee_id'))
                if employee_id:
                    # remove intervals smaller than a cell, as they will cause half a cell to turn grey
                    # ie: when looking at a week, a employee start everyday at 8, so there is a unavailability
                    # like: 2019-05-22 20:00 -> 2019-05-23 08:00 which will make the first half of the 23's cell grey
                    notable_intervals = filter(lambda interval: interval[1] - interval[0] >= cell_dt, leaves_mapping[employee_id.resource_id.id])
                    new_row['unavailabilities'] = [{'start': interval[0], 'stop': interval[1]} for interval in notable_intervals]
            return new_row

        return [traverse(inject_unvailabilty, row) for row in rows]
