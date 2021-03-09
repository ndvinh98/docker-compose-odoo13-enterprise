# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class RentalWizard(models.TransientModel):
    _inherit = 'rental.wizard'

    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')

    product_uom_id = fields.Char(string="Product UoM", related='product_id.uom_id.name')

    # Stock availability
    rented_qty_during_period = fields.Float(
        string="Quantity reserved",
        help="Quantity reserved by other Rental lines during the given period",
        compute='_compute_rented_during_period')
    rentable_qty = fields.Float(
        string="Quantity available in stock for given period",
        compute='_compute_rentable_qty')

    # Serial number management (lots are disabled for Rental Products)
    tracking = fields.Selection(related='product_id.tracking')
    lot_ids = fields.Many2many(
        'stock.production.lot',
        string="Serial Numbers", help="Only available serial numbers are suggested",
        domain="[('id', 'not in', rented_lot_ids), ('id', 'in', rentable_lot_ids)]")
    rentable_lot_ids = fields.Many2many(
        'stock.production.lot',
        string="Serials available in Stock", compute='_compute_rentable_lots')
    rented_lot_ids = fields.Many2many(
        'stock.production.lot',
        string="Serials in rent for given period", compute='_compute_rented_during_period')

    # Rental Availability
    qty_available_during_period = fields.Float(
        string="Quantity available for given period (Stock - In Rent)",
        compute='_compute_rental_availability')

    is_product_storable = fields.Boolean(compute="_compute_is_product_storable")

    @api.depends('pickup_date', 'return_date', 'product_id', 'warehouse_id')
    def _compute_rented_during_period(self):
        for rent in self:
            if not rent.product_id or not rent.pickup_date or not rent.return_date:
                rent.rented_qty_during_period = 0.0
                rent.rented_lot_ids = False
                return
            fro, to = rent.product_id._unavailability_period(rent.pickup_date, rent.return_date)
            if rent.tracking != 'serial':
                rent.rented_qty_during_period = rent.product_id._get_unavailable_qty(
                    fro, to,
                    ignored_soline_id=rent.rental_order_line_id and rent.rental_order_line_id.id,
                    warehouse_id=rent.warehouse_id.id,
                )
                rent.rented_lot_ids = False
            else:
                rented_qty, rented_lots = rent.product_id._get_unavailable_qty_and_lots(
                    fro, to,
                    ignored_soline_id=rent.rental_order_line_id and rent.rental_order_line_id.id,
                    warehouse_id=rent.warehouse_id.id,
                )

                rent.rented_qty_during_period = rented_qty
                rent.rented_lot_ids = rented_lots

    @api.depends('pickup_date', 'return_date', 'product_id', 'warehouse_id')
    def _compute_rentable_qty(self):
        for rent in self:
            if rent.is_product_storable and rent.pickup_date and rent.return_date:
                reservation_begin, reservation_end = rent.product_id._unavailability_period(rent.pickup_date, rent.return_date)
                rent.rentable_qty = rent.product_id.with_context(
                    from_date=max(reservation_begin, fields.Datetime.now()),
                    to_date=reservation_end,
                    warehouse=rent.warehouse_id.id).qty_available
                if reservation_begin > fields.Datetime.now():
                    # Available qty at period t = available stock now + qty in rent now.
                    rent.rentable_qty += rent.product_id.with_context(warehouse_id=rent.warehouse_id.id).qty_in_rent
            else:
                rent.rentable_qty = 0

    @api.depends('product_id', 'warehouse_id')
    def _compute_rentable_lots(self):
        for rent in self:
            if rent.product_id and rent.tracking == 'serial':
                rentable_lots = self.env['stock.production.lot']._get_available_lots(rent.product_id, rent.warehouse_id.lot_stock_id)
                domain = [
                    ('is_rental', '=', True),
                    ('product_id', '=', rent.product_id.id),
                    ('order_id.rental_status', 'in', ['pickup', 'return']),
                    ('state', 'in', ['sale', 'done']),
                    ('id', '!=', rent.rental_order_line_id.id)]
                if rent.warehouse_id:
                    domain += [('order_id.warehouse_id', '=', rent.warehouse_id.id)]
                # Total of lots = lots available + lots currently picked-up.
                rentable_lots += self.env['sale.order.line'].search(domain).mapped('pickedup_lot_ids')
                rent.rentable_lot_ids = rentable_lots
            else:
                rent.rentable_lot_ids = self.env['stock.production.lot']

    @api.depends('quantity', 'rentable_qty', 'rented_qty_during_period')
    def _compute_rental_availability(self):
        for rent in self:
            rent.qty_available_during_period = max(rent.rentable_qty - rent.rented_qty_during_period, 0)

    @api.depends('product_id')
    def _compute_is_product_storable(self):
        """Product type ?= storable product."""
        for rent in self:
            rent.is_product_storable = rent.product_id and rent.product_id.type == "product"

    @api.onchange('lot_ids')
    def _onchange_lot_ids(self):
        if len(self.lot_ids) > self.quantity:
            self.quantity = len(self.lot_ids)

    @api.onchange('quantity')
    def _onchange_qty(self):
        """Remove last lots when qty is decreased."""
        if len(self.lot_ids) > self.quantity:
            self.lot_ids = self.lot_ids[:int(self.quantity)]

    @api.onchange('qty_available_during_period')
    def _onchange_qty_available_during_period(self):
        """If no quantity is available for given period, don't show any choice for the serial numbers."""
        if self.qty_available_during_period <= 0:
            return {
                'domain':
                {
                    'lot_ids': [(0, '=', 1)]
                }
            }
        else:
            return {
                'domain':
                {
                    'lot_ids': "['&', ('id', 'not in', rented_lot_ids), ('id', 'in', rentable_lot_ids)]"
                }
            }

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.lot_ids and self.lot_ids.mapped('product_id') != self.product_id:
            self.lot_ids = self.env['stock.production.lot']

    @api.constrains('product_id', 'rental_order_line_id')
    def _pickedup_product_no_change(self):
        if self.rental_order_line_id and self.product_id != self.rental_order_line_id.product_id and self.rental_order_line_id.qty_delivered > 0:
            raise ValidationError(_("You cannot change the product of a picked-up line."))
