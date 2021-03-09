# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date
from odoo import api, fields, models, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    rent_ok = fields.Boolean(
        string="Can be Rented",
        help="Allow renting of this product.")
    qty_in_rent = fields.Float("Quantity currently in rent", compute='_get_qty_in_rent')
    rental_pricing_ids = fields.One2many(
        'rental.pricing', 'product_template_id',
        string="Rental Pricings", auto_join=True, copy=True)
    display_price = fields.Char(
        "Rental price", help="First rental pricing of the product",
        compute="_compute_display_price")

    # Delays pricing

    extra_hourly = fields.Float("Extra Hour", help="Fine by hour overdue", company_dependent=True)
    extra_daily = fields.Float("Extra Day", help="Fine by day overdue", company_dependent=True)

    def _compute_visible_qty_configurator(self):
        super(ProductTemplate, self)._compute_visible_qty_configurator()
        for product_template in self:
            if len(product_template.product_variant_ids) > 1 and product_template.rent_ok:
                product_template.visible_qty_configurator = False

    def _get_qty_in_rent(self):
        rentable = self.filtered('rent_ok')
        not_rentable = self - rentable
        not_rentable.update({'qty_in_rent': 0.0})
        for template in rentable:
            template.qty_in_rent = sum(template.mapped('product_variant_ids.qty_in_rent'))

    def _compute_display_price(self):
        rentable_products = self.filtered('rent_ok')
        rental_priced_products = rentable_products.filtered('rental_pricing_ids')
        (self - rentable_products).display_price = ""
        (rentable_products - rental_priced_products).display_price = _("Fallback on Sales price")
        # No rental pricing defined, fallback on list price
        for product in rental_priced_products:
            product.display_price = product.rental_pricing_ids[0].display_name

    def action_view_rentals(self):
        """Access Gantt view of rentals (sale.rental.schedule), filtered on variants of the current template."""
        return {
            "type": "ir.actions.act_window",
            "name": _("Scheduled Rentals"),
            "res_model": "sale.rental.schedule",
            "views": [[False, "gantt"]],
            'domain': [('product_id', 'in', self.mapped('product_variant_ids').ids)],
            'context': {'search_default_Rentals':1, 'group_by_no_leaf':1,'group_by':[], 'restrict_renting_products': True}
        }

    def name_get(self):
        res_names = super(ProductTemplate, self).name_get()
        if not self._context.get('rental_products'):
            return res_names
        result = []
        rental_product_ids = self.filtered(lambda p: p.rent_ok).ids
        for res in res_names:
            result.append((res[0], res[0] in rental_product_ids and "%s %s" % (res[1], _("(Rental)")) or res[1]))
        return result


class ProductProduct(models.Model):
    _inherit = 'product.product'

    qty_in_rent = fields.Float("Quantity currently in rent", compute='_get_qty_in_rent')

    def name_get(self):
        res_names = super(ProductProduct, self).name_get()
        if not self._context.get('rental_products'):
            return res_names
        result = []
        rental_product_ids = self.filtered(lambda p: p.rent_ok).ids
        for res in res_names:
            result.append((res[0], res[0] in rental_product_ids and "%s %s" % (res[1], _("(Rental)")) or res[1]))
        return result

    def _get_qty_in_rent_domain(self):
        return [
            ('is_rental', '=', True),
            ('product_id', 'in', self.ids),
            ('state', 'in', ['sale', 'done'])]

    def _get_qty_in_rent(self):
        """
        Note: we don't use product.with_context(location=self.env.company.rental_loc_id.id).qty_available
        because there are no stock moves for services (which can be rented).
        """
        active_rental_lines = self.env['sale.order.line'].read_group(
            domain=self._get_qty_in_rent_domain(),
            fields=['product_id', 'qty_delivered:sum', 'qty_returned:sum'],
            groupby=['product_id'],
        )
        res = dict((data['product_id'][0], data['qty_delivered'] - data['qty_returned']) for data in active_rental_lines)
        for product in self:
            product.qty_in_rent = res.get(product.id, 0)

    def _compute_delay_price(self, duration):
        """Compute daily and hourly delay price.

        :param timedelta duration: datetime representing the delay.
        """
        days = duration.days
        hours = duration.seconds // 3600
        return days * self.extra_daily + hours * self.extra_hourly

    def _get_best_pricing_rule(self, **kwargs):
        """Return the best pricing rule for the given duration.

        :param float duration: duration, in unit uom
        :param str unit: duration unit (hour, day, week)
        :param datetime pickup_date:
        :param datetime return_date:
        :return: least expensive pricing rule for given duration
        :rtype: rental.pricing
        """
        self.ensure_one()
        best_pricing_rule = self.env['rental.pricing']
        if not self.rental_pricing_ids:
            return best_pricing_rule
        pickup_date, return_date = kwargs.get('pickup_date', False), kwargs.get('return_date', False)
        duration, unit = kwargs.get('duration', False), kwargs.get('unit', '')
        pricelist = kwargs.get('pricelist', self.env['product.pricelist'])
        currency = kwargs.get('currency', self.env.company.currency_id)
        company = kwargs.get('company', self.env.company)
        if pickup_date and return_date:
            duration_dict = self.env['rental.pricing']._compute_duration_vals(pickup_date, return_date)
        elif not(duration and unit):
            return best_pricing_rule  # no valid input to compute duration.
        min_price = float("inf")  # positive infinity
        available_pricings = self.rental_pricing_ids.filtered(
            lambda p: p.pricelist_id == pricelist
        )
        if not available_pricings:
            # If no pricing is defined for given pricelist:
            # fallback on generic pricings
            available_pricings = self.rental_pricing_ids.filtered(
                lambda p: not p.pricelist_id
            )
        for pricing in available_pricings:
            if pricing.applies_to(self):
                if duration and unit:
                    price = pricing._compute_price(duration, unit)
                else:
                    price = pricing._compute_price(duration_dict[pricing.unit], pricing.unit)

                if pricing.currency_id != currency:
                    price = pricing.currency_id._convert(
                        from_amount=price,
                        to_currency=currency,
                        company=company,
                        date=date.today(),
                    )

                if price < min_price:
                    min_price, best_pricing_rule = price, pricing
        return best_pricing_rule

    def action_view_rentals(self):
        """Access Gantt view of rentals (sale.rental.schedule), filtered on variants of the current template."""
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.rental.schedule",
            "name": _("Scheduled Rentals"),
            "views": [[False, "gantt"]],
            'domain': [('product_id', 'in', self.ids)],
            'context': {'search_default_Rentals':1, 'group_by_no_leaf':1,'group_by':[], 'restrict_renting_products': True}
        }
