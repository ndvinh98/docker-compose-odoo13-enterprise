# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, fields
from odoo.exceptions import UserError, AccessError

import datetime


class account_analytic_line(models.Model):
    _inherit = "account.analytic.line"

    @api.model
    def clean_xml_ids(self):
        """
        Cleanup in case some xml_ids were created with the wrong module prefix
        """
        dirty_xml_ids = self.env['ir.model.data'].sudo().search([
            ('module', '=', 'project_timesheet_synchro'),
            ('model', 'in', [
                'mail.alias',
                'account.analytic.account',
                'project.project',
                'project.task',
                'account.analytic.line'
            ])
        ])
        dirty_xml_ids.write({'module': '__export__'})
        return True

    @api.model
    def export_data_for_ui(self):
        """
        Exports analytic lines (timesheet entries), tasks and projects for the UI during sync.
        """
        # AALS
        aal_ids = self.search([
            ("user_id", "=", self.env.uid),
            ("project_id", "!=", False),
            ("date", ">", (datetime.datetime.today() - datetime.timedelta(days=21)).strftime('%Y-%m-%d'))
            # The 21 days limit for data retrieval is arbitrary.
        ])

        aals_fields = [
            "id",
            "task_id/id",  # external id, to send to the UI
            "task_id.id",  # internal id, for data manipulation here
            "name",
            "project_id.id",
            "date",
            "unit_amount",
            "__last_update",
            #"sheet_id/state", removed in saas-17
            "project_id/id",
        ]

        aals = aal_ids.with_context(tz='UTC').export_data(aals_fields)

        # /!\ COMPATIBILITY HACK /!\
        # With hr_timesheet_sheet removal, the sheet concept (and its state) are obsolete. To avoid
        # changing the return format value for the mobile app (since it has to be compatible cross
        # version), we hardcored the sheet state as 'open'.
        for aal_row in aals['datas']:
            aal_row.insert(8, 'open')

        # List comprehension to find the task and project ids used in aals.
        task_ids_list = list(set([int(aals['datas'][x][2]) for x in range(len(aals['datas'])) if len(aals['datas'][x][2]) > 0]))
        project_ids_list = list(set([int(aals['datas'][x][4]) for x in range(len(aals['datas'])) if len(aals['datas'][x][4]) > 0]))

        # Tasks
        task_ids = self.env["project.task"].search([
            '&',
                '|',
                    '|',
                        ("user_id", "=", self.env.uid),
                    ("message_partner_ids", "=", self.env.user.partner_id.id),
                ("id", "in", task_ids_list),
            ('active', '=', True),
        ])
        tasks_fields = [
            "id",
            "project_id/id",
            "project_id.id",
            "name",
        ]
        tasks = task_ids.with_context(tz='UTC').export_data(tasks_fields)

        project_ids_from_tasks_list = list(set([int(tasks['datas'][x][2]) for x in range(len(tasks['datas'])) if len(tasks['datas'][x][2]) > 0]))
        project_ids_list = list(set(project_ids_from_tasks_list + project_ids_list))
        # Projects
        projects_ids = self.env["project.project"].search([
            '&', '&', '&', '|',
            ("id", "in", project_ids_list),
            ("user_id", '=', self.env.uid),
            ('favorite_user_ids', 'in', self.env.uid),
            ('active', '=', True),
            ('allow_timesheets', '=', True)
        ])

        projects_fields = [
            "id",
            "name",
        ]
        projects = projects_ids.with_context(tz='UTC').export_data(projects_fields)

        return {
            'aals': aals,
            'tasks': tasks,
            'projects': projects,
        }

    @api.model
    def import_ui_data(self, ls_aals, ls_tasks, ls_projects, context=None):
        """
        Imports the projects, tasks and analytic lines (timesheet entries) sent by the UI during sync.
        Returns a dict with lists of errors and lists of records to remove from the UI.
        The records to remove from the UI are those that no longer exist on the server and that have not been modified in the UI since the previous sync, and analytic lines where the user_id has been changed in the backend.
        In this method, ls_ refers to the items sent by the ui, from its localStorage.
        """
        cr = self.env.cr

        cr.execute("""
            SELECT concat(imd.module,'.',imd.name) as xml_id, p.active
            FROM ir_model_data imd
            JOIN project_project p ON (model='project.project' AND p.id = res_id)
            WHERE concat(imd.module,'.',imd.name) = ANY(%s);
            """, ([x['id'] for x in ls_projects],))

        sv_projects = {project['xml_id']: project['active'] for project in cr.dictfetchall()}

        ls_projects_to_import = []
        ls_projects_to_remove = []
        for ls_project in ls_projects:
            if not ls_project['id'] in sv_projects:
                if ls_project.get('to_sync'):
                    ls_projects_to_import.append([
                        str(ls_project['id']),
                        ls_project['name'],
                        'True'  # allow_timesheets
                    ])
                else:
                    ls_projects_to_remove.append(str(ls_project['id']))
            elif not sv_projects.get(ls_project['id']):
                ls_projects_to_remove.append(str(ls_project['id']))

        projects_fields = [
            'id',
            'name',
            'allow_timesheets'  # allowing timesheet without giving analytic account will generate an analytic account for the project
        ]
        project_errors = self.load_wrapper(self.env["project.project"], projects_fields, ls_projects_to_import)

        # Tasks management

        cr.execute("""
            SELECT concat(imd.module,'.',imd.name) AS xml_id, t.active
            FROM ir_model_data imd
            JOIN project_task t ON (model='project.task' AND t.id = res_id)
            JOIN mail_followers mf ON mf.res_id = t.id AND mf.res_model = 'project.task' AND mf.partner_id = %s
            WHERE concat(imd.module,'.',imd.name) = ANY(%s);
            """, (self.env.user.partner_id.id, [x['id'] for x in ls_tasks]))

        sv_tasks = {task['xml_id']: task['active'] for task in cr.dictfetchall()}

        ls_tasks_to_import = []
        ls_tasks_to_remove = []
        for ls_task in ls_tasks:
            if not ls_task['id'] in sv_tasks:
                if ls_task.get('to_sync'):
                    ls_tasks_to_import.append([
                        str(ls_task['id']),
                        ls_task['name'],
                        str(ls_task['project_id']),
                        str(self.env.uid),
                    ])
                else:
                    ls_tasks_to_remove.append(str(ls_task['id']))
            elif not sv_tasks.get(ls_task['id']):
                ls_tasks_to_remove.append(str(ls_task['id']))

        tasks_fields = [
            'id',
            'name',
            'project_id/id',
            'user_id/.id',
        ]
        task_errors = self.load_wrapper(self.env["project.task"], tasks_fields, ls_tasks_to_import)

        # Account analytic lines management

        cr.execute("""
            SELECT concat(imd.module,'.',imd.name) AS xml_id,
                aal.user_id,
                aal.id,
                DATE_TRUNC('second', aal.write_date) AS write_date
            FROM ir_model_data imd
            JOIN account_analytic_line aal ON (model='account.analytic.line' AND aal.id = res_id)
            WHERE concat(imd.module,'.',imd.name) = ANY(%s);
            """, ([x['id'] for x in ls_aals],))

        sv_aals = {}
        for aal in cr.dictfetchall():
            sv_aals[aal['xml_id']] = {
                'user_id': aal['user_id'],
                'write_date': aal['write_date'],
                'id': aal['id'],
            }

        new_ls_aals = []
        ls_aals_to_remove = []
        aals_on_hold = []
        for ls_aal in ls_aals:
            sv_aal = sv_aals.get(str(ls_aal['id']))
            sv_project = str(ls_aal.get('project_id')) in sv_projects or self.env["ir.model.data"].xmlid_to_object(str(ls_aal['project_id']))  # Fallback condition: when the project created after the sql select and thus is not in the list.

            if sv_aal and sv_aal['user_id'] != self.env.uid:  # The user on the activity has been changed
                ls_aals_to_remove.append(str(ls_aal['id']))
            elif sv_aal and ls_aal.get('to_remove'):  # The UI is requesting the deletion of the activity
                try:
                    self.browse(sv_aal['id']).unlink()
                    ls_aals_to_remove.append(str(ls_aal['id']))
                except (AccessError, UserError):
                    aals_on_hold.append(str(ls_aal['id']))
            elif ls_aal.get('to_sync') and sv_project:
                if sv_aal:
                    if(fields.Datetime.from_string(ls_aal['write_date']) > fields.Datetime.from_string(sv_aal['write_date'])):
                        new_ls_aals.append(ls_aal)
                else:
                    new_ls_aals.append(ls_aal)
            elif ls_aal.get('to_sync') and not sv_project:
                aals_on_hold.append(str(ls_aal['id']))
            elif not sv_aal:
                ls_aals_to_remove.append(str(ls_aal['id']))

        for new_ls_aal in new_ls_aals:
            if not new_ls_aal.get('task_id'):
                new_ls_aal['task_id'] = ""

        ls_aals_to_import = []
        for new_ls_aal in new_ls_aals:
            if new_ls_aal.get('to_sync'):
                ls_aals_to_import.append([
                    str(new_ls_aal['id']),
                    new_ls_aal['desc'],
                    new_ls_aal['project_id'],
                    new_ls_aal['date'],
                    new_ls_aal['unit_amount'],
                    str(new_ls_aal.get('task_id')),
                    self.env.uid,
                ])

        aals_fields = [
            'id',
            'name',
            'project_id/id',
            'date',
            'unit_amount',
            'task_id/id',
            'user_id/.id',
        ]

        aals_errors = self.load_wrapper(self, aals_fields, ls_aals_to_import)
        aals_errors['failed_records'] += aals_on_hold

        return {'project_errors': project_errors,
            'task_errors': task_errors,
            'aals_errors': aals_errors,
            'projects_to_remove': ls_projects_to_remove,
            'tasks_to_remove': ls_tasks_to_remove,
            'aals_to_remove': ls_aals_to_remove,
        }

    def load_wrapper(self, model, fields, data_rows):
        """
        Wrapper for the load method. It ensures that all valid records are loaded, while records that can't be loaded for any reason are left out.
        Returns the failed records ids and error messages.
        """
        messages = model.load(fields, data_rows)['messages']

        failed_records_indices = [messages[x].get('record') for x in range(len(messages)) if messages[x].get('type') == 'error']

        failed_records = []
        failed_records_messages = []

        if failed_records_indices:
            correct_data_rows = [v for i, v in enumerate(data_rows) if i not in failed_records_indices]
            second_load_message = model.load(fields, correct_data_rows)

            failed_records_messages = [messages[x].get('message') for x in range(len(messages)) if messages[x].get('type') == 'error']
            failed_records = [v[0] for i, v in enumerate(data_rows) if i in failed_records_indices]
        return {
            "failed_records": failed_records,
            "failed_records_messages": failed_records_messages,
        }
