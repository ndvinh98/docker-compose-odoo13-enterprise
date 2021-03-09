# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_done(self):
        results = []
        for rec in self:
            result = super(StockPicking, self).action_done()
            rec._ebay_update_carrier(transfered=True)
            results.append(result)
        return results

    def _ebay_update_carrier(self, transfered=False):
        for picking in self:
            so = self.env['sale.order'].search([('name', '=', picking.origin), ('origin', 'like', 'eBay')])
            if so.order_line.filtered(lambda line: line.product_id.product_tmpl_id.ebay_use):
                call_data = {
                    'OrderLineItemID': so.client_order_ref,
                }
                if transfered:
                    call_data['Shipped'] = True
                if picking.carrier_tracking_ref and picking.carrier_id:
                    call_data['Shipment'] = {
                        'ShipmentTrackingDetails': {
                            'ShipmentTrackingNumber': picking.carrier_tracking_ref,
                            'ShippingCarrierUsed': picking.carrier_id.name,
                        },
                    }
                self.env['product.template'].ebay_execute("CompleteSale", call_data)
