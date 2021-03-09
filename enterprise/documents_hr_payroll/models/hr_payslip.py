# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrPaylsip(models.Model):
    _name = 'hr.payslip'
    _inherit = ['hr.payslip', 'documents.mixin']

    def _get_document_tags(self):
        return self.company_id.documents_hr_payslips_tags

    def _get_document_owner(self):
        return self.employee_id.user_id

    def _get_document_folder(self):
        return self.company_id.documents_hr_folder

    def _check_create_documents(self):
        return self.company_id.documents_hr_settings and super()._check_create_documents()
