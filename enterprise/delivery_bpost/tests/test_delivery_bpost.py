# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged, Form

_logger = logging.getLogger(__name__)

@tagged('-standard', 'external')
class TestDeliveryBpost(TransactionCase):

    def setUp(self):
        super(TestDeliveryBpost, self).setUp()

        self.your_company = self.env.ref('base.main_partner')
        self.your_company.write({'name': 'Odoo SA',
                                 'country_id': self.env.ref('base.be').id,
                                 'street': 'Chaussée de Namur 40',
                                 'street2': False,
                                 'state_id': False,
                                 'city': 'Ramillies',
                                 'zip': 1367,
                                 'phone': '081813700',
                                 'vat': 'BE0477472701'
                                 })
        # "country_id" has to be changed in another write than "vat",
        # else "vat" field is not copied on children partners and can
        # cause exception when VAT numbers validation is enabled
        self.your_company.write({'country_id': self.env.ref('base.be').id})

        self.agrolait = self.env.ref('base.res_partner_2')
        self.agrolait.write({'name': 'Odoo Brussels',
                             'street': 'Avenue Edmond Van Nieuwenhuyse 6',
                             'street2': False,
                             'state_id': False,
                             'city': 'Auderghem',
                             'zip': 1160,
                             'country_id': self.env.ref('base.be').id,
                             'phone': '022903490'})
        self.think_big_system = self.env.ref('base.res_partner_18')
        self.think_big_system.write({'name': "Palais de l'Élysee",
                                 'street': '55 Rue du Faubourg Saint-Honoré',
                                 'street2': False,
                                 'state_id': False,
                                 'city': 'Paris VIII',
                                 'zip': 75008,
                                 'country_id': self.env.ref('base.fr').id,
                                 'phone': '0142928100'})
        self.odooinc = self.env['res.partner'].create({'name': "Odoo Inc.",
                                 'is_company': True,
                                 'street': '1485 Bayshore Blvd',
                                 'street2': 'Suite 450',
                                 'state_id': self.env.ref('base.state_us_5').id,
                                 'city': 'San Francisco',
                                 'zip': 94124,
                                 'country_id': self.env.ref('base.us').id,
                                 'phone': '+1 (650) 691-3277  '})
        self.iPadMini = self.env.ref('product.product_product_6')
        self.uom_unit = self.env.ref('uom.product_uom_unit')
        self.stock_location = self.env.ref('stock.stock_location_stock')
        self.customer_location = self.env.ref('stock.stock_location_customers')

    def test_01_bpost_basic_be_domestic_flow(self):
        SaleOrder = self.env['sale.order']

        sol_vals = {'product_id': self.iPadMini.id,
                    'name': "[A1232] Large Cabinet",
                    'product_uom': self.env.ref('uom.product_uom_unit').id,
                    'product_uom_qty': 1.0,
                    'price_unit': self.iPadMini.lst_price}

        so_vals = {'partner_id': self.agrolait.id,
                   'order_line': [(0, None, sol_vals)]}

        sale_order = SaleOrder.create(so_vals)
        # I add delivery cost in Sales order
        delivery_wizard = Form(self.env['choose.delivery.carrier'].with_context({
            'default_order_id': sale_order.id,
            'default_carrier_id': self.env.ref('delivery_bpost.delivery_carrier_bpost_domestic').id
        }))
        choose_delivery_carrier = delivery_wizard.save()
        choose_delivery_carrier.update_price()
        self.assertGreater(choose_delivery_carrier.delivery_price, 0.0, "bpost delivery cost for this SO has not been correctly estimated.")
        choose_delivery_carrier.button_confirm()

        sale_order.action_confirm()
        self.assertEquals(len(sale_order.picking_ids), 1, "The Sales Order did not generate a picking.")

        picking = sale_order.picking_ids[0]
        self.assertEquals(picking.carrier_id.id, sale_order.carrier_id.id, "Carrier is not the same on Picking and on SO.")

        picking.move_lines[0].quantity_done = 1.0
        self.assertGreater(picking.shipping_weight, 0.0, "Picking weight should be positive.")

        try:
            picking.action_done()
        except UserError as exc:
            if exc.name == "The BPost shipping service is unresponsive, please retry later.":
                _logger.warning("BPost test aborted, service is unresponsive.")
                return
            raise
        self.assertIsNot(picking.carrier_tracking_ref, False, "bpost did not return any tracking number")
        self.assertGreater(picking.carrier_price, 0.0, "bpost carrying price is probably incorrect")

    def test_02_bpost_basic_europe_flow(self):
        SaleOrder = self.env['sale.order']

        sol_vals = {'product_id': self.iPadMini.id,
                    'name': "[A1232] Large Cabinet",
                    'product_uom': self.env.ref('uom.product_uom_unit').id,
                    'product_uom_qty': 1.0,
                    'price_unit': self.iPadMini.lst_price}

        so_vals = {'partner_id': self.think_big_system.id,
                   'order_line': [(0, None, sol_vals)]}

        sale_order = SaleOrder.create(so_vals)
        # I add delivery cost in Sales order
        delivery_wizard = Form(self.env['choose.delivery.carrier'].with_context({
            'default_order_id': sale_order.id,
            'default_carrier_id': self.env.ref('delivery_bpost.delivery_carrier_bpost_inter').id
        }))
        choose_delivery_carrier = delivery_wizard.save()
        choose_delivery_carrier.update_price()
        self.assertGreater(choose_delivery_carrier.delivery_price, 0.0, "bpost delivery cost for this SO has not been correctly estimated.")
        choose_delivery_carrier.button_confirm()

        sale_order.action_confirm()
        self.assertEquals(len(sale_order.picking_ids), 1, "The Sales Order did not generate a picking.")

        picking = sale_order.picking_ids[0]
        self.assertEquals(picking.carrier_id.id, sale_order.carrier_id.id, "Carrier is not the same on Picking and on SO.")

        picking.move_lines[0].quantity_done = 1.0
        self.assertGreater(picking.shipping_weight, 0.0, "Picking weight should be positive.")

        try:
            picking.action_done()
        except UserError as exc:
            if exc.name == "The BPost shipping service is unresponsive, please retry later.":
                _logger.warning("BPost test aborted, service is unresponsive.")
                return
            raise
        self.assertIsNot(picking.carrier_tracking_ref, False, "bpost did not return any tracking number")
        self.assertGreater(picking.carrier_price, 0.0, "bpost carrying price is probably incorrect")

    def test_02b_bpost_real_invoice_policy(self):
        SaleOrder = self.env['sale.order']
        # set invoice policy to 'real'
        self.env.ref('delivery_bpost.delivery_carrier_bpost_inter').invoice_policy = 'real'
        sol_vals = {'product_id': self.iPadMini.id,
                    'name': "[A1232] Large Cabinet",
                    'product_uom': self.env.ref('uom.product_uom_unit').id,
                    'product_uom_qty': 1.0,
                    'price_unit': self.iPadMini.lst_price}

        so_vals = {'partner_id': self.think_big_system.id,
                   'order_line': [(0, None, sol_vals)]}

        sale_order = SaleOrder.create(so_vals)
        # I add delivery cost in Sales order
        delivery_wizard = Form(self.env['choose.delivery.carrier'].with_context({
            'default_order_id': sale_order.id,
            'default_carrier_id': self.env.ref('delivery_bpost.delivery_carrier_bpost_inter').id
        }))
        choose_delivery_carrier = delivery_wizard.save()
        choose_delivery_carrier.update_price()
        self.assertGreater(choose_delivery_carrier.delivery_price, 0.0, "bpost delivery cost for this SO has not been correctly estimated.")
        choose_delivery_carrier.button_confirm()

        delivery_line = sale_order.order_line.filtered(lambda line: line.is_delivery)
        self.assertEquals(len(delivery_line), 1, "The delivery line is not present on the SO.")
        self.assertEquals(delivery_line.price_unit, 0, "The delivery cost should be 0.")

        sale_order.action_confirm()
        self.assertEquals(len(sale_order.picking_ids), 1, "The Sales Order did not generate a picking.")

        picking = sale_order.picking_ids[0]
        self.assertEquals(picking.carrier_id.id, sale_order.carrier_id.id, "Carrier is not the same on Picking and on SO.")

        picking.move_lines[0].quantity_done = 1.0
        self.assertGreater(picking.shipping_weight, 0.0, "Picking weight should be positive.")

        try:
            picking.action_done()
        except UserError as exc:
            if exc.name == "The BPost shipping service is unresponsive, please retry later.":
                _logger.warning("BPost test aborted, service is unresponsive.")
                return
            raise
        self.assertIsNot(picking.carrier_tracking_ref, False, "bpost did not return any tracking number")
        self.assertGreater(picking.carrier_price, 0.0, "bpost carrying price is probably incorrect")
        # Check that the delivery cost (previously set to 0) has been correctly updated
        self.assertEquals(picking.carrier_price, delivery_line.price_unit, "The delivery cost is not updated")

    def test_03_bpost_flow_from_delivery_order(self):

        inventory = self.env['stock.inventory'].create({
            'name': '[A1232] iPad Mini',
            'location_ids': [(4, self.stock_location.id)],
            'product_ids': [(4, self.iPadMini.id)],
        })

        StockPicking = self.env['stock.picking']

        order1_vals = {
                    'product_id': self.iPadMini.id,
                    'name': "[A1232] iPad Mini",
                    'product_uom': self.uom_unit.id,
                    'product_uom_qty': 1.0,
                    'location_id': self.stock_location.id,
                    'location_dest_id': self.customer_location.id}

        do_vals = { 'partner_id': self.think_big_system.id,
                    'carrier_id': self.env.ref('delivery_bpost.delivery_carrier_bpost_inter').id,
                    'location_id': self.stock_location.id,
                    'location_dest_id': self.customer_location.id,
                    'picking_type_id': self.env.ref('stock.picking_type_out').id,
                    'move_ids_without_package': [(0, None, order1_vals)]}

        delivery_order = StockPicking.create(do_vals)
        self.assertEqual(delivery_order.state, 'draft', 'Shipment state should be draft.')

        delivery_order.action_confirm()
        self.assertEqual(delivery_order.state, 'confirmed', 'Shipment state should be waiting(confirmed).')

        delivery_order.action_assign()
        self.assertEqual(delivery_order.state, 'assigned', 'Shipment state should be ready(assigned).')
        delivery_order.move_ids_without_package.quantity_done = 1.0

        try:
            delivery_order.button_validate()
        except UserError as exc:
            if exc.name == "The BPost shipping service is unresponsive, please retry later.":
                _logger.warning("BPost test aborted, service is unresponsive.")
                return
            raise
        self.assertEqual(delivery_order.state, 'done', 'Shipment state should be done.')
