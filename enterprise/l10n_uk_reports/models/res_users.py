# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api

class User(models.Model):
    _inherit = 'res.users'

    l10n_uk_user_token = fields.Char('User Token', copy=False, groups='base.group_system',
                                     help="Is a token given by the Odoo server used to refresh the access token. ")
    l10n_uk_hmrc_vat_token = fields.Char("Oauth Access Token", copy=False, groups='base.group_system',
                                         help="This is the token given by the government to access its api. ")
    l10n_uk_hmrc_vat_token_expiration_time = fields.Datetime("Oauth access token expiration time", copy=False, groups='base.group_system',
                                                             help="When the access token expires, then it can be refreshed"
                                                                  "through the Odoo server with the user token. ")

    def hmrc_reset_tokens(self):
        self.ensure_one()
        self.env['hmrc.service'].sudo(self.id)._clean_tokens()
        return True
