# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    coupons_count = fields.Integer('Coupons Count', compute="_compute_coupons_count")
    coupon_ids = fields.Many2many('sale.coupon', string="Generated Coupons")

    @api.depends('coupon_ids')
    def _compute_coupons_count(self):
        for ticket in self:
            ticket.coupons_count = len(ticket.coupon_ids)

    def open_coupons(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Coupons'),
            'res_model': 'sale.coupon',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.coupon_ids.ids)],
            'context': {
                'default_company_id': self.company_id.id
            },
        }
