# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class IrSequence(models.Model):
    _inherit = "ir.sequence"

    l10n_latam_document_type_code = fields.Char(
        'Document Type Code', related='l10n_latam_document_type_id.name', readonly=True)
    l10n_cl_dte_caf_ids = fields.One2many('l10n_cl.dte.caf', 'sequence_id', 'DTE Caf')
    l10n_cl_qty_available = fields.Integer('Quantity Available', compute='_qty_available')

    @api.depends('l10n_cl_dte_caf_ids')
    def _qty_available(self):
        for record in self:
            available_folios = 0
            for caf in record.sudo().l10n_cl_dte_caf_ids.filtered(lambda x: x.status == 'in_use'):
                if record.number_next_actual in range(caf.start_nb, caf.final_nb + 1):
                    available_folios += caf.final_nb - record.number_next_actual + 1
                else:
                    available_folios += caf.final_nb - caf.start_nb + 1
            record.l10n_cl_qty_available = available_folios

    def get_caf_file(self, folio=None):
        folio = folio or self.number_next_actual
        caf = self.sudo().l10n_cl_dte_caf_ids.filtered(
            lambda x: folio in range(x.start_nb, x.final_nb + 1) and x.status == 'in_use')
        if not caf:
            raise UserError(_('There are no CAFs available for folio %s in the sequence of %s. '
                            'Please upload a CAF file or ask for a new one at www.sii.cl website') % (folio, self.name))
        return caf._decode_caf()
