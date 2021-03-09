# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models

# ----------------------------------------------------------
# Models
# ----------------------------------------------------------


class OnsipConfigurator(models.Model):
    _inherit = 'voip.configurator'

    @api.model
    def get_pbx_config(self):
        result = super(OnsipConfigurator, self).get_pbx_config()
        result.update(onsip_auth_user=self.env.user.onsip_auth_user)
        return result
