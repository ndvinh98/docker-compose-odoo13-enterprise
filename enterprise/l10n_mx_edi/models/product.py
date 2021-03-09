# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api
from odoo.osv import expression


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    l10n_mx_edi_code_sat_id = fields.Many2one(
        'l10n_mx_edi.product.sat.code', 'Code SAT',
        help='This value is required in CFDI version 3.3 to express the code '
        'of the product or service covered by the present concept. Must be '
        'used a key from the SAT catalog.',
        domain=[('applies_to', '=', 'product')])
    l10n_mx_edi_tariff_fraction_id = fields.Many2one(
        'l10n_mx_edi.tariff.fraction', string='Tariff Fraction',
        help='It is used to express the key of the tariff fraction '
        'corresponding to the description of the product to export.')
    l10n_mx_edi_umt_aduana_id = fields.Many2one(
        'uom.uom', 'UMT Aduana', help='Used in complement '
        '"Comercio Exterior" to indicate in the products the '
        'TIGIE Units of Measurement. It is based in the SAT catalog.')


class ProductUoM(models.Model):
    _inherit = 'uom.uom'

    l10n_mx_edi_code_sat_id = fields.Many2one(
        'l10n_mx_edi.product.sat.code', 'Code SAT',
        help='This value is required in CFDI version 3.3 to specify '
        'the standardized unit of measure code applicable to the quantity '
        'expressed in the concept. The unit must correspond to the '
        'description in the concept.', domain=[('applies_to', '=', 'uom')])
    l10n_mx_edi_code_aduana = fields.Char(
        'Customs code', help='Used in the complement of "Comercio Exterior" to'
        ' indicate in the products the UoM. It is based in the SAT catalog.')


class ProductSatCode(models.Model):
    """Product and UOM Codes from SAT Data.
    This code must be defined in CFDI 3.3, in each concept, and this is set
    by each product.
    Is defined a new catalog to only allow select the codes defined by the SAT
    that are load by data in the system.
    This catalog is found `here <https://goo.gl/iAUGEh>`_ in the page
    c_ClaveProdServ.

    This model also is used to define the uom code defined by the SAT
    """
    _name = 'l10n_mx_edi.product.sat.code'
    _description = "Product and UOM Codes from SAT Data"

    code = fields.Char(
        help='This value is required in CFDI version 3.3 to express the '
        'code of product or service covered by the present concept. Must be '
        'used a key from SAT catalog.', required=True)
    name = fields.Char(
        help='Name defined by SAT catalog to this product',
        required=True)
    applies_to = fields.Selection([
        ('product', 'Product'),
        ('uom', 'UoM'),
    ], required=True,
        help='Indicate if this code could be used in products or in UoM',)
    active = fields.Boolean(
        help='If this record is not active, this cannot be selected.',
        default=True)

    def name_get(self):
        result = []
        for prod in self:
            result.append((prod.id, "%s %s" % (prod.code, prod.name or '')))
        return result

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if operator == 'ilike' and not (name or '').strip():
            domain = []
        else:
            domain = ['|', ('name', 'ilike', name), ('code', 'ilike', name)]
        sat_code_ids = self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
        return models.lazy_name_get(self.browse(sat_code_ids).with_user(name_get_uid))


class L10nMXEdiTariffFraction(models.Model):
    _name = 'l10n_mx_edi.tariff.fraction'
    _description = "Mexican EDI Tariff Fraction"

    code = fields.Char(help='Code defined in the SAT to this record.')
    name = fields.Char(help='Name defined in the SAT catalog to this record.')
    uom_code = fields.Char(
        help='UoM code related with this tariff fraction. This value is '
        'defined in the SAT catalog and will be assigned in the attribute '
        '"UnidadAduana" in the merchandise.')
    active = fields.Boolean(
        help='If the tariff fraction has expired it could be disabled to '
        'do not allow select the record.', default=True)

    def name_get(self):
        result = []
        for tariff in self:
            result.append((tariff.id, "%s %s" % (
                tariff.code, tariff.name or '')))
        return result

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if operator == 'ilike' and not (name or '').strip():
            domain = []
        else:
            domain = ['|', ('name', 'ilike', name), ('code', 'ilike', name)]
        ids = self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
        return self.browse(ids).name_get()
