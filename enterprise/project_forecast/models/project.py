# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, exceptions, fields, models, _
from odoo.exceptions import UserError


class Project(models.Model):
    _inherit = 'project.project'

    allow_forecast = fields.Boolean("Planning", default=False, help="Enable planning tasks on the project.")

    def unlink(self):
        if self.env['planning.slot'].sudo().search_count([('project_id', 'in', self.ids)]) > 0:
            raise UserError(_('You cannot delete a project containing plannings. You can either delete all the project\'s forecasts and then delete the project or simply deactivate the project.'))
        return super(Project, self).unlink()


class Task(models.Model):
    _inherit = 'project.task'

    allow_forecast = fields.Boolean('Allow Planning', readonly=True, related='project_id.allow_forecast', store=False)

    def unlink(self):
        if self.env['planning.slot'].sudo().search_count([('task_id', 'in', self.ids)]) > 0:
            raise UserError(_('You cannot delete a task containing plannings. You can either delete all the task\'s plannings and then delete the task or simply deactivate the task.'))
        return super(Task, self).unlink()
