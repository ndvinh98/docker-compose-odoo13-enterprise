# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions


class SignTemplate(models.Model):
    _name = 'sign.template'
    _inherit = ['sign.template', 'documents.mixin']

    folder_id = fields.Many2one('documents.folder', 'Signed Document Workspace')
    documents_tag_ids = fields.Many2many('documents.tag', string="Signed Document Tags")

    def _get_document_tags(self):
        return self.documents_tag_ids

    def _get_document_folder(self):
        return self.folder_id
