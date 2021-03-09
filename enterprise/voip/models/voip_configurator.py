# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.exceptions import AccessDenied


class VoipConfigurator(models.Model):
    _name = 'voip.configurator'
    _description = 'VOIP Configurator'

    @api.model
    def get_pbx_config(self):
        if not self.env.user.has_group('base.group_user'):
            raise AccessDenied()
        get_param = self.env['ir.config_parameter'].sudo().get_param
        return {'pbx_ip': get_param('voip.pbx_ip', default='localhost'),
                'wsServer': get_param('voip.wsServer', default='ws://localhost'),
                'login': self.env.user[0].sip_login,
                'password': self.env.user[0].sip_password,
                'debug': self.user_has_groups('base.group_no_one'),
                'external_phone': self.env.user[0].sip_external_phone,
                'always_transfer': self.env.user[0].sip_always_transfer,
                'ignore_incoming': self.env.user[0].sip_ignore_incoming,
                'mode': get_param('voip.mode', default="demo"),
                }
