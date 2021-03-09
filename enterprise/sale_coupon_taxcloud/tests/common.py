# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import common


class TestSaleCouponTaxCloudCommon(common.TransactionCase):
    """The aim of these tests is NOT to test coupon programs, but only that
       what we send to TaxCloud is coherent to the application of discounts.
       There are weird things that may happen with poorly configured discounts.
       E.g. we can remove 100$ on product C, but product C only costs 50$.
       That means that the other 50$ are deduced from the rest of the order.
       We do the same thing in TaxCloud: if the discount applies to C,
       we try to remove everything from the C line(s),
       and if there is a remainder we remove from other lines.
       Worst case, the whole order can have a negative price.
       In TaxCloud negative prices cannot exist, so we would just consider the
       order to be 0 on all lines.
       Note that mindful sellers should avoid such situations by themselves.
    """
    def setUp(self):
        super(TestSaleCouponTaxCloudCommon, self).setUp()

        self.env['sale.coupon.program'].search([]).write({'active': False})

        self.customer = self.env['res.partner'].create({
            'name': 'Theodore John K.',
        })
        self.fiscal_position = self.env['account.fiscal.position'].create({
            'name': 'BurgerLand',
            'is_taxcloud': True,
        })
        self.order = self.env['sale.order'].create({
            'partner_id': self.customer.id,
            'fiscal_position_id': self.fiscal_position.id,
        })
        self.tic_category = self.env['product.tic.category'].create({
            'code': 20110,
            'description': 'Computers',
        })
        def create_product(name, price):
            product = self.env['product.product'].create({
                'name': name,
                'list_price': price,
                'sale_ok': True,
                'tic_category_id': self.tic_category.id,
                'taxes_id': False,
            })
            return product

        self.product_A = create_product('A', 100)
        self.product_B = create_product('B', 5)
        self.product_C = create_product('C', 10)

        def create_line(product, quantity):
            line = self.env['sale.order.line'].create({
                'order_id': self.order.id,
                'product_id': product.id,
                'product_uom_qty': quantity,
            })
            return line

        lines = (create_line(self.product_A, 1) +
                 create_line(self.product_B, 10) +
                 create_line(self.product_C, 1))

        self.order.write({'order_line': [(6, 0, lines.ids)]})

        def create_program(values):
            common_values = {
                'rule_products_domain': "[['sale_ok', '=', True]]",
                'program_type': 'coupon_program',
                'promo_applicability': 'on_current_order',
                'active': True,
            }
            values.update(common_values)
            return self.env['sale.coupon.program'].create(values)

        self.program_order_percent = create_program({
            'name': '10% on order',
            'discount_apply_on': 'on_order',
            'reward_type': 'discount',
            'discount_percentage': 10.0,
        })
        self.program_cheapest_percent = self.env['sale.coupon.program'].create({
            'name': '50% on cheapest product',
            'discount_apply_on': 'cheapest_product',
            'reward_type': 'discount',
            'discount_percentage': 50.0,
        })
        self.program_specific_product_A = self.env['sale.coupon.program'].create({
            'name': '20% on product A',
            'discount_apply_on': 'specific_products',
            'reward_type': 'discount',
            'discount_percentage': 20.0,
            'discount_line_product_id': self.product_A.id,
        })
        self.program_free_product_C = self.env['sale.coupon.program'].create({
            'name': 'free product C',
            'discount_apply_on': 'on_order',
            'reward_type': 'product',
            'reward_product_id': self.product_C.id,
        })
        self.all_programs = (self.program_order_percent +
                             self.program_cheapest_percent +
                             self.program_specific_product_A +
                             self.program_free_product_C)

        def generate_coupon(program):
            Generate = self.env['sale.coupon.generate']
            Generate = Generate.with_context(active_id=program.id)
            Generate.create({
                'generation_type': 'nbr_coupon',
                'nbr_coupons': 1
            }).generate_coupon()

        for program in self.all_programs:
            generate_coupon(program)
