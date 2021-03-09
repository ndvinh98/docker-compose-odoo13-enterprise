# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class ProductTemplate(models.Model):
    _inherit = "product.template"

    worksheet_template_id = fields.Many2one('project.worksheet.template', string="Worksheet Template")

    @api.onchange('service_tracking')
    def _onchange_service_tracking(self):
        if self.service_tracking not in ['task_global_project', 'task_new_project']:
            self.worksheet_template_id = False
        super(ProductTemplate, self)._onchange_service_tracking()

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id.is_fsm:
            self.worksheet_template_id = self.project_id.worksheet_template_id
