# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request

from odoo.addons.website_sale.controllers.main import WebsiteSale

class WebsiteSale(WebsiteSale):

    def _get_shop_payment_values(self, order, **kwargs):
        res = super(WebsiteSale, self)._get_shop_payment_values(order, **kwargs)
        res['on_payment_step'] = True

        return res

    @http.route(['/shop/payment'], type='http', auth="public", website=True)
    def payment(self, **post):
        response = super(WebsiteSale, self).payment(**post)
        order = request.website.sale_get_order()
        if order.fiscal_position_id.is_taxcloud:
            order.validate_taxes_on_sales_order()

        return response
