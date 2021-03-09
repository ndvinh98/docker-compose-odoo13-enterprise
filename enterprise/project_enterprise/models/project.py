# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools.misc import format_date
from datetime import timedelta

class ProjectTaskType(models.Model):
    _inherit = 'project.task.type'

    is_closed = fields.Boolean('Is a close stage', help="Tasks in this stage are considered as closed.")


class Task(models.Model):
    _inherit = "project.task"

    planned_date_begin = fields.Datetime("Start date")
    planned_date_begin_formatted = fields.Char(compute='_compute_planned_date_begin')
    planned_date_end = fields.Datetime("End date")
    partner_email = fields.Char(related='partner_id.email', string='Customer Email', readonly=False)
    partner_phone = fields.Char(related='partner_id.phone', readonly=False)
    partner_mobile = fields.Char(related='partner_id.mobile', readonly=False)
    partner_zip = fields.Char(related='partner_id.zip', readonly=False)
    partner_street = fields.Char(related='partner_id.street', readonly=False)
    project_color = fields.Integer('Project color', related='project_id.color')

    _sql_constraints = [
        ('planned_dates_check', "CHECK ((planned_date_begin <= planned_date_end))", "The planned start date must be prior to the planned end date."),
    ]

    @api.depends('planned_date_begin')
    def _compute_planned_date_begin(self):
        for task in self:
            task.planned_date_begin_formatted = format_date(self.env, task.planned_date_begin) if task.planned_date_begin else None

    # ----------------------------------------------------
    # Gantt view
    # ----------------------------------------------------

    @api.model
    def gantt_unavailability(self, start_date, end_date, scale, group_bys=None, rows=None):
        start_datetime = fields.Datetime.from_string(start_date)
        end_datetime = fields.Datetime.from_string(end_date)
        user_ids = set()

        # function to "mark" top level rows concerning users
        # the propagation of that user_id to subrows is taken care of in the traverse function below
        def tag_user_rows(rows):
            for row in rows:
                group_bys = row.get('groupedBy')
                res_id = row.get('resId')
                if group_bys:
                    # if user_id is the first grouping attribute
                    if group_bys[0] == 'user_id' and res_id:
                        user_id = res_id
                        user_ids.add(user_id)
                        row['user_id'] = user_id
                    # else we recursively traverse the rows
                    elif 'user_id' in group_bys:
                        tag_user_rows(row.get('rows'))

        tag_user_rows(rows)
        resources = self.env['res.users'].browse(user_ids).mapped('resource_ids').filtered(lambda r: r.company_id.id == self.env.company.id)
        # we reverse sort the resources by date to keep the first one created in the dictionary
        # to anticipate the case of a resource added later for the same employee and company
        user_resource_mapping = {resource.user_id.id : resource.id for resource in resources.sorted('create_date', True)}
        leaves_mapping = resources._get_unavailable_intervals(start_datetime, end_datetime)

        # function to recursively replace subrows with the ones returned by func
        def traverse(func, row):
            new_row = dict(row)
            if new_row.get('user_id'):
                for sub_row in new_row.get('rows'):
                    sub_row['user_id'] = new_row['user_id']
            new_row['rows'] = [traverse(func, row) for row in new_row.get('rows')]
            return func(new_row)

        cell_dt = timedelta(hours=1) if scale in ['day', 'week'] else timedelta(hours=12)

        # for a single row, inject unavailability data
        def inject_unavailability(row):
            new_row = dict(row)
            user_id = row.get('user_id')
            if user_id:
                resource_id = user_resource_mapping.get(user_id)
                if resource_id:
                    # remove intervals smaller than a cell, as they will cause half a cell to turn grey
                    # ie: when looking at a week, a employee start everyday at 8, so there is a unavailability
                    # like: 2019-05-22 20:00 -> 2019-05-23 08:00 which will make the first half of the 23's cell grey
                    notable_intervals = filter(lambda interval: interval[1] - interval[0] >= cell_dt, leaves_mapping[resource_id])
                    new_row['unavailabilities'] = [{'start': interval[0], 'stop': interval[1]} for interval in notable_intervals]
            return new_row

        return [traverse(inject_unavailability, row) for row in rows]
