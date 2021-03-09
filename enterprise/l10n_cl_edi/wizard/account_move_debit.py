# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountDebitNote(models.TransientModel):
    """
    Add Debit Note wizard: when you want to correct an invoice with a positive amount.
    Opposite of a Credit Note, but different from a regular invoice as you need the link to the original invoice.
    In some cases, also used to cancel Credit Notes
    """
    _name = 'account.debit.note'
    _inherit = 'account.debit.note'
    _description = 'Add Debit Note wizard'

    l10n_cl_edi_reference_doc_code = fields.Selection([
        ('1', '1. Cancels Referenced Document'),
        ('2', '2. Corrects Referenced Document Text'),
        ('3', '3. Corrects Referenced Document Amount')
    ], string='SII Reference Code')
    l10n_cl_original_text = fields.Char('Original Text', help='This is the text that is intended to be changed')
    l10n_cl_corrected_text = fields.Char('New Corrected Text', help='This is the text that should say')

    def _l10n_cl_get_reverse_doc_type(self, move):
        if move.partner_id.l10n_cl_sii_taxpayer_type == '4' or move.partner_id.country_id != self.env.ref('base.cl'):
            return self.env['l10n_latam.document.type'].search([('code', '=', '111'), ('country_id', '=', self.env.ref('base.cl').id)], limit=1)
        return self.env['l10n_latam.document.type'].search([('code', '=', '56'), ('country_id', '=', self.env.ref('base.cl').id)], limit=1)

    def _is_tax(self, account):
        return len(self.env['account.tax.repartition.line'].search(
            [['account_id', '=', account.id], ['repartition_type', '=', 'tax']])) > 0

    def _prepare_default_values(self, move):
        # I would like to add the following line, because there is no case where you need to copy the lines
        # except for reverting a credit note, and this case is not included in the base code of credit note.
        # The only motivation to comment it is to prevent the test to fail.
        # self.copy_lines = True if self.l10n_cl_edi_reference_doc_code == '1' else False
        default_values = super(AccountDebitNote, self)._prepare_default_values(move)
        if move.company_id.country_id != self.env.ref('base.cl'):
            return default_values
        reverse_move_latam_doc_type = self._l10n_cl_get_reverse_doc_type(move)
        default_values['invoice_origin'] = '%s %s' % (move.l10n_latam_document_type_id.doc_code_prefix,
                                                      move.l10n_latam_document_number)
        default_values['l10n_latam_document_type_id'] = reverse_move_latam_doc_type.id
        default_values['l10n_cl_reference_ids'] = [[0, 0, {
            'move_id': move.id,
            'origin_doc_number': int(move.l10n_latam_document_number),
            'l10n_cl_reference_doc_type_selection': move.l10n_latam_document_type_id.code,
            'reference_doc_code': self.l10n_cl_edi_reference_doc_code,
            'reason': self.reason,
            'date': move.invoice_date, }, ], ]
        if self.l10n_cl_edi_reference_doc_code == '1':
            # this is needed to reverse a credit note: we must include the same items we have in the credit note
            # if we make this with traditional "with_context(internal_type='debit_note').copy(default=default_values)
            # the values will appear negative in the debit note
            default_values['line_ids'] = [[5, 0]]
            tax_amount = sum([(taxes.price_unit if taxes.move_id.type in [
                'out_refund', 'in_refund'] else -taxes.price_unit) for taxes in move.line_ids.filtered(
                lambda x: self._is_tax(x.account_id))])
            for line in move.line_ids:
                if self._is_tax(line.account_id):
                    # if we have a line with a tax, there will be an unbalanced move entry. We must leave the tax
                    # apart and let the tax calculation to happen during the post
                    continue
                price_unit = abs(tax_amount) - abs(line.price_unit) if line.account_id.user_type_id.type in [
                    'receivable', 'payable'] else line.price_unit
                default_values['line_ids'].append([0, 0, {
                    'product_id': line.product_id.id,
                    'account_id': line.account_id.id,
                    'analytic_account_id': line.analytic_account_id.id,
                    'analytic_tag_ids': [[6, 0, line.analytic_tag_ids.ids]],
                    'name': line.name,
                    'quantity': line.quantity,
                    'price_unit': price_unit,
                    'exclude_from_invoice_tab': line.move_id.is_invoice() and (line.account_id.user_type_id.type in [
                        'receivable', 'payable'] or self._is_tax(line.account_id)),
                    'tax_ids': [[6, 0, line.tax_ids.ids]],
                    'tag_ids': [[6, 0, line.tag_ids.ids]], }, ])
        elif self.l10n_cl_edi_reference_doc_code == '2':
            default_values['line_ids'] = [[5, 0], [0, 0, {
                'account_id': move.journal_id.default_debit_account_id.id,
                'name': _('Where it says: %s should say: %s') % (
                    self._context.get('default_l10n_cl_original_text'),
                    self._context.get('default_l10n_cl_corrected_text')), 'quantity': 1, 'price_unit': 0.0, }, ], ]
        return default_values

    def create_debit(self):
        for move in self.move_ids.filtered(lambda r: r.company_id.country_id == self.env.ref('base.cl') and
                                                     r.type in ['out_invoice', 'out_refund'] and
                                                     r.l10n_cl_journal_point_of_sale_type == 'online' and
                                                     r.l10n_cl_dte_status not in ['accepted', 'objected']):
            raise UserError(_('You can add a debit note only if the %s is accepted or objected by SII. ' % move.name))
        return super(AccountDebitNote, self).create_debit()
