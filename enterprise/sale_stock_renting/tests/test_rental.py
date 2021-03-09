# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import common
from odoo import fields
from datetime import timedelta

class TestRentalCommon(common.SingleTransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestRentalCommon, cls).setUpClass()

        cls.product_id = cls.env.ref('sale_renting.rental_product_1')
        cls.product_id = cls.env['product.product'].create({
            'name': 'Test1',
            'categ_id': cls.env.ref('sale_renting.cat_renting').id,  # remove category if possible?
            'uom_id': cls.env.ref('uom.product_uom_unit').id,
            'uom_po_id': cls.env.ref('uom.product_uom_unit').id,
            'rent_ok': True,
            'type': 'product',
        })
        cls.tracked_product_id = cls.env['product.product'].create({
            'name': 'Test2',
            'categ_id': cls.env.ref('sale_renting.cat_renting').id,  # remove category if possible?
            'uom_id': cls.env.ref('uom.product_uom_unit').id,
            'uom_po_id': cls.env.ref('uom.product_uom_unit').id,
            'rent_ok': True,
            'type': 'product',
            'tracking': 'serial',
        })

        # Set Stock quantities

        cls.lot_id1 = cls.env['stock.production.lot'].create({
            'product_id': cls.tracked_product_id.id,
            'name': "RentalLot1",
            'company_id': cls.env.company.id,
        })

        cls.lot_id2 = cls.env['stock.production.lot'].create({
            'product_id': cls.tracked_product_id.id,
            'name': "RentalLot2",
            'company_id': cls.env.company.id,
        })

        cls.lot_id3 = cls.env['stock.production.lot'].create({
            'product_id': cls.tracked_product_id.id,
            'name': "RentalLot3",
            'company_id': cls.env.company.id,
        })

        test_inventory = cls.env['stock.inventory'].create({
            'name': 'Rental Test Inventory',
        })

        cls.env['stock.inventory.line'].create({
            'product_id': cls.product_id.id,
            'product_uom_id': cls.product_id.uom_id.id,
            'inventory_id': test_inventory.id,
            'product_qty': 4.0,
            'location_id': cls.env['sale.order']._default_warehouse_id().lot_stock_id.id,
        })

        cls.env['stock.inventory.line'].create({
            'product_id': cls.tracked_product_id.id,
            'product_uom_id': cls.tracked_product_id.uom_id.id,
            'inventory_id': test_inventory.id,
            'product_qty': 1.0,
            'prod_lot_id': cls.lot_id1.id,
            'location_id': cls.env['sale.order']._default_warehouse_id().lot_stock_id.id,
        })

        cls.env['stock.inventory.line'].create({
            'product_id': cls.tracked_product_id.id,
            'product_uom_id': cls.tracked_product_id.uom_id.id,
            'inventory_id': test_inventory.id,
            'product_qty': 1.0,
            'prod_lot_id': cls.lot_id2.id,
            'location_id': cls.env['sale.order']._default_warehouse_id().lot_stock_id.id,
        })

        cls.env['stock.inventory.line'].create({
            'product_id': cls.tracked_product_id.id,
            'product_uom_id': cls.tracked_product_id.uom_id.id,
            'inventory_id': test_inventory.id,
            'product_qty': 1.0,
            'prod_lot_id': cls.lot_id3.id,
            'location_id': cls.env['sale.order']._default_warehouse_id().lot_stock_id.id,
        })

        test_inventory._action_start()
        test_inventory.action_validate()

        # Define rental order and lines

        cls.cust1 = cls.env['res.partner'].create({'name': 'test_rental_1'})
        # cls.cust2 = cls.env['res.partner'].create({'name': 'test_rental_2'})
        # user_group_employee = cls.env.ref('base.group_user')

        cls.user_id = cls.env['res.users'].with_context({'no_reset_password': True, 'mail_create_nosubscribe': True}).create({
            'name': 'Rental',
            'login': 'renter',
            'email': 'sale.rental@example.com',
            'notification_type': 'inbox'})

        cls.sale_order_id = cls.env['sale.order'].create({
            'partner_id': cls.cust1.id,
            'partner_invoice_id': cls.cust1.id,
            'partner_shipping_id': cls.cust1.id,
            'user_id': cls.user_id.id,
            # TODO
        })

        cls.order_line_id1 = cls.env['sale.order.line'].create({
            'order_id': cls.sale_order_id.id,
            'product_id': cls.product_id.id,
            'product_uom_qty': 0.0,
            'product_uom': cls.product_id.uom_id.id,
            'is_rental': True,
            'pickup_date': fields.Datetime.today(),
            'return_date': fields.Datetime.today() + timedelta(days=3),
            'price_unit': 150,
        })

        cls.sale_order_id.action_confirm()

        cls.lots_rental_order = cls.env['sale.order'].create({
            'partner_id': cls.cust1.id,
            'partner_invoice_id': cls.cust1.id,
            'partner_shipping_id': cls.cust1.id,
            'user_id': cls.user_id.id,
        })

        cls.order_line_id2 = cls.env['sale.order.line'].create({
            'order_id': cls.lots_rental_order.id,
            'product_id': cls.tracked_product_id.id,
            'product_uom_qty': 0.0,
            'product_uom': cls.tracked_product_id.uom_id.id,
            'is_rental': True,
            'pickup_date': fields.Datetime.today(),
            'return_date': fields.Datetime.today() + timedelta(days=3),
            'price_unit': 250,
        })

        cls.order_line_id3 = cls.env['sale.order.line'].create({
            'order_id': cls.lots_rental_order.id,
            'product_id': cls.tracked_product_id.id,
            'product_uom_qty': 0.0,
            'product_uom': cls.tracked_product_id.uom_id.id,
            'is_rental': True,
            'pickup_date': fields.Datetime.today(),
            'return_date': fields.Datetime.today() + timedelta(days=3),
            'price_unit': 250,
        })

    def test_rental_product_flow(self):

        self.assertEquals(
            self.product_id.qty_available,
            4
        )

        self.order_line_id1.write({
            'product_uom_qty': 3
        })

        self.assertEquals(
            self.product_id._get_unavailable_qty(
                self.order_line_id1.reservation_begin,
                self.order_line_id1.return_date,
                # self.order_line_id1.id,
            ), 3
        )

        """
            Total Pickup
        """

        self.order_line_id1.write({
            'qty_delivered': 3
        })

        """ In sale order warehouse """
        self.assertEquals(
            self.product_id.with_context(
                warehouse=self.order_line_id1.order_id.warehouse_id.id,
                from_date=self.order_line_id1.reservation_begin,
                to_date=self.order_line_id1.return_date,
            ).qty_available,
            1
        )

        self.product_id.invalidate_cache()
        """ In company internal rental location (in stock valuation but not in available qty) """
        self.assertEquals(
            self.product_id.with_context(
                location=self.env.company.rental_loc_id.id,
                from_date=self.order_line_id1.pickup_date,
                to_date=self.order_line_id1.return_date,
            ).qty_available,
            3
        )

        """ In company warehouses """
        self.assertEquals(
            self.product_id.qty_available,
            1
        )

        """ In company stock valuation """
        self.assertEquals(
            self.product_id.with_context(company_owned=True).qty_available,
            4
        )

        """
            Partial Return
        """

        self.order_line_id1.write({
            'qty_returned': 2
        })

        """ In sale order warehouse """
        self.assertEquals(
            self.product_id.with_context(
                warehouse=self.order_line_id1.order_id.warehouse_id.id
            ).qty_available,
            3
        )

        """ In company internal rental location (in stock valuation but not in available qty) """
        self.assertEquals(
            self.product_id.with_context(
                location=self.env.company.rental_loc_id.id,
                from_date=self.order_line_id1.pickup_date,
                to_date=self.order_line_id1.return_date,
            ).qty_available,
            1
        )

        """ In company warehouses """
        self.assertEquals(
            self.product_id.qty_available,
            3
        )

        """ In company stock valuation """
        self.assertEquals(
            self.product_id.with_context(company_owned=True).qty_available,
            4
        )

        """
            Total Return
        """

        self.order_line_id1.write({
            'qty_returned': 3
        })

        self.assertEquals(
            self.product_id.qty_available,
            4.0
        )

    def test_rental_lot_flow(self):
        self.lots_rental_order.action_confirm()

        lots = self.env['stock.production.lot'].search([('product_id', '=', self.tracked_product_id.id)])
        rentable_lots = self.env['stock.production.lot']._get_available_lots(self.tracked_product_id)
        self.assertEquals(set(lots.ids), set(rentable_lots.ids))  # set is here to ensure that order wont break test

        self.order_line_id2.reserved_lot_ids += self.lot_id1
        self.order_line_id2.product_uom_qty = 1.0

        self.order_line_id2.pickedup_lot_ids += self.lot_id2

        # Ensure lots are unreserved if other lots are picked up in their place
        # and qty pickedup = product_uom_qty (qty reserved)
        self.assertEquals(self.order_line_id2.reserved_lot_ids, self.order_line_id2.pickedup_lot_ids)

        return

    def test_schedule_report(self):
        """Verify sql scheduling view consistency.

        One sale.order.line with 3 different lots (reserved/pickedup/returned)
        is represented by 3 sale.rental.schedule to allow grouping reservation information
        by stock.production.lot .

        Note that a lot can be pickedup (sol.pickedup_lot_ids) even if not reserved (sol.reserved_lot_ids).
        """
        self.order_line_id2.reserved_lot_ids = self.lot_id1
        # Avoid magic setting pickedup lots as reserved when full quantity has been pickedup
        self.order_line_id2.product_uom_qty = 2.0

        # Lot pickedup but not reserved.
        self.order_line_id2.pickedup_lot_ids = self.lot_id2

        self.assertEquals(
            self.env["sale.rental.schedule"].search_count([('lot_id', '=', self.lot_id2.id)]),
            1,
        )
        scheduling_recs = self.env["sale.rental.schedule"].search([
            ('order_line_id', '=', self.order_line_id2.id),
        ])
        self.assertEquals(
            len(scheduling_recs),
            2, # 1 reserved, 1 pickedup
        )
        self.assertEquals(
            scheduling_recs.mapped('report_line_status'),
            ["reserved", "pickedup"],
        )

        # More generic behavior:
        # 2 reserved, 2 pickedup, 1 returned
        self.order_line_id2.returned_lot_ids = self.lot_id2
        self.order_line_id2.pickedup_lot_ids += self.lot_id1
        scheduling_recs.invalidate_cache()
        scheduling_recs = self.env["sale.rental.schedule"].search([
            ('order_line_id', '=', self.order_line_id2.id)
        ])
        self.assertEquals(
            len(scheduling_recs),
            2,
        )
        self.assertEquals(
            scheduling_recs.lot_id,
            self.lot_id1 + self.lot_id2,
        )
        self.assertEquals(
            scheduling_recs.mapped('report_line_status'),
            ["pickedup", "returned"],
        )
