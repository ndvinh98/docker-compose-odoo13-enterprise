# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class Product(models.Model):
    _inherit = 'product.product'

    @api.model
    def get_all_products_by_barcode(self):
        products = self.env['product.product'].search_read(
            [('barcode', '!=', None), ('type', '!=', 'service')],
            ['barcode', 'display_name', 'uom_id', 'tracking']
        )
        packagings = self.env['product.packaging'].search_read(
            [('barcode', '!=', None), ('product_id', '!=', None)],
            ['barcode', 'product_id', 'qty']
        )
        # for each packaging, grab the corresponding product data
        to_add = []
        to_read = []
        products_by_id = {product['id']: product for product in products}
        for packaging in packagings:
            if products_by_id.get(packaging['product_id']):
                product = products_by_id[packaging['product_id']]
                to_add.append(dict(product, **{'qty': packaging['qty']}))
            # if the product doesn't have a barcode, you need to read it directly in the DB
            to_read.append((packaging, packaging['product_id'][0]))
        products_to_read = self.env['product.product'].browse(list(set(t[1] for t in to_read))).sudo().read(['display_name', 'uom_id', 'tracking'])
        products_to_read = {product['id']: product for product in products_to_read}
        to_add.extend([dict(t[0], **products_to_read[t[1]]) for t in to_read])
        return {product.pop('barcode'): product for product in products + to_add}

    def read_product_and_package(self, lot_ids=False, fetch_product=False):
        """ Fetch product and/or package fields value used by the barcode app.

        :param lot_ids: list of `stock.production.lot` ids, used to retrieve package and owner
        :type lot_ids: list, optional
        :param fetch_product: set on True to read product's fields used by barcode.
        :type fetch_product: bool, optional

        :return: product and/or package info.
        :rtype: dict
        """
        res = {}
        if fetch_product:
            product = self.read(['display_name', 'uom_id', 'tracking'])
            res['product'] = product[0]
        if lot_ids:
            quant = self.env['stock.quant'].search_read(
                [
                    ('lot_id', 'in', lot_ids),
                    ('location_id.usage', '=', 'internal'),
                    ('product_id', '=', self.id),
                ],
                ['package_id', 'owner_id'],
                limit=1,
            )
            res['quant'] = quant[0]
        return res
