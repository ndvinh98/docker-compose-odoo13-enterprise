# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request

from odoo.addons.website_sale.controllers.main import WebsiteSale

class WebsiteSaleTaxcloudDelivery(WebsiteSale):

    @http.route(['/shop/payment'], type='http', auth="public", website=True)
    def payment(self, **post):
        order = request.website.sale_get_order()
        if order.fiscal_position_id.is_taxcloud:
            order.validate_taxes_on_sales_order()

        return super(WebsiteSaleTaxcloudDelivery, self).payment(**post)

    def _update_website_sale_delivery_return(self, order, **post):
        if order and order.fiscal_position_id.is_taxcloud:
            order.validate_taxes_on_sales_order()
        return super(WebsiteSaleTaxcloudDelivery, self)._update_website_sale_delivery_return(order, **post)
