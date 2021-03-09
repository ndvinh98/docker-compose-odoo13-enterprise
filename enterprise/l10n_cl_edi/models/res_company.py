# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

L10N_CL_SII_REGIONAL_OFFICES_ITEMS = [
    ('ur_Anc', 'Ancud'),
    ('ur_Ang', 'Angol'),
    ('ur_Ant', 'Antofagasta'),
    ('ur_Ari', 'Arica y Parinacota'),
    ('ur_Ays', 'Aysén'),
    ('ur_Cal', 'Calama'),
    ('ur_Cas', 'Castro'),
    ('ur_Cau', 'Cauquenes'),
    ('ur_Cha', 'Chaitén'),
    ('ur_Chn', 'Chañaral'),
    ('ur_ChC', 'Chile Chico'),
    ('ur_Chi', 'Chillán'),
    ('ur_Coc', 'Cochrane'),
    ('ur_Cop', 'Concepción '),
    ('ur_Cos', 'Constitución'),
    ('ur_Coo', 'Copiapo'),
    ('ur_Coq', 'Coquimbo'),
    ('ur_Coy', 'Coyhaique'),
    ('ur_Cur', 'Curicó'),
    ('ur_Ill', 'Illapel'),
    ('ur_Iqu', 'Iquique'),
    ('ur_LaF', 'La Florida'),
    ('ur_LaL', 'La Ligua'),
    ('ur_LaS', 'La Serena'),
    ('ur_LaU', 'La Unión'),
    ('ur_Lan', 'Lanco'),
    ('ur_Leb', 'Lebu'),
    ('ur_Lin', 'Linares'),
    ('ur_Lod', 'Los Andes'),
    ('ur_Log', 'Los Ángeles'),
    ('ur_Oso', 'Osorno'),
    ('ur_Ova', 'Ovalle'),
    ('ur_Pan', 'Panguipulli'),
    ('ur_Par', 'Parral'),
    ('ur_Pic', 'Pichilemu'),
    ('ur_Por', 'Porvenir'),
    ('ur_PuM', 'Puerto Montt'),
    ('ur_PuN', 'Puerto Natales'),
    ('ur_PuV', 'Puerto Varas'),
    ('ur_PuA', 'Punta Arenas'),
    ('ur_Qui', 'Quillota'),
    ('ur_Ran', 'Rancagua'),
    ('ur_SaA', 'San Antonio'),
    ('ur_Sar', 'San Carlos'),
    ('ur_SaF', 'San Felipe'),
    ('ur_SaD', 'San Fernando'),
    ('ur_SaV', 'San Vicente de Tagua Tagua'),
    ('ur_SaZ', 'Santa Cruz'),
    ('ur_SaC', 'Santiago Centro'),
    ('ur_SaN', 'Santiago Norte'),
    ('ur_SaO', 'Santiago Oriente'),
    ('ur_SaP', 'Santiago Poniente'),
    ('ur_SaS', 'Santiago Sur'),
    ('ur_TaT', 'Tal-Tal'),
    ('ur_Tac', 'Talca'),
    ('ur_Tah', 'Talcahuano'),
    ('ur_Tem', 'Temuco'),
    ('ur_Toc', 'Tocopilla'),
    ('ur_Vld', 'Valdivia'),
    ('ur_Val', 'Vallenar'),
    ('ur_Vlp', 'Valparaíso'),
    ('ur_Vic', 'Victoria'),
    ('ur_ViA', 'Villa Alemana'),
    ('ur_ViR', 'Villarrica'),
    ('ur_ViM', 'Viña del Mar'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_cl_dte_email = fields.Char('DTE Email', related='partner_id.l10n_cl_dte_email', readonly=False)
    l10n_cl_dte_service_provider = fields.Selection([
        ('SIITEST', 'SII - Test'),
        ('SII', 'SII - Production')], 'DTE Service Provider',
        help='Please select your company service provider for DTE service.')
    l10n_cl_dte_resolution_number = fields.Char(
        'SII Exempt Resolution Number',
        help='This value must be provided and must appear in your pdf or printed tribute document, under the '
             'electronic stamp to be legally valid.')
    l10n_cl_dte_resolution_date = fields.Date('SII Exempt Resolution Date')
    l10n_cl_sii_regional_office = fields.Selection(
        L10N_CL_SII_REGIONAL_OFFICES_ITEMS, translate=False, string='SII Regional Office')
    l10n_cl_activity_description = fields.Char(
        string='Glosa Giro', related='partner_id.l10n_cl_activity_description', readonly=False)
    l10n_cl_company_activity_ids = fields.Many2many('l10n_cl.company.activities', string='Activities Names',
        help='Please select the SII registered economic activities codes for the company', readonly=False)
    l10n_cl_sii_taxpayer_type = fields.Selection(
        related='partner_id.l10n_cl_sii_taxpayer_type', index=True, readonly=False,
        help='1 - VAT Affected (1st Category) (Most of the cases)\n'
             '2 - Fees Receipt Issuer (Applies to suppliers who issue fees receipt)\n'
             '3 - End consumer (only receipts)\n'
             '4 - Foreigner')
    l10n_cl_certificate_ids = fields.One2many(
        'l10n_cl.certificate', 'company_id', string='Certificates')

    def _get_digital_signature(self, user_id=None):
        """
        This method looks for a digital signature that could be used to sign invoices for the current company.
        If the digital signature is intended to be used exclusively by a single user, it will have that user_id
        otherwise, if the user is false, it is understood that the owner of the signature (which is always
        a natural person) shares it with the rest of the users for that company.
        """
        if user_id is not None:
            user_certificates = self.sudo().l10n_cl_certificate_ids.filtered(
                lambda x: x._is_valid_certificate() and x.user_id.id == user_id and
                          x.company_id.id == self.id)
            if user_certificates:
                return user_certificates[0]
        shared_certificates = self.sudo().l10n_cl_certificate_ids.filtered(
            lambda x: x._is_valid_certificate() and not x.user_id and x.company_id.id == self.id)
        if not shared_certificates:
            raise UserError(_('There is not a valid certificate for the company: %s') % self.name)

        return shared_certificates[0]
