# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _


class Task(models.Model):

    _inherit = 'project.task'

    def name_get(self):
        if 'project_task_display_forecast' in self._context:
            result = []
            for task in self:
                result.append((task.id, _('%s (%s remaining hours)') % (task.name, task.remaining_hours)))
            return result
        return super(Task, self).name_get()
