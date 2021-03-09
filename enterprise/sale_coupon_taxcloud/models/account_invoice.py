# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from .taxcloud_request import TaxCloudRequest
from odoo import api, models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _get_TaxCloudRequest(self, api_id, api_key):
        return TaxCloudRequest(api_id, api_key)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    coupon_program_id = fields.Many2one('sale.coupon.program',
        string='Discount Program', readonly=True,
        help='The coupon program that created this line.',
    )
    price_taxcloud = fields.Float('Taxcloud Price', default=0,
                                  help='Technical field to hold prices for TaxCloud.')

    def _get_taxcloud_price(self):
        self.ensure_one()
        return self.price_taxcloud
