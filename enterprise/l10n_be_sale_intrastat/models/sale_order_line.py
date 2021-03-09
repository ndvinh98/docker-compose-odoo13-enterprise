# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _prepare_invoice_line(self):
        invoice_line = super(SaleOrderLine, self)._prepare_invoice_line()
        invoice_line['intrastat_product_origin_country_id'] = self.product_id.intrastat_origin_country_id.id
        return invoice_line
