# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class SaleReport(models.Model):
    _inherit = 'sale.report'

    is_abandoned_cart = fields.Boolean(string="Abandoned Cart", readonly=True)
    invoice_status = fields.Selection([
        ('upselling', 'Upselling Opportunity'),
        ('invoiced', 'Fully Invoiced'),
        ('to invoice', 'To Invoice'),
        ('no', 'Nothing to Invoice')
        ], string="Invoice Status", readonly=True)

    def _query(self, with_clause='', fields={}, groupby='', from_clause=''):
        fields['is_abandoned_cart'] = """, s.date_order <= (timezone('utc', now()) - ((COALESCE(w.cart_abandoned_delay, '1.0') || ' hour')::INTERVAL))
        AND s.website_id != NULL
        AND s.state = 'draft'
        AND s.partner_id != %s
        AS is_abandoned_cart""" % self.env.ref('base.public_partner').id
        fields['invoice_status'] = ', s.invoice_status as invoice_status'

        from_clause += """
            left join crm_team team on team.id = s.team_id
            left join website w on w.id = s.website_id
        """

        groupby += """
            , w.cart_abandoned_delay
            , s.invoice_status
            """
        return super(SaleReport, self)._query(with_clause, fields, groupby, from_clause)
