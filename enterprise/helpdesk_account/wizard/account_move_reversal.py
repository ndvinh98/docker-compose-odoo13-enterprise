# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _


class AccountMoveReversal(models.TransientModel):
    _inherit = 'account.move.reversal'

    @api.model
    def default_get(self, fields):
        result = super(AccountMoveReversal, self).default_get(fields)
        ticket_id = self._context.get('default_helpdesk_ticket_id')
        if ticket_id and 'reason' in fields:
            result['reason'] = _('Helpdesk Ticket #%s') % ticket_id
        return result

    helpdesk_ticket_id = fields.Many2one('helpdesk.ticket')
    helpdesk_sale_order_id = fields.Many2one('sale.order', related="helpdesk_ticket_id.sale_order_id", string='Sales Order')

    @api.onchange('helpdesk_sale_order_id', 'helpdesk_ticket_id')
    def _onchange_helpdesk_move_domain(self):
        domain = [('state', '=', 'posted'), ('type', '=', 'out_invoice')]
        if self.helpdesk_sale_order_id:
            domain += [('id', 'in', self.helpdesk_sale_order_id.invoice_ids.ids)]
        elif self.helpdesk_ticket_id.partner_id:
            domain += [('partner_id', 'child_of', self.helpdesk_ticket_id.partner_id.commercial_partner_id.id)]
        return {'domain': {'move_id': domain}}

    def reverse_moves(self):
        # OVERRIDE
        res = super(AccountMoveReversal, self).reverse_moves()

        if self.helpdesk_ticket_id:
            reverse_move = self.env['account.move'].browse(res.get('res_id'))
            self.helpdesk_ticket_id.invoice_ids |= reverse_move

        return res
