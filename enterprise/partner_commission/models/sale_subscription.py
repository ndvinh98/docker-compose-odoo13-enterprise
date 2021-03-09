# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import api, fields, models


class SaleSubscription(models.Model):
    _inherit = 'sale.subscription'

    referrer_id = fields.Many2one('res.partner', 'Referrer', domain=[('grade_id', '!=', False)])
    commission_plan_frozen = fields.Boolean('Freeze Commission Plan', tracking=True, help="Whether the commission plan is frozen. When checked, the commission plan won't automatically be updated according to the partner level.")
    commission_plan_id = fields.Many2one(
        'commission.plan',
        'Commission Plan',
        compute='_compute_commission_plan',
        inverse='_set_commission_plan',
        store=True,
        tracking=True,
        help="Takes precedence over the Referrer's commission plan.")
    commission = fields.Monetary(string='Referrer Commission', compute='_compute_commission')

    # This field is only used to improve the UX; commission_plan_frozen is technically preferred.
    commission_plan_assignation = fields.Selection([
        ('auto', 'Based On Referrer'),
        ('fixed', 'Manual')],
        default='auto', compute='_compute_commission_plan_assignation', inverse='_inverse_commission_plan_assignation', search='_search_commission_plan_assignation')

    @api.depends('commission_plan_frozen')
    def _compute_commission_plan_assignation(self):
        for sub in self:
            sub.commission_plan_assignation = 'fixed' if sub.commission_plan_frozen else 'auto'

    def _inverse_commission_plan_assignation(self):
        for sub in self:
            sub.commission_plan_frozen = sub.commission_plan_assignation == 'fixed'

    def _search_commission_plan_assignation(self, operator, value):
        if (operator, value) in [('=', 'auto'), ('!=', 'fixed')]:
            return [('commission_plan_frozen', '=', False)]
        return [('commission_plan_frozen', '=', True)]

    @api.depends('referrer_id', 'commission_plan_id', 'template_id', 'pricelist_id', 'recurring_invoice_line_ids.price_subtotal')
    def _compute_commission(self):
        for sub in self:
            if not sub.referrer_id or not sub.commission_plan_id:
                sub.commission = 0
            else:
                comm_by_rule = defaultdict(float)

                template = sub.template_id
                template_id = template.id if template else None

                for line in self.recurring_invoice_line_ids:
                    rule = sub.commission_plan_id._match_rules(line.product_id, template_id, sub.pricelist_id.id)
                    if rule:
                        commission = sub.currency_id.round(line.price_subtotal * rule.rate / 100.0)
                        comm_by_rule[rule] += commission

                # cap by rule
                for r, amount in comm_by_rule.items():
                    if r.is_capped:
                        amount = min(amount, r.max_commission)
                        comm_by_rule[r] = amount

                sub.commission = sum(comm_by_rule.values())

    @api.depends('commission_plan_frozen', 'partner_id', 'referrer_id', 'referrer_id.commission_plan_id')
    def _compute_commission_plan(self):
        for sub in self:
            if not sub.commission_plan_frozen:
                sub.commission_plan_id = sub.referrer_id.commission_plan_id

    def _set_commission_plan(self):
        for sub in self:
            if not sub.commission_plan_frozen and sub.referrer_id and sub.referrer_id.commission_plan_id != sub.commission_plan_id:
                sub.commission_plan_frozen = True

    def _prepare_invoice_data(self):
        vals = super(SaleSubscription, self)._prepare_invoice_data()
        if self.referrer_id:
            vals.update({
                'referrer_id': self.referrer_id.id,
            })
        return vals

    def _prepare_renewal_order_values(self):
        vals = super(SaleSubscription, self)._prepare_renewal_order_values()
        for subscription in self.filtered('referrer_id'):
            vals[subscription.id].update({
                'referrer_id': subscription.referrer_id.id,
                'commission_plan_id': subscription.commission_plan_id.id,
            })
        return vals
