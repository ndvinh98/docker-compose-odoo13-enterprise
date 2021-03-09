from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteSale(WebsiteSale):

    @http.route("/shop/ups_check_service_type", type='json', auth="public", website=True, sitemap=False)
    def ups_check_service_type_is_available(self, **post):
        return request.env['sale.order'].sudo().check_ups_service_type(post)

    @http.route("/shop/ups_carrier_account/set", type='http', auth="public", website=True, sitemap=False)
    def set_ups_carrier_account(self, **post):
        order = request.website.sale_get_order()
        # set ups bill my account data in sale order
        if order.carrier_id.ups_bill_my_account and post.get('ups_carrier_account'):
            # Update Quotation with ups_service_type and ups_carrier_account
            order.write({
                'ups_service_type': post['ups_service_type'],
                'ups_carrier_account': post['ups_carrier_account']
            })
        return request.redirect("/shop/payment")

    @http.route("/shop/ups_carrier_account/unset", type='http', auth="public", website=True, sitemap=False)
    def reset_ups_carrier_account(self, **post):
        order = request.website.sale_get_order()
        # remove ups bill my account data in sale order
        if order.ups_carrier_account:
            order.write({
                'ups_service_type': False,
                'ups_carrier_account': False
            })
        return request.redirect("/shop/payment")

    @http.route()
    def payment(self, **post):
        res = super(WebsiteSale, self).payment(**post)
        order = request.website.sale_get_order()
        if 'acquirers' not in res.qcontext:
            return res

        if not order.carrier_id.delivery_type == 'ups' or not order.carrier_id.ups_cod:
            res.qcontext['acquirers'] = [
                acquirer for acquirer in res.qcontext['acquirers'] if acquirer != request.env.ref('website_delivery_ups.payment_acquirer_ups_cod')
            ]
        else:
            res.qcontext['acquirers'] = [
                acquirer for acquirer in res.qcontext['acquirers'] if acquirer == request.env.ref('website_delivery_ups.payment_acquirer_ups_cod')
            ]
        return res
