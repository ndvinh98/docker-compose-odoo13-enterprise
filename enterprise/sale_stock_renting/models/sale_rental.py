# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class RentalOrderLine(models.Model):
    _inherit = 'sale.order.line'

    tracking = fields.Selection(related='product_id.tracking')

    reserved_lot_ids = fields.Many2many('stock.production.lot', 'rental_reserved_lot_rel', domain="[('product_id','=',product_id)]", copy=False)
    pickedup_lot_ids = fields.Many2many('stock.production.lot', 'rental_pickedup_lot_rel', domain="[('product_id','=',product_id)]", copy=False)
    returned_lot_ids = fields.Many2many('stock.production.lot', 'rental_returned_lot_rel', domain="[('product_id','=',product_id)]", copy=False)

    unavailable_lot_ids = fields.Many2many('stock.production.lot', 'unreturned_reserved_serial', compute='_compute_unavailable_lots', store=False)

    @api.model
    def write(self, vals):
        """Move product quantities on pickup/return in case of rental orders.

        When qty_delivered or qty_returned are changed (and/or pickedup_lot_ids/returned_lot_ids),
        we need to move those quants to make sure they aren't seen as available in the stock.
        For quantities, the quantity is requested in the warehouse (self.order_id.warehouse_id) through stock move generation.
        For serial numbers(lots), lots are found one by one and then a stock move is generated based on the quant location itself.

        The destination location is the independent internal location of the company dedicated to stock in rental, to still count
        in inventory valuation and company assets.

        When quantity/lots are decreased/removed, we decrease the quantity in the stock moves made by previous corresponding write call.
        """
        if not any(key in vals for key in ['qty_delivered', 'pickedup_lot_ids', 'qty_returned', 'returned_lot_ids']):
            # If nothing to catch for rental: usual write behavior
            return super(RentalOrderLine, self).write(vals)

        # TODO add context for disabling stock moves in write ?
        old_vals = dict()
        movable_confirmed_rental_lines = self.filtered(lambda sol: sol.is_rental and sol.state in ['sale', 'done'] and sol.product_id.type in ["product", "consu"])
        for sol in movable_confirmed_rental_lines:
            old_vals[sol.id] = (sol.pickedup_lot_ids, sol.returned_lot_ids) if sol.product_id.tracking == 'serial' else (sol.qty_delivered, sol.qty_returned)
            if vals.get('pickedup_lot_ids', False) and vals['pickedup_lot_ids'][0][0] == 6:
                pickedup_lot_ids = vals['pickedup_lot_ids'][0][2]
                if sol.product_uom_qty == len(pickedup_lot_ids) and pickedup_lot_ids != sol.reserved_lot_ids.ids:
                    """ When setting the pickedup_lots:
                    If the total reserved quantity is picked_up we need to unreserve
                    the reserved_lots not picked to ensure the consistency of rental reservations.
                    NOTE : This is only guaranteed for generic 6, _, _ orm magic commands.
                    """
                    vals['reserved_lot_ids'] = vals['pickedup_lot_ids']

        res = super(RentalOrderLine, self).write(vals)
        if not movable_confirmed_rental_lines:
            return res

        movable_confirmed_rental_lines.mapped('company_id').filtered(lambda company: not company.rental_loc_id)._create_rental_location()
        # to undo stock moves partially: what if location has changed? :x
        # can we ascertain the warehouse_id.lot_stock_id of a sale.order doesn't change???

        for sol in movable_confirmed_rental_lines:
            rented_location = sol.company_id.rental_loc_id
            stock_location = sol.order_id.warehouse_id.lot_stock_id
            if sol.product_id.tracking == 'serial' and (vals.get('pickedup_lot_ids', False) or vals.get('returned_lot_ids', False)):
                # for product tracked by serial numbers: move the lots
                if vals.get('pickedup_lot_ids', False):
                    pickedup_lots = sol.pickedup_lot_ids - old_vals[sol.id][0]
                    removed_pickedup_lots = old_vals[sol.id][0] - sol.pickedup_lot_ids
                    sol._move_serials(pickedup_lots, stock_location, rented_location)
                    sol._return_serials(removed_pickedup_lots, rented_location, stock_location)
                if vals.get('returned_lot_ids', False):
                    returned_lots = sol.returned_lot_ids - old_vals[sol.id][1]
                    removed_returned_lots = old_vals[sol.id][1] - sol.returned_lot_ids
                    sol._move_serials(returned_lots, rented_location, stock_location)
                    sol._return_serials(removed_returned_lots, stock_location, rented_location)
            elif sol.product_id.tracking != 'serial' and (vals.get('qty_delivered', False) or vals.get('qty_returned', False)):
                # for products not tracked : move quantities
                qty_delivered_change = sol.qty_delivered - old_vals[sol.id][0]
                qty_returned_change = sol.qty_returned - old_vals[sol.id][1]
                if qty_delivered_change > 0:
                    sol._move_qty(qty_delivered_change, stock_location, rented_location)
                elif qty_delivered_change < 0:
                    sol._return_qty(-qty_delivered_change, stock_location, rented_location)

                if qty_returned_change > 0.0:
                    sol._move_qty(qty_returned_change, rented_location, stock_location)
                elif qty_returned_change < 0.0:
                    sol._return_qty(-qty_returned_change, rented_location, stock_location)

        # TODO constraint s.t. qty_returned cannot be > than qty_delivered (and same for lots)
        return res

    def _move_serials(self, lot_ids, location_id, location_dest_id):
        """Move the given lots from location_id to location_dest_id.

        :param stock.production.lot lot_ids:
        :param stock.location location_id:
        :param stock.location location_dest_id:
        """
        if not lot_ids:
            return
        rental_stock_move = self.env['stock.move'].create({
            'product_id': self.product_id.id,
            'product_uom_qty': len(lot_ids),
            'product_uom': self.product_id.uom_id.id,
            'location_id': location_id.id,
            'location_dest_id': location_dest_id.id,
            'partner_id': self.order_partner_id.id,
            'sale_line_id': self.id,
            'name': _("Rental move :") + " %s" % (self.order_id.name),
        })

        for lot_id in lot_ids:
            lot_quant = self.env['stock.quant']._gather(self.product_id, location_id, lot_id)
            lot_quant = lot_quant.filtered(lambda quant: quant.quantity == 1.0)
            if not lot_quant:
                raise ValidationError(_("No valid quant has been found in location %s for serial number %s !") % (location_id.name, lot_id.name))
                # Best fallback strategy??
                # Make a stock move without specifying quants and lots?
                # Let the move be created with the erroneous quant???
            # As we are using serial numbers, only one quant is expected
            ml = self.env['stock.move.line'].create(rental_stock_move._prepare_move_line_vals(reserved_quant=lot_quant))
            ml['qty_done'] = 1

        rental_stock_move._action_done()

    def _return_serials(self, lot_ids, location_id, location_dest_id):
        """Undo the move of lot_ids from location_id to location_dest_id.

        :param stock.production.lot lot_ids:
        :param stock.location location_id:
        :param stock.location location_dest_id:
        """
        # VFE NOTE : or use stock moves to undo return/pickups ???
        if not lot_ids:
            return
        rental_stock_move = self.env['stock.move'].search([
            ('sale_line_id', '=', self.id),
            ('location_id', '=', location_id.id),
            ('location_dest_id', '=', location_dest_id.id)
        ])
        for ml in rental_stock_move.mapped('move_line_ids'):
            # update move lines qties.
            if ml.lot_id.id in lot_ids:
                ml.qty_done = 0.0

        rental_stock_move.product_uom_qty -= len(lot_ids)

    def _move_qty(self, qty, location_id, location_dest_id):
        """Move qty from location_id to location_dest_id.

        :param float qty:
        :param stock.location location_id:
        :param stock.location location_dest_id:
        """
        rental_stock_move = self.env['stock.move'].create({
            'product_id': self.product_id.id,
            'product_uom_qty': qty,
            'product_uom': self.product_id.uom_id.id,
            'location_id': location_id.id,
            'location_dest_id': location_dest_id.id,
            'partner_id': self.order_partner_id.id,
            'sale_line_id': self.id,
            'name': _("Rental move :") + " %s" % (self.order_id.name),
            'state': 'confirmed',
        })
        rental_stock_move._action_assign()
        rental_stock_move._set_quantity_done(qty)
        rental_stock_move._action_done()

    def _return_qty(self, qty, location_id, location_dest_id):
        """Undo a qty move (partially or totally depending on qty).

        :param float qty:
        :param stock.location location_id:
        :param stock.location location_dest_id:
        """
        # VFE NOTE : or use stock moves to undo return/pickups ???
        rental_stock_move = self.env['stock.move'].search([
            ('sale_line_id', '=', self.id),
            ('location_id', '=', location_id.id),
            ('location_dest_id', '=', location_dest_id.id)
        ], order='date desc')

        for ml in rental_stock_move.mapped('move_line_ids'):
            # update move lines qties.
            qty -= ml.qty_done
            ml.qty_done = 0.0 if qty > 0.0 else -qty

            if qty <= 0.0:
                return True
                # TODO ? ml.move_id.product_uom_qty -= decrease of qty

        return qty <= 0.0

    @api.depends('product_id')
    def _compute_qty_delivered_method(self):
        """Allow modification of delivered qty without depending on stock moves."""
        super(RentalOrderLine, self)._compute_qty_delivered_method()

        for line in self:
            if line.is_rental:
                line.qty_delivered_method = 'manual'

    def _compute_qty_to_deliver(self):
        """Don't show inventory widget for rental order lines."""
        super(RentalOrderLine, self.filtered(lambda sol: not sol.is_rental))._compute_qty_to_deliver()
        self.filtered('is_rental').write({
            'qty_to_deliver': 0.0,
            'display_qty_widget': False,
        })

    @api.constrains('product_id')
    def _stock_consistency(self):
        for line in self.filtered('is_rental'):
            moves = line.move_ids.filtered(lambda m: m.state != 'cancel')
            if moves and moves.mapped('product_id') != line.product_id:
                raise ValidationError("You cannot change the product of lines linked to stock moves.")

    def _check_availability(self, product_id):
        """No current stock warning for rental lines."""
        if not self.order_id.is_rental_order or not product_id.rent_ok:
            return super(RentalOrderLine, self)._check_availability(product_id)
        else:
            return {}  # Rental availability computation?

    def _onchange_product_uom_qty(self):
        if not self.is_rental:
            return super(RentalOrderLine, self)._onchange_product_uom_qty()

    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """Disable stock moves for rental order lines.

        Stock moves for rental orders are created on pickup/return.
        The rental reservations are not propagated in the stock until
        the effective pickup or returns.
        """
        other_lines = self.filtered(lambda sol: not sol.is_rental)
        super(RentalOrderLine, other_lines)._action_launch_stock_rule(previous_product_uom_qty)

    @api.depends('pickedup_lot_ids', 'returned_lot_ids', 'reserved_lot_ids')
    def _compute_unavailable_lots(self):
        """Unavailable lots = reserved_lots U pickedup_lots - returned_lots."""
        for line in self:
            line.unavailable_lot_ids = (line.reserved_lot_ids | line.pickedup_lot_ids) - line.returned_lot_ids

    @api.depends('pickup_date')
    def _compute_reservation_begin(self):
        lines = self.filtered(lambda line: line.is_rental)
        for line in lines:
            padding_timedelta_before = timedelta(hours=line.product_id.preparation_time)
            line.reservation_begin = line.pickup_date - padding_timedelta_before
        (self - lines).reservation_begin = None
