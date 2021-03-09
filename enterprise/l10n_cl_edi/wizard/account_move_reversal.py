# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    l10n_cl_edi_reference_doc_code = fields.Selection([
        ('1', '1. Cancels Referenced Document'),
        ('2', '2. Corrects Referenced Document Text'),
        ('3', '3. Corrects Referenced Document Amount')
    ], string='SII Reference Code')
    l10n_cl_is_text_correction = fields.Boolean('Only Text Correction')
    l10n_cl_original_text = fields.Char('Original Text', help='This is the text that is intended to be changed')
    l10n_cl_corrected_text = fields.Char('New Corrected Text', help='This is the text that should say')

    @api.onchange('refund_method', 'l10n_cl_is_text_correction')
    def _set_l10n_cl_edi_reference_doc_code(self):
        for record in self:
            if record.refund_method in ['cancel', 'modify']:
                record.l10n_cl_edi_reference_doc_code = '1'
            else:
                record.l10n_cl_edi_reference_doc_code = '2' if record.l10n_cl_is_text_correction else '3'

    def reverse_moves(self):
        return super(AccountMoveReversal, self.with_context(
            default_l10n_cl_edi_reference_doc_code=self.l10n_cl_edi_reference_doc_code,
            default_l10n_cl_original_text=self.l10n_cl_original_text,
            default_l10n_cl_corrected_text=self.l10n_cl_corrected_text
        )).reverse_moves()

    def _prepare_default_reversal(self, move):
        res = super()._prepare_default_reversal(move)
        if move.company_id.country_id != self.env.ref('base.cl'):
            return res
        res.update({
            'type': self._get_reverse_move_type(move.type),
            'l10n_latam_document_type_id': move._l10n_cl_get_reverse_doc_type().id,
            'invoice_origin': '%s %s' % (move.l10n_latam_document_type_id.doc_code_prefix,
                                         move.l10n_latam_document_number),
            'l10n_cl_reference_ids': [[0, 0, {
                'move_id': move.id,
                'origin_doc_number': int(move.l10n_latam_document_number),
                'l10n_cl_reference_doc_type_selection': move.l10n_latam_document_type_id.code,
                'reference_doc_code': self.l10n_cl_edi_reference_doc_code,
                'reason': self.reason,
                'date': move.invoice_date,
            }, ], ]
        })
        return res

    def _get_reverse_move_type(self, move_type):
        reverse_move_types = {
            'out_invoice': 'out_refund',
            'out_refund': 'out_invoice',
            'in_invoice': 'in_refund',
            'in_refund': 'in_invoice',
        }
        return reverse_move_types.get(move_type)
