# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests.common import TransactionCase, tagged, Form


@tagged('-standard', 'external')
class TestDeliveryDHL(TransactionCase):

    def setUp(self):
        super(TestDeliveryDHL, self).setUp()

        self.iPadMini = self.env.ref('product.product_product_6')
        self.large_desk = self.env.ref('product.product_product_8')
        self.uom_unit = self.env.ref('uom.product_uom_unit')

        self.your_company = self.env.ref('base.main_partner')
        self.your_company.write({'street': "44 Wall Street",
                                 'street2': "Suite 603",
                                 'city': "New York",
                                 'zip': 10005,
                                 'state_id': self.env.ref('base.state_us_27').id,
                                 'country_id': self.env.ref('base.us').id})
        self.agrolait = self.env.ref('base.res_partner_2')
        self.agrolait.write({'street': "rue des Bourlottes, 9",
                             'street2': "",
                             'city': "Ramillies",
                             'zip': 1367,
                             'state_id': False,
                             'country_id': self.env.ref('base.be').id})
        self.delta_pc = self.env.ref('base.res_partner_4')
        self.delta_pc.write({'street': "51 Federal Street",
                             'street2': "Suite 401",
                             'city': "San Francisco",
                             'zip': 94107,
                             'state_id': self.env.ref('base.state_us_5').id,
                             'country_id': self.env.ref('base.us').id})
        self.stock_location = self.env.ref('stock.stock_location_stock')
        self.customer_location = self.env.ref('stock.stock_location_customers')

    def wiz_put_in_pack(self, picking):
        """ Helper to use the 'choose.delivery.package' wizard
        in order to call the '_put_in_pack' method.
        """
        wiz_action = picking.put_in_pack()
        self.assertEquals(wiz_action['res_model'], 'choose.delivery.package', 'Wrong wizard returned')
        wiz = self.env[wiz_action['res_model']].with_context(wiz_action['context']).create({
            'delivery_packaging_id': picking.carrier_id.dhl_default_packaging_id.id
        })
        wiz.put_in_pack()

    def test_01_dhl_basic_us_domestic_flow(self):
        SaleOrder = self.env['sale.order']

        sol_vals = {'product_id': self.iPadMini.id,
                    'name': "[A1232] Large Cabinet",
                    'product_uom': self.uom_unit.id,
                    'product_uom_qty': 1.0,
                    'price_unit': self.iPadMini.lst_price}

        so_vals = {'partner_id': self.delta_pc.id,
                   'order_line': [(0, None, sol_vals)]}

        sale_order = SaleOrder.create(so_vals)
        # I add free delivery cost in Sales order
        delivery_wizard = Form(self.env['choose.delivery.carrier'].with_context({
            'default_order_id': sale_order.id,
            'default_carrier_id': self.env.ref('delivery_dhl.delivery_carrier_dhl_dom').id
        }))
        choose_delivery_carrier = delivery_wizard.save()
        choose_delivery_carrier.update_price()
        # DHL test server will return 0.0...
        # self.assertGreater(sale_order.delivery_price, 0.0, "DHL delivery cost for this SO has not been correctly estimated.")
        choose_delivery_carrier.button_confirm()

        sale_order.action_confirm()
        self.assertEquals(len(sale_order.picking_ids), 1, "The Sales Order did not generate a picking.")

        picking = sale_order.picking_ids[0]
        self.assertEquals(picking.carrier_id.id, sale_order.carrier_id.id, "Carrier is not the same on Picking and on SO.")

        picking.move_lines[0].quantity_done = 1.0
        self.assertGreater(picking.shipping_weight, 0.0, "Picking weight should be positive.")

        picking.action_done()
        self.assertIsNot(picking.carrier_tracking_ref, False, "DHL did not return any tracking number")
        # self.assertGreater(picking.carrier_price, 0.0, "DHL carrying price is probably incorrect")

        picking.cancel_shipment()
        self.assertFalse(picking.carrier_tracking_ref, "Carrier Tracking code has not been properly deleted")
        self.assertEquals(picking.carrier_price, 0.0, "Carrier price has not been properly deleted")

    def test_02_dhl_basic_international_flow(self):
        SaleOrder = self.env['sale.order']

        sol_vals = {'product_id': self.iPadMini.id,
                    'name': "[A1232] Large Cabinet",
                    'product_uom': self.uom_unit.id,
                    'product_uom_qty': 1.0,
                    'price_unit': self.iPadMini.lst_price}

        so_vals = {'partner_id': self.agrolait.id,
                   'carrier_id': self.env.ref('delivery_dhl.delivery_carrier_dhl_intl').id,
                   'order_line': [(0, None, sol_vals)]}

        sale_order = SaleOrder.create(so_vals)
        # I add free delivery cost in Sales order
        delivery_wizard = Form(self.env['choose.delivery.carrier'].with_context({
            'default_order_id': sale_order.id,
            'default_carrier_id': self.env.ref('delivery_dhl.delivery_carrier_dhl_intl').id
        }))
        choose_delivery_carrier = delivery_wizard.save()
        choose_delivery_carrier.update_price()
        # DHL test server will return 0.0...
        # self.assertGreater(sale_order.delivery_price, 0.0, "DHL delivery cost for this SO has not been correctly estimated.")
        choose_delivery_carrier.button_confirm()

        sale_order.action_confirm()
        self.assertEquals(len(sale_order.picking_ids), 1, "The Sales Order did not generate a picking.")

        picking = sale_order.picking_ids[0]
        self.assertEquals(picking.carrier_id.id, sale_order.carrier_id.id, "Carrier is not the same on Picking and on SO.")

        picking.move_lines[0].quantity_done = 1.0
        self.assertGreater(picking.shipping_weight, 0.0, "Picking weight should be positive.")

        picking.action_done()
        self.assertIsNot(picking.carrier_tracking_ref, False, "DHL did not return any tracking number")
        # self.assertGreater(picking.carrier_price, 0.0, "DHL carrying price is probably incorrect")

        picking.cancel_shipment()
        self.assertFalse(picking.carrier_tracking_ref, "Carrier Tracking code has not been properly deleted")
        self.assertEquals(picking.carrier_price, 0.0, "Carrier price has not been properly deleted")

    def test_03_dhl_multipackage_international_flow(self):
        SaleOrder = self.env['sale.order']

        sol_1_vals = {'product_id': self.iPadMini.id,
                      'name': "[A1232] Large Cabinet",
                      'product_uom': self.uom_unit.id,
                      'product_uom_qty': 1.0,
                      'price_unit': self.iPadMini.lst_price}
        sol_2_vals = {'product_id': self.large_desk.id,
                      'name': "[A1090] Large Desk",
                      'product_uom': self.uom_unit.id,
                      'product_uom_qty': 1.0,
                      'price_unit': self.large_desk.lst_price}

        so_vals = {'partner_id': self.agrolait.id,
                   'carrier_id': self.env.ref('delivery_dhl.delivery_carrier_dhl_intl').id,
                   'order_line': [(0, None, sol_1_vals), (0, None, sol_2_vals)]}

        sale_order = SaleOrder.create(so_vals)
        # I add free delivery cost in Sales order
        delivery_wizard = Form(self.env['choose.delivery.carrier'].with_context({
            'default_order_id': sale_order.id,
            'default_carrier_id': self.env.ref('delivery_dhl.delivery_carrier_dhl_intl').id
        }))
        choose_delivery_carrier = delivery_wizard.save()
        choose_delivery_carrier.update_price()
        # DHL test server will return 0.0...
        # self.assertGreater(sale_order.delivery_price, 0.0, "DHL delivery cost for this SO has not been correctly estimated.")
        choose_delivery_carrier.button_confirm()

        sale_order.action_confirm()
        self.assertEquals(len(sale_order.picking_ids), 1, "The Sales Order did not generate a picking.")

        picking = sale_order.picking_ids[0]
        self.assertEquals(picking.carrier_id.id, sale_order.carrier_id.id, "Carrier is not the same on Picking and on SO.")

        move0 = picking.move_lines[0]
        move0.quantity_done = 1.0
        self.wiz_put_in_pack(picking)
        move1 = picking.move_lines[1]
        move1.quantity_done = 1.0
        self.wiz_put_in_pack(picking)
        self.assertEquals(len(picking.move_line_ids.mapped('result_package_id')), 2, "2 Packages should have been created at this point")
        self.assertGreater(picking.shipping_weight, 0.0, "Picking weight should be positive.")

        picking.action_done()
        self.assertIsNot(picking.carrier_tracking_ref, False, "DHL did not return any tracking number")
        # self.assertGreater(picking.carrier_price, 0.0, "DHL carrying price is probably incorrect")

        picking.cancel_shipment()
        self.assertFalse(picking.carrier_tracking_ref, "Carrier Tracking code has not been properly deleted")
        self.assertEquals(picking.carrier_price, 0.0, "Carrier price has not been properly deleted")

    def test_04_dhl_flow_from_delivery_order(self):

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

        do_vals = { 'partner_id': self.agrolait.id,
                    'carrier_id': self.env.ref('delivery_dhl.delivery_carrier_dhl_intl').id,
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

        delivery_order.button_validate()
        self.assertEqual(delivery_order.state, 'done', 'Shipment state should be done.')
