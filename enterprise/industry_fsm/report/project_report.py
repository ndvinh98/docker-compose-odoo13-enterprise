# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo import models, tools


class ReportProjectTaskUser(models.Model):
    _name = 'report.project.task.user.fsm'
    _inherit = 'report.project.task.user'
    _description = "FSM Tasks Analysis"

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            CREATE view %s as
            %s
            FROM project_task t
            INNER JOIN project_project p ON t.project_id = p.id AND p.is_fsm = 't'
            WHERE t.active = 'true'
                %s
        """ % (self._table, self._select(), self._group_by()))
