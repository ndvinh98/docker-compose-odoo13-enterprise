# -*- coding: utf-8 -*-
# Part of Odoo. See ICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    partner_id = fields.Many2one('res.partner', related="ticket_id.partner_id", string="Customer")
    ticket_id = fields.Many2one('helpdesk.ticket')
    sale_order_id = fields.Many2one('sale.order', related="ticket_id.sale_order_id", string='Sales Order')

    @api.onchange('sale_order_id', 'partner_id')
    def _onchange_picking_id_domain(self):
        domain = [('state', '=', 'done')]
        if self.sale_order_id:
            domain += [('id', 'in', self.sale_order_id.picking_ids.ids)]
        elif self.partner_id:
            domain += [('partner_id', 'child_of', self.partner_id.commercial_partner_id.id)]
        return {'domain': {'picking_id': domain}}

    def create_returns(self):
        res = super(ReturnPicking, self).create_returns()
        picking_id = self.env['stock.picking'].browse(res['res_id'])
        if self.ticket_id:
            self.ticket_id.picking_ids |= picking_id
        else:
            ticket_id = self.env['helpdesk.ticket'].search([('picking_ids', 'in', self.picking_id.id)], limit=1)
            if ticket_id:
                ticket_id.picking_ids |= picking_id
        return res
