# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import math
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

PERIOD_RATIO = {
    'hour': 1,
    'day': 24,
    'week': 24 * 7
}


class RentalPricing(models.Model):
    """Rental pricing rules."""

    _name = 'rental.pricing'
    _description = 'Pricing rule of rentals'
    _order = 'price'

    duration = fields.Integer(
        string="Duration", required=True,
        help="Minimum duration before this rule is applied. If set to 0, it represents a fixed rental price.")
    unit = fields.Selection([("hour", "Hours"), ("day", "Days"), ("week", "Weeks"), ("month", "Months")], string="Unit", required=True, default='day')

    price = fields.Monetary(string="Price", required=True, digits='Product Price', default=1.0)
    currency_id = fields.Many2one(
        'res.currency', 'Currency',
        default=lambda self: self.env.company.currency_id.id,
        required=True)

    product_template_id = fields.Many2one(
        'product.template', string="Product Templates",
        help="Select products on which this pricing will be applied.")

    product_variant_ids = fields.Many2many(
        'product.product', string="Product Variants",
        help="Select Variants of the Product for which this rule applies."
        "\n Leave empty if this rule applies for any variant of this template.")
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')
    company_id = fields.Many2one('res.company', related='pricelist_id.company_id')

    @api.onchange('pricelist_id')
    def _onchange_pricelist_id(self):
        for pricing in self.filtered('pricelist_id'):
            pricing.currency_id = pricing.pricelist_id.currency_id

    def _compute_price(self, duration, unit):
        """Compute the price for a specified duration of the current pricing rule.

        :param float duration: duration in hours
        :param str unit: duration unit (hour, day, week)
        :return float: price
        """
        self.ensure_one()
        if duration <= 0 or self.duration <= 0:
            return self.price
        if unit != self.unit:
            if unit == 'month' or self.unit == 'month':
                raise ValidationError(_("Conversion between Months and another duration unit are not supported!"))
            converted_duration = math.ceil((duration * PERIOD_RATIO[unit]) / (self.duration * PERIOD_RATIO[self.unit]))
        else:
            converted_duration = math.ceil(duration / self.duration)
        return self.price * converted_duration

    def name_get(self):
        result = []
        uom_translation = dict()
        for key, value in self._fields['unit']._description_selection(self.env):
            uom_translation[key] = value
        for pricing in self:
            label = ""
            if pricing.currency_id.position == 'before':
                label += pricing.currency_id.symbol + str(pricing.price)
            else:
                label += str(pricing.price) + pricing.currency_id.symbol
            label += "/ %s" % uom_translation[pricing.unit]
            result.append((pricing.id, label))
        return result

    @api.model
    def _compute_duration_vals(self, pickup_date, return_date):
        duration = return_date - pickup_date
        vals = dict(hour=(duration.days * 24 + duration.seconds / 3600))
        vals['day'] = math.ceil(vals['hour'] / 24)
        vals['week'] = math.ceil(vals['day'] / 7)
        duration_diff = relativedelta(return_date, pickup_date)
        months = 1 if duration_diff.days or duration_diff.hours or duration_diff.minutes else 0
        months += duration_diff.months
        months += duration_diff.years * 12
        vals['month'] = months
        return vals

    _sql_constraints = [
        ('rental_pricing_duration',
            "CHECK(duration >= 0)",
            "The pricing duration has to be greater or equal to 0."),
        ('rental_pricing_price',
            "CHECK(price >= 0)",
            "The pricing price has to be greater or equal to 0."),
    ]

    def applies_to(self, product):
        """Check whether current pricing applies to given product.

        :param product.product product:
        :return: true if current pricing is applicable for given product, else otherwise.
        :rtype: bool
        """
        return (
            self.product_template_id == product.product_tmpl_id
            and (
                not self.product_variant_ids
                or product in self.product_variant_ids))
