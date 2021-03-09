# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AmazonOffer(models.Model):
    _name = 'amazon.offer'
    _description = "Amazon Offer"

    def _default_marketplace(self):
        """ Return the single marketplace of this offer's account if it exists. """
        account_id = self.env.context.get('default_account_id')
        if account_id:
            marketplaces = self.env['amazon.account'].browse([account_id]).active_marketplace_ids
            return len(marketplaces) == 1 and marketplaces[0]

    account_id = fields.Many2one(
        'amazon.account', "Account", help='The seller account used to manage this product',
        required=True, ondelete='cascade')  # Default account provided in context of list view
    company_id = fields.Many2one(related='account_id.company_id', readonly=True)
    active_marketplace_ids = fields.Many2many(related='account_id.active_marketplace_ids')
    marketplace_id = fields.Many2one(
        'amazon.marketplace', "Marketplace", help="The marketplace of this offer", required=True,
        default=_default_marketplace, domain="[('id', 'in', active_marketplace_ids)]")
    domain = fields.Char(related='marketplace_id.domain', store=True, readonly=True)
    product_id = fields.Many2one('product.product', "Product", required=True, ondelete='cascade')
    product_template_id = fields.Many2one(
        related="product_id.product_tmpl_id", store=True, readonly=True)
    sku = fields.Char("SKU", help="The Stock Keeping Unit", required=True)

    _sql_constraints = [(
        'unique_sku',
        'UNIQUE(account_id, marketplace_id, sku)',
        "SKU must be unique for a given account and marketplace."
    )]

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """ Set the SKU to the internal reference of the product if it exists. """
        for offer in self:
            offer.sku = offer.product_id.default_code

    def action_view_online(self):
        self.ensure_one()
        url = "https://sellercentral.%s/skucentral?mSku=%s" % \
              (self.marketplace_id.domain.lower(), self.sku)
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
