# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    subscription_ids = fields.One2many('sale.subscription', 'analytic_account_id', string='Subscriptions')
    subscription_count = fields.Integer(compute='_compute_subscription_count', string='Subscription Count')

    def _compute_subscription_count(self):
        subscription_data = self.env['sale.subscription'].read_group(domain=[('analytic_account_id', 'in', self.ids)],
                                                                     fields=['analytic_account_id'],
                                                                     groupby=['analytic_account_id'])
        mapped_data = dict([(m['analytic_account_id'][0], m['analytic_account_id_count']) for m in subscription_data])
        for account in self:
            account.subscription_count = mapped_data.get(account.id, 0)

    def subscriptions_action(self):
        subscription_ids = self.mapped('subscription_ids').ids
        result = {
            "type": "ir.actions.act_window",
            "res_model": "sale.subscription",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [["id", "in", subscription_ids]],
            "context": {"create": False},
            "name": "Subscriptions",
        }
        if len(subscription_ids) == 1:
            result['views'] = [(False, "form")]
            result['res_id'] = subscription_ids[0]
        return result
