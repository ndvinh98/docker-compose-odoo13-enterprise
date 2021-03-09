# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrEmployee(models.Model):
    _name = 'hr.employee'
    _inherit = ['hr.employee', 'documents.mixin']

    def _get_document_folder(self):
        return self.company_id.documents_hr_folder

    def _get_document_owner(self):
        return self.user_id

    def _check_create_documents(self):
        return self.company_id.documents_hr_settings and super()._check_create_documents()
