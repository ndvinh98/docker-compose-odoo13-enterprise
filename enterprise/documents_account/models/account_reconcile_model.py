# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class AccountReconciliation(models.AbstractModel):
    _inherit = 'account.reconciliation.widget'

    @api.model
    def process_bank_statement_line(self, st_line_ids, data):
        bsl_dict = super(AccountReconciliation, self).process_bank_statement_line(st_line_ids, data)
        moves = self.env['account.move'].browse(bsl_dict.get('moves'))
        if moves:
            bsl_dict['documents_actions'] = moves._get_request_document_actions()
        return bsl_dict


class AccountReconcileModel(models.Model):
    _inherit = 'account.reconcile.model'

    activity_type_id = fields.Many2one('mail.activity.type',
                                       string="Activity type",
                                       domain="[('category', '=', 'upload_file'), ('folder_id', '!=', False)]")

    @api.onchange('to_check')
    def _on_to_check_change(self):
        if not self.to_check:
            self.activity_type_id = False
