# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.helpdesk.tests import common
from odoo.tests.common import Form


class TestHelpdeskStock(common.HelpdeskCommon):
    """ Test used to check that the functionalities of After sale in Helpdesk (stock).
    """

    def test_helpdesk_stock(self):
        # give the test team ability to create coupons
        self.test_team.use_product_returns = True

        partner = self.env['res.partner'].create({
            'name': 'Customer Credee'
        })
        product = self.env['product.product'].create({
            'name': 'product 1',
            'type': 'product',
        })
        so = self.env['sale.order'].create({
            'partner_id': partner.id,
        })
        self.env['sale.order.line'].create({
            'product_id': product.id,
            'price_unit': 10,
            'product_uom_qty': 1,
            'order_id': so.id,
        })
        so.action_confirm()
        so._create_invoices()
        invoice = so.invoice_ids
        invoice.post()
        so.picking_ids[0].move_lines[0].quantity_done = 1
        so.picking_ids[0].action_done()
        ticket = self.env['helpdesk.ticket'].create({
            'name': 'test',
            'partner_id': partner.id,
            'team_id': self.test_team.id,
            'sale_order_id': so.id,
        })

        stock_picking_form = Form(self.env['stock.return.picking'].with_context({
            'active_model': 'helpdesk.ticket',
            'default_ticket_id': ticket.id
        }))
        stock_picking_form.picking_id = so.picking_ids[0]
        return_picking = stock_picking_form.save()

        self.assertEqual(len(return_picking.product_return_moves), 1,
            "A picking line should be present")
        self.assertEqual(return_picking.product_return_moves[0].product_id, product,
            "The product of the picking line does not match the product of the sale order")

        return_picking.create_returns()

        return_picking = self.env['stock.picking'].search([
            ('partner_id', '=', partner.id),
            ('picking_type_code', '=', 'incoming'),
        ])

        self.assertEqual(len(return_picking), 1, "No return created")
        self.assertEqual(return_picking.state, 'assigned', "Wrong status of the refund")
        self.assertEqual(ticket.pickings_count, 1,
            "The ticket should be linked to a return")
        self.assertEqual(return_picking.id, ticket.picking_ids[0].id,
            "The correct return should be referenced in the ticket")
