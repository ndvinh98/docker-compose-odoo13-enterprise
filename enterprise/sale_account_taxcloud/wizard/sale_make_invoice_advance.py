# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import api, models


class SaleAdvancePaymentInv(models.TransientModel):
    """Downpayment should have no taxes set on them.
       To that effect, we should get the category 'Gift card' (10005) on the
       deposit product. If this category cannot be found, either the user
       messed up with TaxCloud categories or did not configure them properly yet;
       in this case, the user is also responsible for configuring this properly.

       Otherwise, taxes are applied on downpayments, but not subtracted from the
       regular invoice, since we ignore negative lines, so get counted twice.
    """
    _inherit = "sale.advance.payment.inv"

    @api.model
    def _get_deposit_category(self):
        category = self.env['product.tic.category'].search([('code', '=', '10005')], limit=1)
        return category

    @api.model
    def _default_product_id(self):
        product = super(SaleAdvancePaymentInv, self)._default_product_id()
        deposit_category = self._get_deposit_category()
        if product and product.tic_category_id != deposit_category:
            product.tic_category_id = deposit_category
        return product

    def _prepare_deposit_product(self):
        product_dict = super(SaleAdvancePaymentInv, self)._prepare_deposit_product()
        product_dict.update(tic_category_id=self._get_deposit_category().id)
        return product_dict
