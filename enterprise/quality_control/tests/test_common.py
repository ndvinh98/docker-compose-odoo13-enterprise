# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import common


class TestQualityCommon(common.TransactionCase):

    def setUp(self):
        super(TestQualityCommon, self).setUp()

        self.product = self.env.ref('product.product_delivery_01')
        self.product_tmpl_id = self.ref('product.product_delivery_01_product_template')
        self.partner_id = self.ref('base.res_partner_4')
        self.picking_type_id = self.ref('stock.picking_type_in')
        self.location_id = self.ref('stock.stock_location_suppliers')
        self.location_dest_id = self.ref('stock.stock_location_stock')
