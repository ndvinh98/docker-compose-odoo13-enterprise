# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import fields, models, api


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    subscription_id = fields.Many2one("sale.subscription")
    subscription_start_date = fields.Date(
        string="Subscription Revenue Start Date", readonly=True
    )
    subscription_end_date = fields.Date(
        string="Subscription Revenue End Date", readonly=True
    )
    subscription_mrr = fields.Monetary(
        string="Monthly Recurring Revenue",
        compute="_compute_mrr",
        store=True,
        help="The MRR is computed by dividing the signed amount (in company currency) by the "
        "amount of time between the start and end dates converted in months.\nThis allows "
        "comparison of invoice lines created by subscriptions with different temporalities.\n"
        "The computation assumes that 1 month is comprised of exactly 30 days, regardless "
        " of the actual length of the month.",
    )

    # NOTE: deps on subscription_id are omitted by design, as it would trigger a recompute of
    # past data is a subscription's template where changed somehow
    # This computation should happen once and should basically be left as-is once done
    @api.depends("price_subtotal", "subscription_start_date", "subscription_end_date")
    def _compute_mrr(self):
        """Compute the Subscription MRR for the line.

        The MRR is defined using generally accepted ratios used identically in the
        sale.subscription model to compute the MRR for a subscription; this method
        simply applies the same computation for a single invoice line for reporting
        purposes.
        """
        for line in self:
            if not (line.subscription_end_date and line.subscription_start_date):
                line.subscription_mrr = 0
                continue
            # we need to retro-compute the interval of the subscription as close as possible
            # hence the addition of 1 extra day to the end date - this mirrors the computation
            # of the next date in the subscription
            delta = relativedelta(
                dt1=line.subscription_end_date + relativedelta(days=1),
                dt2=line.subscription_start_date,
            )
            months = delta.months + delta.days / 30.0 + delta.years * 12.0
            line.subscription_mrr = line.price_subtotal / months if months else 0
