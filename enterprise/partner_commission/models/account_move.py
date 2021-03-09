# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import _, fields, models
from odoo.tools import formatLang, format_date


class AccountMove(models.Model):
    _inherit = 'account.move'

    referrer_id = fields.Many2one('res.partner', 'Referrer', domain=[('grade_id', '!=', False)])
    commission_po_line_id = fields.Many2one('purchase.order.line', 'Referrer Purchase Order line', copy=False)

    def _get_commission_purchase_order_domain(self):
        self.ensure_one()
        return [
            ('partner_id', '=', self.referrer_id.id),
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'draft'),
            ('currency_id', '=', self.currency_id.id),
        ]

    def _get_commission_purchase_order(self):
        self.ensure_one()
        purchase = self.env['purchase.order'].sudo().search(self._get_commission_purchase_order_domain(), limit=1)

        if not purchase:
            purchase = self.env['purchase.order'].with_context(mail_create_nosubscribe=True).sudo().create({
                'partner_id': self.referrer_id.id,
                'currency_id': self.currency_id.id,
                'company_id': self.company_id.id,
                'fiscal_position_id': self.env['account.fiscal.position'].with_context(force_company=self.company_id.id).get_fiscal_position(self.referrer_id.id),
                'payment_term_id': self.referrer_id.with_context(force_company=self.company_id.id).property_supplier_payment_term_id.id,
                'user_id': False,
                'dest_address_id': self.referrer_id.id,
                'origin': self.name,
            })

        return purchase

    def _make_commission(self):
        for move in self.filtered(lambda m: m.type in ['out_invoice', 'in_invoice']):
            if move.commission_po_line_id or not move.referrer_id:
                continue

            comm_by_rule = defaultdict(float)

            product = None
            subscription = None
            for line in move.invoice_line_ids:
                rule = line._get_commission_rule()
                if rule:
                    if not product:
                        product = rule.plan_id.product_id
                    if not subscription:
                        subscription = line.subscription_id
                    commission = move.currency_id.round(line.price_subtotal * rule.rate / 100.0)
                    comm_by_rule[rule] += commission

            # regulate commissions
            for r, amount in comm_by_rule.items():
                if r.is_capped:
                    amount = min(amount, r.max_commission)
                    comm_by_rule[r] = amount

            total = sum(comm_by_rule.values())
            if not total:
                continue

            # build description lines
            desc = f"{_('Commission on %s') % (move.name)}, {move.partner_id.name}, {formatLang(self.env, move.amount_untaxed, currency_obj=move.currency_id)}"
            if subscription:
                periods = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months', 'yearly': 'years'}
                date_to = subscription.recurring_next_date
                date_from = fields.Date.subtract(date_to, **{periods[subscription.recurring_rule_type]: subscription.recurring_interval})
                desc += f"\n{subscription.code}, {_('from %s to %s') % (format_date(self.env, date_from), format_date(self.env, date_to))}"

            purchase = move._get_commission_purchase_order()

            line = self.env['purchase.order.line'].sudo().create({
                'name': desc,
                'product_id': product.id,
                'product_qty': 1,
                'price_unit': total,
                'product_uom': product.uom_id.id,
                'date_planned': fields.Datetime.now(),
                'order_id': purchase.id,
                'qty_received': 1,
            })

            # link the purchase order line to the invoice
            move.commission_po_line_id = line

            msg_body = 'New commission. Invoice: <a href=# data-oe-model=account.move data-oe-id=%d>%s</a>. Amount: %s.' % (move.id, move.name, formatLang(self.env, total, currency_obj=move.currency_id))
            purchase.message_post(body=msg_body)

    def _refund_commission(self):
        for move in self.filtered('commission_po_line_id'):
            purchase = move._get_commission_purchase_order()
            line = move.commission_po_line_id
            self.env['purchase.order.line'].sudo().create({
                'name': _('Refund for %s') % line.name,
                'product_id': line.product_id.id,
                'product_qty': 1,
                'price_unit': -line.price_unit,
                'product_uom': line.product_id.uom_id.id,
                'date_planned': fields.Datetime.now(),
                'order_id': purchase.id,
                'qty_received': 1,
            })
            msg_body = 'Commission refunded. Invoice: <a href=# data-oe-model=account.move data-oe-id=%d>%s</a>. Amount: %s.' % (move.id, move.name, formatLang(self.env, -line.price_unit, currency_obj=move.currency_id))
            purchase.message_post(body=msg_body)

    def _reverse_moves(self, default_values_list=None, cancel=False):
        if not default_values_list:
            default_values_list = [{} for move in self]
        for move, default_values in zip(self, default_values_list):
            default_values.update({
                'referrer_id': move.referrer_id.id,
                'commission_po_line_id': move.commission_po_line_id.id,
            })
        return super(AccountMove, self)._reverse_moves(default_values_list=default_values_list, cancel=cancel)

    def action_invoice_paid(self):
        res = super().action_invoice_paid()
        self.filtered(lambda move: move.type == 'out_refund')._refund_commission()
        self.filtered(lambda move: move.type == 'out_invoice')._make_commission()
        return res


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _get_commission_rule(self):
        self.ensure_one()
        template = self.subscription_id.template_id
        # check whether the product is part of the subscription template
        template_id = template.id if template and self.product_id.product_tmpl_id in template.product_ids else None
        sub_pricelist = self.subscription_id.pricelist_id
        pricelist_id =  sub_pricelist and sub_pricelist.id or self.sale_line_ids.mapped('order_id.pricelist_id')[:1].id

        # a specific commission plan can be set on the subscription, taking predence over the referrer's commission plan
        plan = self.move_id.referrer_id.commission_plan_id
        if self.subscription_id:
            plan = self.subscription_id.commission_plan_id

        if not plan:
            return self.env['commission.rule']

        return plan._match_rules(self.product_id, template_id, pricelist_id)
