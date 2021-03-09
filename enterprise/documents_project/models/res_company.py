# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _


class ResCompany(models.Model):
    _inherit = "res.company"

    def _domain_company(self):
        company = self.env.company
        return ['|', ('company_id', '=', False), ('company_id', '=', company)]

    documents_project_settings = fields.Boolean()
    project_folder = fields.Many2one('documents.folder', string="Project Workspace", domain=_domain_company,
                                     default=lambda self: self.env.ref('documents.documents_internal_folder',
                                                                       raise_if_not_found=False))
    project_tags = fields.Many2many('documents.tag', 'project_tags_table')

