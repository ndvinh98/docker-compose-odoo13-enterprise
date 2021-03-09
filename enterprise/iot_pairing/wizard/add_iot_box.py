# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import requests
import time

from odoo import _, fields, models
from odoo.exceptions import UserError

TIMEOUT = 20


class AddIotBox(models.TransientModel):
    _inherit = 'add.iot.box'

    pairing_code = fields.Char(string='Pairing Code')

    def box_pairing(self):
        data = {
            'params': {
                'pairing_code': self.pairing_code,
                'db_uuid': self.env['ir.config_parameter'].sudo().get_param('database.uuid'),
                'database_url': self.env['ir.config_parameter'].sudo().get_param('web.base.url'),
                'enterprise_code': self.env['ir.config_parameter'].sudo().get_param('database.enterprise_code'),
                'token': self.env['ir.config_parameter'].sudo().get_param('iot_token'),
            },
        }
        try:
            req = requests.post('https://iot-proxy.odoo.com/odoo-enterprise/iot/connect-db', json=data, timeout=TIMEOUT)
        except requests.exceptions.ReadTimeout:
            raise UserError(_("We had troubles pairing your IoT Box. Please try again later."))

        response = req.json()

        if 'error' in response:
            if response['error']['code'] == 404:
                raise UserError(_("The pairing code you provided was not found in our system. Please check that you entered it correctly."))
            else:
                raise requests.exceptions.ConnectionError()
        else:
            time.sleep(12)  # The IoT Box only polls the server every 10 seconds
            return self.reload_page()
