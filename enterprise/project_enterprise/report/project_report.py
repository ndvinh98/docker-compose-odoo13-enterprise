# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details

from odoo import models, tools


class ReportProjectTaskUser(models.Model):
    _inherit = 'report.project.task.user'

    def _select(self):
        return super(ReportProjectTaskUser, self)._select() + """,
            t.planned_date_begin as planned_date_begin,
            t.planned_date_end as planned_date_end
        """

    def _group_by(self):
        return super(ReportProjectTaskUser, self)._group_by() + """,
            planned_date_begin,
            planned_date_end
        """