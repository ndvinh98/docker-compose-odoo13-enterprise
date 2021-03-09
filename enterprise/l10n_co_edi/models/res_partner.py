# coding: utf-8
from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_co_edi_large_taxpayer = fields.Boolean(string='Gran Contribuyente')

    l10n_co_edi_representation_type_id = fields.Many2one('l10n_co_edi.type_code', string='Tipo de Representación', domain=[('type', '=', 'representation')])
    l10n_co_edi_establishment_type_id = fields.Many2one('l10n_co_edi.type_code', string='Tipo Establecimiento', domain=[('type', '=', 'establishment')])

    l10n_co_edi_obligation_type_ids = fields.Many2many('l10n_co_edi.type_code',
                                                       'partner_l10n_co_edi_obligation_types',
                                                       'partner_id', 'type_id',
                                                       string='Obligaciones y Responsabilidades',
                                                       domain=[('type', '=', 'obligation')])
    l10n_co_edi_customs_type_ids = fields.Many2many('l10n_co_edi.type_code',
                                                    'partner_l10n_co_edi_customs_types',
                                                    'partner_id', 'type_id',
                                                    string='Usuario Aduanero',
                                                    domain=[('type', '=', 'customs')])
    l10n_co_edi_simplified_regimen = fields.Boolean('Simplified Regimen')

    def _get_vat_without_verification_code(self):
        self.ensure_one()
        # last digit is the verification code
        return self.vat[:-1] if self.vat else ''
