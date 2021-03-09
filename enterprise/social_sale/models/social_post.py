# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class SocialPost(models.Model):
    _inherit = 'social.post'

    sale_quotation_count = fields.Integer('Quotation Count', compute='_compute_sale_quotation_count')
    sale_invoiced_amount = fields.Integer('Invoiced Amount', compute='_compute_sale_invoiced_amount')

    def _compute_sale_quotation_count(self):
        has_so_access = self.env['sale.order'].check_access_rights('read', raise_exception=False)
        if has_so_access:
            quotation_data = self.env['sale.order'].read_group(
                [('source_id', 'in', self.utm_source_id.ids)],
                ['source_id'], ['source_id'])
            mapped_data = {datum['source_id'][0]: datum['source_id_count'] for datum in quotation_data}

            for post in self:
                post.sale_quotation_count = mapped_data.get(post.utm_source_id.id, 0)
        else:
            for post in self:
                post.sale_quotation_count = 0

    def _compute_sale_invoiced_amount(self):
        has_account_move_access = self.env['account.move'].check_access_rights('read', raise_exception=False)
        if has_account_move_access:
            query = """SELECT move.source_id as source_id, -SUM(line.balance) as price_subtotal
                        FROM account_move_line line
                        INNER JOIN account_move move ON line.move_id = move.id
                        WHERE move.state not in ('draft', 'cancel')
                            AND move.source_id IN %s
                            AND move.type IN ('out_invoice', 'out_refund', 'in_invoice', 'in_refund', 'out_receipt', 'in_receipt')
                            AND line.account_id IS NOT NULL
                            AND NOT line.exclude_from_invoice_tab
                        GROUP BY move.source_id
                        """
            self._cr.execute(query, [tuple(self.utm_source_id.ids)])
            query_res = self._cr.dictfetchall()
            mapped_data = {datum['source_id']: datum['price_subtotal'] for datum in query_res}

            for post in self:
                post.sale_invoiced_amount = mapped_data.get(post.utm_source_id.id, 0)
        else:
            for post in self:
                post.sale_invoiced_amount = 0

    def action_redirect_to_quotations(self):
        action = self.env.ref('sale.action_quotations_with_onboarding').read()[0]
        action['domain'] = self._get_sale_utm_domain()
        action['context'] = {'create': False}
        return action

    def action_redirect_to_invoiced(self):
        action = self.env.ref('account.action_move_journal_line').read()[0]
        action['context'] = {
            'create': False,
            'edit': False,
            'view_no_maturity': True
        }
        action['domain'] = [
            ('source_id', '=', self.utm_source_id.id),
            ('type', 'in', ('out_invoice', 'out_refund', 'in_invoice', 'in_refund', 'out_receipt', 'in_receipt')),
            ('state', 'not in', ['draft', 'cancel'])
        ]
        return action

    def _get_sale_utm_domain(self):
        """ We want all records that match the UTMs """
        return [('source_id', '=', self.utm_source_id.id)]
