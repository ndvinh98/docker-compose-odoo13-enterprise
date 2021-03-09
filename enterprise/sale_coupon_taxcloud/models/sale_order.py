# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from .taxcloud_request import TaxCloudRequest
from odoo import api, models, fields, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def _get_TaxCloudRequest(self, api_id, api_key):
        return TaxCloudRequest(api_id, api_key)

    def _get_reward_values_discount(self, program):
        res = list(super(SaleOrder, self)._get_reward_values_discount(program))
        [vals.update(coupon_program_id=program.id) for vals in res]
        return res

    def _get_reward_values_product(self, program):
        res = super(SaleOrder, self)._get_reward_values_product(program)
        res.update(coupon_program_id=program.id)
        return res

    def recompute_coupon_lines(self):
        """Before we apply the discounts, we clean up any preset tax
           that might already since it may mess up the discount computation.
        """
        taxcloud_orders = self.filtered('fiscal_position_id.is_taxcloud')
        taxcloud_orders.mapped('order_line').write({'tax_id': [(5,)]})
        return super(SaleOrder, self).recompute_coupon_lines()

    def _create_invoices(self, grouped=False, final=False):
        """Ensure that any TaxCloud order that has discounts is invoiced in one go.
           Indeed, since the tax computation of discount lines with Taxcloud
           requires that any negative amount of a coupon line be deduced from the
           lines it originated from, these cannot be invoiced separately as it be
           incoherent with what was computed on the order.
        """
        def not_totally_invoiceable(order):
            totally_invoiceable_lines = order.order_line.filtered(
                lambda l: l.qty_to_invoice == l.product_uom_qty)
            return totally_invoiceable_lines < order.order_line

        taxcloud_orders = self.filtered('fiscal_position_id.is_taxcloud')
        taxcloud_coupon_orders = taxcloud_orders.filtered('order_line.coupon_program_id')
        partial_taxcloud_coupon_orders = taxcloud_coupon_orders.filtered(not_totally_invoiceable)
        if partial_taxcloud_coupon_orders:
            bad_orders = str(partial_taxcloud_coupon_orders.mapped('display_name'))[1:-1]
            bad_orders = bad_orders if len(bad_orders) < 80 else bad_orders[:80] + ', ...'
            raise UserError(_('Any order that has discounts and uses TaxCloud must be invoiced '
                              'all at once to prevent faulty tax computation with Taxcloud.\n'
                              'The following orders must be completely invoiced:\n%s') % bad_orders)

        return super(SaleOrder, self)._create_invoices(grouped=grouped, final=final)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    coupon_program_id = fields.Many2one('sale.coupon.program',
        string='Discount Program', readonly=True,
        help='The coupon program that created this line.',
    )
    price_taxcloud = fields.Float('Taxcloud Price', default=0,
                                  help='Technical fields to hold prices for TaxCloud.')

    def _check_taxcloud_promo(self, vals):
        """Ensure that users cannot modify sale order lines of a Taxcloud order
           with promotions if there is already a valid invoice"""

        blocked_fields = (
            'product_id',
            'price_unit',
            'price_subtotal',
            'price_tax',
            'price_total',
            'tax_id',
            'discount',
            'product_id',
            'product_uom_qty',
            'product_qty'
        )
        for line in self:
            if (
                line.order_id.is_taxcloud
                and not line.display_type
                and any(field in vals for field in blocked_fields)
                and any(line.order_id.order_line.mapped(lambda sol: sol.invoice_status not in ('no','to invoice')))
                and any(line.order_id.order_line.mapped('is_reward_line'))
            ):
                raise UserError(
                    _(
                    'Orders with coupons or promotions programs that use TaxCloud for '
                    'automatic tax computation cannot be modified after having been invoiced.\n'
                    'To modify this order, you must first cancel or refund all existing invoices.'
                    )
                )

    def write(self, vals):
        self._check_taxcloud_promo(vals)
        return super(SaleOrderLine, self).write(vals)

    @api.model
    def create(self, vals):
        line = super(SaleOrderLine, self).create(vals)
        line._check_taxcloud_promo(vals)
        return line

    def _get_taxcloud_price(self):
        self.ensure_one()
        return self.price_taxcloud

    def _prepare_invoice_line(self):
        res = super(SaleOrderLine, self)._prepare_invoice_line()
        res.update({'coupon_program_id': self.coupon_program_id.id})
        return res


class SaleCouponApplyCode(models.TransientModel):
    _inherit = 'sale.coupon.apply.code'

    def apply_coupon(self, order, coupon_code):
        if order.fiscal_position_id.is_taxcloud:
            order.mapped('order_line').write({'tax_id': [(5,)]})
        return super(SaleCouponApplyCode, self).apply_coupon(order, coupon_code)
