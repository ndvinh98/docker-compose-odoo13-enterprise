# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
import math
from datetime import date

class RentalWizard(models.TransientModel):
    _name = 'rental.wizard'
    _description = 'Configure the rental of a product'

    def _default_uom_id(self):
        if self.env.context.get('default_uom_id', False):
            return self.env['uom.uom'].browse(self.context.get('default_uom_id'))
        else:
            return self.env['product.product'].browse(self.env.context.get('default_product_id')).uom_id

    rental_order_line_id = fields.Many2one('sale.order.line', ondelete='cascade')  # When wizard used to edit a Rental SO line

    product_id = fields.Many2one(
        'product.product', "Product", required=True, ondelete='cascade',
        domain=[('rent_ok', '=', True)], help="Product to rent (has to be rentable)")
    uom_id = fields.Many2one('uom.uom', 'Unit of Measure', readonly=True, default=_default_uom_id)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company.id, store=False)

    pickup_date = fields.Datetime(
        string="Pickup", required=True, help="Date of Pickup",
        default=lambda s: fields.Datetime.now() + relativedelta(minute=0, second=0, hours=1))
    return_date = fields.Datetime(
        string="Return", required=True, help="Date of Return",
        default=lambda s: fields.Datetime.now() + relativedelta(minute=0, second=0, hours=1, days=1))

    quantity = fields.Float("Quantity", default=1, required=True)  # Can be changed on SO line later if needed

    pricing_id = fields.Many2one(
        'rental.pricing', compute="_compute_pricing",
        string="Pricing", help="Best Pricing Rule based on duration")
    currency_id = fields.Many2one('res.currency', string="Currency", compute='_compute_displayed_currency')

    duration = fields.Integer(
        string="Duration", compute="_compute_duration",
        help="Duration of the rental (in unit of the pricing)")
    duration_unit = fields.Selection([("hour", "Hours"), ("day", "Days"), ("week", "Weeks"), ("month", "Months")],
                                     string="Unit", required=True, compute="_compute_duration")

    unit_price = fields.Monetary(
        string="Unit Price", help="This price is based on the rental price rule that gives the cheapest price for requested duration.",
        readonly=False, default=0.0, required=True)
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')

    pricing_explanation = fields.Html(string="Price Computation", help="Helper text to understand rental price computation.", compute="_compute_pricing_explanation")

    @api.depends('pickup_date', 'return_date')
    def _compute_pricing(self):
        self.pricing_id = False
        for wizard in self:
            if wizard.product_id:
                wizard.pricing_id = wizard.product_id._get_best_pricing_rule(
                    pickup_date=wizard.pickup_date,
                    return_date=wizard.return_date,
                    pricelist=wizard.pricelist_id,
                    company=wizard.company_id)

    @api.depends('pricelist_id', 'pricing_id')
    def _compute_displayed_currency(self):
        for wizard in self:
            wizard.currency_id = wizard.pricelist_id.currency_id or wizard.pricing_id.currency_id

    @api.depends('pricing_id', 'pickup_date', 'return_date')
    def _compute_duration(self):
        for wizard in self:
            values = {
                'duration_unit': 'day',
                'duration': 1.0,
            }
            if wizard.pickup_date and wizard.return_date:
                duration_dict = self.env['rental.pricing']._compute_duration_vals(wizard.pickup_date, wizard.return_date)
                if wizard.pricing_id:
                    values = {
                        'duration_unit': wizard.pricing_id.unit,
                        'duration': duration_dict[wizard.pricing_id.unit]
                    }
                else:
                    values = {
                        'duration_unit': 'day',
                        'duration': duration_dict['day']
                    }
            wizard.update(values)

    @api.onchange('pricing_id', 'currency_id', 'duration', 'duration_unit')
    def _compute_unit_price(self):
        for wizard in self:
            if wizard.pricing_id and wizard.duration > 0:
                unit_price = wizard.pricing_id._compute_price(wizard.duration, wizard.duration_unit)
                if wizard.currency_id != wizard.pricing_id.currency_id:
                    wizard.unit_price = wizard.pricing_id.currency_id._convert(
                        from_amount=unit_price,
                        to_currency=wizard.currency_id,
                        company=wizard.company_id,
                        date=date.today())
                else:
                    wizard.unit_price = unit_price
            elif wizard.duration > 0:
                wizard.unit_price = wizard.product_id.lst_price

    @api.depends('unit_price', 'pricing_id')
    def _compute_pricing_explanation(self):
        translated_pricing_duration_unit = dict()
        for key, value in self.pricing_id._fields['unit']._description_selection(self.env):
            translated_pricing_duration_unit[key] = value
        for wizard in self:
            if wizard.pricing_id and wizard.duration > 0 and wizard.unit_price != 0.0:
                if wizard.pricing_id.duration > 0:
                    pricing_explanation = "%i * %i %s (%s)" % (
                        math.ceil(wizard.duration / wizard.pricing_id.duration),
                        wizard.pricing_id.duration,
                        translated_pricing_duration_unit[wizard.pricing_id.unit],
                        self.env['ir.qweb.field.monetary'].value_to_html(
                            wizard.pricing_id.price, {
                                'from_currency': wizard.pricing_id.currency_id,
                                'display_currency': wizard.pricing_id.currency_id,
                                'company_id': self.env.company.id,
                            }))
                else:
                    pricing_explanation = _("Fixed rental price")
                if wizard.product_id.extra_hourly or wizard.product_id.extra_daily:
                    pricing_explanation += "<br/>%s" % (_("Extras:"))
                if wizard.product_id.extra_hourly:
                    pricing_explanation += " %s%s" % (
                        self.env['ir.qweb.field.monetary'].value_to_html(
                            wizard.product_id.extra_hourly, {
                                'from_currency': wizard.product_id.currency_id,
                                'display_currency': wizard.product_id.currency_id,
                                'company_id': self.env.company.id,
                            }),
                        _("/hour"))
                if wizard.product_id.extra_daily:
                    pricing_explanation += " %s%s" % (
                        self.env['ir.qweb.field.monetary'].value_to_html(
                            wizard.product_id.extra_daily, {
                                'from_currency': wizard.product_id.currency_id,
                                'display_currency': wizard.product_id.currency_id,
                                'company_id': self.env.company.id,
                            }),
                        _("/day"))
                wizard.pricing_explanation = pricing_explanation
            else:
                # if no pricing on product: explain only sales price is applied ?
                if not wizard.product_id.rental_pricing_ids and wizard.duration:
                    wizard.pricing_explanation = _("No rental price is defined on the product.\nThe price used is the sales price.")
                else:
                    wizard.pricing_explanation = ""

    _sql_constraints = [
        ('rental_period_coherence',
            "CHECK(pickup_date < return_date)",
            "Please choose a return date that is after the pickup date."),
    ]
