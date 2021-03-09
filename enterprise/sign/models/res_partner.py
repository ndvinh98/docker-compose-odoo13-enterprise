# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    signature_count = fields.Integer(compute='_compute_signature_count', string="# Signatures")

    def _compute_signature_count(self):
        signature_data = self.env['sign.request.item'].sudo().read_group([('partner_id', 'in', self.ids)], ['partner_id'], ['partner_id'])
        signature_data_mapped = dict((data['partner_id'][0], data['partner_id_count']) for data in signature_data)
        for partner in self:
            partner.signature_count = signature_data_mapped.get(partner.id, 0)

    def open_signatures(self):
        self.ensure_one()
        request_ids = self.env['sign.request.item'].search([('partner_id', '=', self.id)]).mapped('sign_request_id')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Signature(s)',
            'view_mode': 'tree,form',
            'res_model': 'sign.request',
            'domain': [('id', 'in', request_ids.ids)]
        }
