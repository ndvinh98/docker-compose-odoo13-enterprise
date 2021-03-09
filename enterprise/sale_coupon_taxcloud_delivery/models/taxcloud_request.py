# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.sale_coupon_taxcloud.models.taxcloud_request import TaxCloudRequest


class TaxCloudRequest(TaxCloudRequest):
    """We want the delivery reward to be computed independently.
       With sale_coupon_delivery, delivery line are not discountable anymore.
       (Note that coupon and delivery can be installed without sale_coupon_delivery.)
    """

    def _rank_discount_line(self, line):
        res = super(TaxCloudRequest, self)._rank_discount_line(line)
        res.insert(0, line.coupon_program_id.reward_type != 'free_shipping')
        return res

    def _get_discountable_lines(self, discount_line, lines):
        lines = super(TaxCloudRequest, self)._get_discountable_lines(discount_line, lines)
        if discount_line.coupon_program_id.reward_type == 'free_shipping':
            lines = lines.filtered(lambda l: l._is_delivery())
        else:
            lines = lines.filtered(lambda l: not l._is_delivery())
        return lines
