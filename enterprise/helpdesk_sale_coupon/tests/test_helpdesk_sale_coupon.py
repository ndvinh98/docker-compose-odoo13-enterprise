# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.helpdesk.tests import common
from odoo.tests.common import Form


class TestHelpdeskSaleCoupon(common.HelpdeskCommon):
    """ Test used to check that the functionalities of After sale in Helpdesk (sale_coupon).
    """

    def test_helpdesk_sale_coupon(self):
        # give the test team ability to create coupons
        self.test_team.use_coupons = True

        partner = self.env['res.partner'].create({
            'name': 'Customer Credee'
        })
        ticket = self.env['helpdesk.ticket'].create({
            'name': 'test',
            'partner_id': partner.id,
            'team_id': self.test_team.id,
        })
        program = self.env['sale.coupon.program'].create({
            'name': 'test program',
            'promo_code_usage': 'code_needed',
            'discount_apply_on': 'on_order',
            'discount_type': 'percentage',
            'discount_percentage': 10.0,
            'program_type': 'coupon_program',
        })

        coupon_form = Form(self.env['helpdesk.sale.coupon.generate'].with_context({
            'active_model': 'helpdesk.ticket',
            'default_ticket_id': ticket.id,
        }))
        coupon_form.program = program
        sale_coupon = coupon_form.save()
        sale_coupon.generate_coupon()

        coupon = self.env['sale.coupon'].search([
            ('partner_id', '=', partner.id),
            ('program_id', '=', program.id)
        ])

        self.assertEqual(len(coupon), 1, "No coupon created")
        self.assertEqual(coupon.state, 'new', "Wrong status of the refund")
        self.assertEqual(len(ticket.coupon_ids), 1,
            "The ticket is not linked to a coupon")
        self.assertEqual(coupon[0], ticket.coupon_ids[0],
            "The correct coupon should be referenced in the ticket")
