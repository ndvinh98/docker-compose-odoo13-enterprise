# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    documents_project_settings = fields.Boolean(related='company_id.documents_project_settings', readonly=False,
                                                string="Project")
    project_folder = fields.Many2one('documents.folder', related='company_id.project_folder', readonly=False,
                                     string="project default workspace")
    project_tags = fields.Many2many('documents.tag', 'project_tags_table',
                                    related='company_id.project_tags', readonly=False,
                                    string="Project Tags")

    @api.onchange('project_folder')
    def on_project_folder_change(self):
        if self.project_folder != self.project_tags.mapped('folder_id'):
            self.project_tags = False
