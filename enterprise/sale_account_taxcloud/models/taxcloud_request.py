# -*- coding: utf-8 -*-

from odoo.addons.account_taxcloud.models.taxcloud_request import TaxCloudRequest

class TaxCloudRequest(TaxCloudRequest):

    def set_order_items_detail(self, order):
        self.cart_items = self.factory.ArrayOfCartItem()
        self.cart_items.CartItem = self._process_lines(order.order_line)
