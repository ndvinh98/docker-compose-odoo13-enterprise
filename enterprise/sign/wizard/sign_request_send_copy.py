# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SignRequestSendCopy(models.TransientModel):
    _name = 'sign.request.send.copy'
    _description = 'Sign send request copy'

    @api.model
    def default_get(self, fields):
        res = super(SignRequestSendCopy, self).default_get(fields)
        res['request_id'] = self.env.context.get('active_id')
        return res

    request_id = fields.Many2one('sign.request')
    partner_ids = fields.Many2many('res.partner', string="Contact")

    def send_a_copy(self):
        return self.env['sign.request'].add_followers(self.request_id.id, self.partner_ids.ids)
