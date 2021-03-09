# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_mx_edi_pac = fields.Selection(
        related='company_id.l10n_mx_edi_pac', readonly=False,
        string='MX PAC*')
    l10n_mx_edi_pac_test_env = fields.Boolean(
        related='company_id.l10n_mx_edi_pac_test_env', readonly=False,
        string='MX PAC test environment*')
    l10n_mx_edi_pac_username = fields.Char(
        related='company_id.l10n_mx_edi_pac_username', readonly=False,
        string='MX PAC username*')
    l10n_mx_edi_pac_password = fields.Char(
        related='company_id.l10n_mx_edi_pac_password', readonly=False,
        string='MX PAC password*')
    l10n_mx_edi_certificate_ids = fields.Many2many(
        related='company_id.l10n_mx_edi_certificate_ids', readonly=False,
        string='MX Certificates*')
    l10n_mx_edi_num_exporter = fields.Char(
        related='company_id.l10n_mx_edi_num_exporter', readonly=False,
        string='Number of Reliable Exporter')
    l10n_mx_edi_fiscal_regime = fields.Selection(
        related='company_id.l10n_mx_edi_fiscal_regime', readonly=False,
        string="Fiscal Regime",
        help="It is used to fill Mexican XML CFDI required field "
        "Comprobante.Emisor.RegimenFiscal.")
