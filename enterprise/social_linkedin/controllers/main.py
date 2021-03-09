# -*- coding: utf-8 -*-
import requests
import werkzeug

from odoo import http
from odoo.http import request
from odoo.tools import html_escape
from werkzeug.urls import url_encode


class SocialLinkedin(http.Controller):
    @http.route(['/social_linkedin/callback'], type='http', auth='user')
    def social_linkedin_callback(self, **kw):
        """
        We can receive
        - authorization_code directly from LinkedIn
        - access_token from IAP
        """
        if not request.env.user.has_group('social.group_social_manager'):
            return 'unauthorized'

        if kw.get('error') != 'user_cancelled_authorize':
            # we received the access_token from IAP
            access_token = kw.get('access_token')
            # we receive authorization_code from LinkedIn
            authorization_code = kw.get('code')

            linkedin_csrf = kw.get('state')
            media = request.env.ref('social_linkedin.social_media_linkedin')

            if media._compute_linkedin_csrf() != linkedin_csrf:
                return 'Wrong CSRF token'

            if not access_token:
                if not authorization_code:
                    return 'An error occurred. Authorization code is missing.'
                else:
                    # if we do not have the acces_token, we should exchange the
                    # authorization_code for an access token
                    try:
                        access_token = self._get_linkedin_access_token(authorization_code, media)
                    except Exception as e:
                        return html_escape(str(e))

            request.env['social.account']._create_linkedin_accounts(access_token, media)

        url_params = {
            'action': request.env.ref('social.action_social_stream_post').id,
            'view_type': 'kanban',
            'model': 'social.stream.post',
        }

        return werkzeug.utils.redirect('/web?#%s' % url_encode(url_params))

    def _get_linkedin_access_token(self, linkedin_authorization_code, media):
        """
        Take the `authorization code` and exchange it for an `access token`
        We also need the `redirect uri`

        :return: the access token
        """
        linkedin_url = 'https://www.linkedin.com/oauth/v2/accessToken'
        linkedin_app_id = request.env['ir.config_parameter'].sudo().get_param('social.linkedin_app_id')
        linkedin_client_secret = request.env['ir.config_parameter'].sudo().get_param('social.linkedin_client_secret')

        params = {
            'grant_type': 'authorization_code',
            'code': linkedin_authorization_code,
            'redirect_uri': media._get_linkedin_redirect_uri(),
            'client_id': linkedin_app_id,
            'client_secret': linkedin_client_secret
        }

        response = requests.post(linkedin_url, data=params).json()

        error_description = response.get('error_description')
        if error_description:
            raise Exception(error_description)

        return response.get('access_token')
