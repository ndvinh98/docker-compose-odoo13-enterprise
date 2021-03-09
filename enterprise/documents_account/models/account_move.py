# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.osv import expression


class AccountMove(models.Model):
    _inherit = "account.move"

    document_request_line_id = fields.Many2one('account.move.line', string='Reconciliation Journal Entry Line')

    def _get_request_document_actions(self):
        actions = []
        view_id = self.env.ref('documents.documents_request_form_view').id
        for record in self:
            for line in record.line_ids:
                reconcile_model = line.reconcile_model_id
                if reconcile_model and reconcile_model.activity_type_id:
                    activity = reconcile_model.activity_type_id
                    if activity and activity.category == 'upload_file':
                        actions.append({
                            'type': 'ir.actions.act_window',
                            'res_model': 'documents.request_wizard',
                            'name': _("Request Document for %s") % line.name,
                            'view_id': view_id,
                            'views': [(view_id, 'form')],
                            'target': 'new',
                            'view_mode': 'form',
                            'context': {'default_res_model': 'account.move.line',
                                        'default_res_id': line.id,
                                        'default_name': line.name,
                                        'default_activity_type_id': activity.id}
                        })
        return actions

    def _get_domain_matching_suspense_moves(self):
        # OVERRIDE to handle the document requests in the suspense accounts domain.
        domain = super(AccountMove, self)._get_domain_matching_suspense_moves()
        return expression.OR([
            domain,
            [('reconciliation_invoice_id', '=', self.id)]
        ])

    def write(self, vals):
        main_attachment_id = vals.get('message_main_attachment_id')
        # We assume that main_attachment_id is written on a single record,
        # since the current flows are going this way. Ensuring that we have only one record will avoid performance issue
        # when writing on invoices in batch.
        # To make it work in batch if we want to update multiple main_attachment_ids simultaneously,
        # most of this function may need to be rewritten.
        if main_attachment_id and not self._context.get('no_document') and len(self) == 1:
            previous_attachment_id = self.message_main_attachment_id.id
            document = False
            if previous_attachment_id:
                document = self.env['documents.document'].sudo().search([('attachment_id', '=', previous_attachment_id)], limit=1)
            if document:
                document.attachment_id = main_attachment_id
            elif self.company_id.documents_account_settings:
                setting = self.env['documents.account.folder.setting'].sudo().search(
                    [('journal_id', '=', self.journal_id.id),
                     ('company_id', '=', self.company_id.id)], limit=1)
                if setting:
                    values = {
                        'folder_id': setting.folder_id.id,
                        'partner_id': self.partner_id.id,
                        'owner_id': self.create_uid.id,
                        'tag_ids': [(6, 0, setting.tag_ids.ids if setting.tag_ids else [])],
                    }
                    Documents = self.env['documents.document'].with_context(default_type='empty').sudo()
                    doc = Documents.search([('attachment_id', '=', main_attachment_id)], limit=1)
                    if doc:
                        doc.write(values)
                    else:
                        # backward compatibility with documents that may be not
                        # registered as attachments yet
                        values.update({'attachment_id' : main_attachment_id})
                        doc.create(values)
        return super(AccountMove, self).write(vals)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    reconciliation_invoice_id = fields.One2many('account.move', 'document_request_line_id')
