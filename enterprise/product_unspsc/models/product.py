# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api
from odoo.osv import expression



class ProductTemplate(models.Model):
    _inherit = 'product.template'

    unspsc_code_id = fields.Many2one('product.unspsc.code', 'UNSPSC code', domain=[('applies_to', '=', 'product')],
        help='The UNSPSC code related to this product.  Used for edi in Colombia, Peru and Mexico')


class UomUom(models.Model):
    _inherit = 'uom.uom'

    unspsc_code_id = fields.Many2one('product.unspsc.code', 'UNSPSC code',
                                                domain=[('applies_to', '=', 'uom')],
                                                help='The UNSPSC code related to this UoM. ')


class ProductCode(models.Model):
    """Product and UoM codes defined by UNSPSC
    Used by Mexico, Peru and Colombia localizations
    """
    _name = 'product.unspsc.code'
    _description = "Product and UOM Codes from UNSPSC"

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', required=True)
    applies_to = fields.Selection([('product', 'Product'), ('uom', 'UoM'),], required=True,
        help='Indicate if this code could be used in products or in UoM',)
    active = fields.Boolean()

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
        unspsc_code_ids = self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
        return self.browse(unspsc_code_ids).name_get()