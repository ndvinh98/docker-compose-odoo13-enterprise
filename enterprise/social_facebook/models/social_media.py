# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import requests

from odoo import _, models, fields
from odoo.exceptions import UserError
from werkzeug.urls import url_encode, url_join


class SocialMediaFacebook(models.Model):
    _inherit = 'social.media'

    _FACEBOOK_ENDPOINT = 'https://graph.facebook.com'

    media_type = fields.Selection(selection_add=[('facebook', 'Facebook')])

    def action_add_account(self):
        """ Builds the URL to Facebook with the appropriate page rights request, then redirects the client.
        Redirect is done in 'self' since Facebook will then return back to the app with the 'redirect_uri' param.

        Redirect URI from Facebook will land on this module controller's 'facebook_account_callback' method.

        Facebook will display an error message if the callback URI is not correctly defined in the Facebook APP settings. """

        self.ensure_one()

        if self.media_type != 'facebook':
            return super(SocialMediaFacebook, self).action_add_account()

        facebook_app_id = self.env['ir.config_parameter'].sudo().get_param('social.facebook_app_id')
        facebook_client_secret = self.env['ir.config_parameter'].sudo().get_param('social.facebook_client_secret')
        if facebook_app_id and facebook_client_secret:
            return self._add_facebook_accounts_from_configuration(facebook_app_id)
        else:
            return self._add_facebook_accounts_from_iap()

    def _add_facebook_accounts_from_configuration(self, facebook_app_id):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        base_facebook_url = 'https://www.facebook.com/v3.3/dialog/oauth?%s'
        params = {
            'client_id': facebook_app_id,
            'redirect_uri': url_join(base_url, "social_facebook/callback"),
            'response_type': 'token',
            'scope': 'manage_pages,publish_pages,read_insights'
        }

        return {
            'type': 'ir.actions.act_url',
            'url': base_facebook_url % url_encode(params),
            'target': 'self'
        }

    def _add_facebook_accounts_from_iap(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        social_iap_endpoint = self.env['ir.config_parameter'].sudo().get_param(
            'social.social_iap_endpoint',
            self.env['social.media']._DEFAULT_SOCIAL_IAP_ENDPOINT
        )

        iap_add_accounts_url = requests.get(url_join(social_iap_endpoint, 'iap/social_facebook/add_accounts'), params={
            'returning_url': url_join(base_url, 'social_facebook/callback'),
            'db_uuid': self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        }).text

        if iap_add_accounts_url == 'unauthorized':
            raise UserError(_("You don't have an active subscription. Please buy one here: %s") % 'https://www.odoo.com/buy')

        return {
            'type': 'ir.actions.act_url',
            'url': iap_add_accounts_url,
            'target': 'self'
        }
