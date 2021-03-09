# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class HelpdeskSaleCouponGenerate(models.TransientModel):
    _name = "helpdesk.sale.coupon.generate"
    _description = 'Generate Sales Coupon from Helpdesk'

    ticket_id = fields.Many2one('helpdesk.ticket')
    company_id = fields.Many2one(related="ticket_id.company_id")
    program = fields.Many2one('sale.coupon.program', string="Coupon Program", domain=[('program_type', '=', 'coupon_program'), ('company_id', '=', False)])

    @api.onchange('ticket_id')
    def _onchange_ticketid_coupon(self):
        if self.ticket_id:
            return {'domain':
                        {'program': [('program_type', '=', 'coupon_program'), '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)]}
                }

    def generate_coupon(self):
        """Generates a coupon for the selected program and the partner linked
        to the ticket
        """
        vals = {
            'partner_id': self.ticket_id.partner_id.id,
            'state': 'new',
            'program_id': self.program.id,
        }
        coupon = self.env['sale.coupon'].create(vals)
        self.ticket_id.coupon_ids |= coupon
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.coupon',
            'res_id': coupon.id,
            'view_mode': 'form',
        }
