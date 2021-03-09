# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    commercial_partner_id = fields.Many2one(related='partner_id.commercial_partner_id')
    sale_order_id = fields.Many2one('sale.order', string='Sales Order', domain="[('partner_id', 'child_of', commercial_partner_id), ('company_id', '=', company_id)]",
        groups="sales_team.group_sale_salesman,account.group_account_invoice",
        help="Reference of the Sales Order to which this ticket refers. Setting this information aims at easing your After Sales process and only serves indicative purposes.")

    @api.onchange('partner_id')
    def _onchange_partner_id_domain_sale_order_id(self):
        return {
            'domain': {
                'sale_order_id': [('company_id', '=', self.company_id.id), ('partner_id', 'child_of', self.commercial_partner_id.id)] if self.partner_id else []
            }
        }

    def copy(self, default=None):
        if not self.env.user.has_group('sales_team.group_sale_salesman') and not self.env.user.has_group('account.group_account_invoice'):
            if default is None:
                default = {'sale_order_id': False}
            else:
                default.update({'sale_order_id': False})
        return super(HelpdeskTicket, self).copy(default=default)
