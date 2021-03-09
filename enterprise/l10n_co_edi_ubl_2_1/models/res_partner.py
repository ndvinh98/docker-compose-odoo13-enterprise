# coding: utf-8
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_co_edi_fiscal_regimen = fields.Selection([
        ('48', 'Responsable del Impuesto sobre las ventas - IVA'),
        ('49', 'No responsables del IVA'),
    ], string="Fiscal Regimen", required=True, default='48')
    l10n_co_edi_commercial_name = fields.Char('Commercial Name')

    def _get_vat_without_verification_code(self):
        self.ensure_one()
        # last digit is the verification code
        # last digit is the verification code, but it could have a - before
        if self.l10n_co_document_type != 'rut' or self.vat == '222222222222':
            return self.vat
        if self.vat and "-" in self.vat:
            return self.vat.split('-')[0]
        return self.vat[:-1] if self.vat else ''

    def _get_vat_verification_code(self):
        self.ensure_one()
        if self.l10n_co_document_type != 'rut':
            return ''
        if self.vat and "-" in self.vat:
            return self.vat.split('-')[1]
        return self.vat[-1] if self.vat else ''

    def _l10n_co_edi_get_fiscal_values(self):
        return self.l10n_co_edi_obligation_type_ids | self.l10n_co_edi_customs_type_ids
