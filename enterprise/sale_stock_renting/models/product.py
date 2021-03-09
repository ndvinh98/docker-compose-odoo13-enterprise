# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta
from odoo import api, fields, models, exceptions


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Padding Time

    preparation_time = fields.Float(string="Security Time", company_dependent=True,
                                    help="Temporarily make this product unavailable before pickup.")

    # TODO replace by UI greying of unselectable conflicting choices ?
    @api.constrains('rent_ok', 'tracking')
    def _lot_not_supported_rental(self):
        for template in self:
            if template.rent_ok and template.tracking == 'lot':
                raise exceptions.ValidationError("Tracking by lots isn't supported for rental products. \
                    \n You should rather change the tracking mode to unique serial numbers.")


class Product(models.Model):
    _inherit = 'product.product'

    def _get_qty_in_rent_domain(self):
        """Allow precising the warehouse_id to get qty currently in rent."""
        if self.env.context.get('warehouse_id', False):
            return super(Product, self)._get_qty_in_rent_domain() + [('order_id.warehouse_id', '=', int(self.env.context.get('warehouse_id')))]
        else:
            return super(Product, self)._get_qty_in_rent_domain()

    def _unavailability_period(self, fro, to):
        """Give unavailability period given rental period."""
        return fro - timedelta(hours=self.preparation_time), to

    def _get_unavailable_qty(self, fro, to=None, **kwargs):
        """Return max qty of self (unique) unavailable between fro and to.

        Doesn't count already returned quantities.
        :param datetime fro:
        :param datetime to:
        :param dict kwargs: search domain restrictions (ignored_soline_id, warehouse_id)
        """
        def unavailable_qty(so_line):
            return so_line.product_uom_qty - so_line.qty_returned

        begins_during_period, ends_during_period, covers_period = self._get_active_rental_lines(fro, to, **kwargs)
        active_lines_in_period = begins_during_period + ends_during_period
        max_qty_rented = 0

        # TODO is it more efficient to filter the records active in period
        # or to make another search on all the sale order lines???
        if active_lines_in_period:
            for date in (begins_during_period.mapped('reservation_begin') + [fro]):
                # If no soline in begins_during_period, we need to check at period beginning
                # how much products are rented.
                active_lines_at_date = active_lines_in_period.filtered(
                    lambda line: line.reservation_begin <= date and line.return_date >= date)
                qty_rented_at_date = sum(active_lines_at_date.mapped(unavailable_qty))
                if qty_rented_at_date > max_qty_rented:
                    max_qty_rented = qty_rented_at_date

        qty_always_in_rent_during_period = sum(covers_period.mapped(unavailable_qty)) if covers_period else 0

        return max_qty_rented + qty_always_in_rent_during_period

    def _get_active_rental_lines(self, fro, to, **kwargs):
        self.ensure_one()

        Reservation = self.env['sale.order.line']
        domain = [
            ('is_rental', '=', True),
            ('product_id', '=', self.id),
            ('state', 'in', ['sale', 'done']),
        ]

        ignored_soline_id = kwargs.get('ignored_soline_id', False)
        if ignored_soline_id:
            domain += [('id', '!=', ignored_soline_id)]

        warehouse_id = kwargs.get('warehouse_id', False)
        if warehouse_id:
            domain += [('order_id.warehouse_id', '=', warehouse_id)]

        if not to or fro == to:
            active_lines_at_time_fro = Reservation.search(domain + [
                ('reservation_begin', '<=', fro),
                ('return_date', '>=', fro)
            ])
            return [], [], active_lines_at_time_fro
        else:
            begins_during_period = Reservation.search(domain + [
                ('reservation_begin', '>', fro),
                ('reservation_begin', '<', to)])
            ends_during_period = Reservation.search(domain + [
                ('return_date', '>', fro),
                ('return_date', '<', to),
                ('id', 'not in', begins_during_period.ids)])
            covers_period = Reservation.search(domain + [
                ('reservation_begin', '<=', fro),
                ('return_date', '>=', to)])
            return begins_during_period, ends_during_period, covers_period

    """
        Products with tracking (by serial number)
    """

    def _get_unavailable_lots(self, fro=fields.Datetime.now(), to=None, **kwargs):
        begins_during_period, ends_during_period, covers_period = self._get_active_rental_lines(fro, to, **kwargs)
        return (begins_during_period + ends_during_period + covers_period).mapped('unavailable_lot_ids')

    def _get_unavailable_qty_and_lots(self, fro, to, **kwargs):
        """
        :param datetime fro:
        :param datetime to:
        :param dict kwargs: search domain restrictions (ignored_soline_id, warehouse_id)
        :return tuple(float, array(stock.production.lot)):
        """
        def unavailable_qty(so_line):
            return so_line.product_uom_qty - so_line.qty_returned

        begins_during_period, ends_during_period, covers_period = self._get_active_rental_lines(fro, to, **kwargs)
        active_lines_in_period = begins_during_period + ends_during_period
        max_qty_rented = 0

        # TODO is it more efficient to filter the records active in period
        # or to make another search on all the sale order lines???
        if begins_during_period:
            for date in begins_during_period.mapped('reservation_begin'):
                active_lines_at_date = active_lines_in_period.filtered(
                    lambda line: line.reservation_begin <= date and line.return_date >= date)
                qty_rented_at_date = sum(active_lines_at_date.mapped(unavailable_qty))
                if qty_rented_at_date > max_qty_rented:
                    max_qty_rented = qty_rented_at_date

        qty_always_in_rent_during_period = sum(covers_period.mapped(unavailable_qty))

        # returns are removed from the count (WARNING : early returns don't support padding times)
        all_lines = (active_lines_in_period + covers_period)
        rented_serial_during_period = all_lines.mapped('unavailable_lot_ids')

        return max_qty_rented + qty_always_in_rent_during_period, rented_serial_during_period
