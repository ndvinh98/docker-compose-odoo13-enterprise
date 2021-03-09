# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import json

import requests
import werkzeug
import urllib.parse
from werkzeug.urls import url_encode, url_join

from odoo import http
from odoo.http import request
from odoo.addons.auth_oauth.controllers.main import fragment_to_query_string


class SocialFacebookController(http.Controller):
    # ========================================================
    # Accounts management
    # ========================================================

    @fragment_to_query_string
    @http.route(['/social_facebook/callback'], type='http', auth='user')
    def facebook_account_callback(self, access_token=None, is_extended_token=False):
        if not request.env.user.has_group('social.group_social_manager'):
            return 'unauthorized'

        """ Facebook returns to the callback URL with all its own arguments as hash parameters.
        We use this very handy 'fragment_to_query_string' decorator to convert them to server readable parameters. """

        if access_token:
            media = request.env.ref('social_facebook.social_media_facebook')
            self._create_facebook_accounts(access_token, media, is_extended_token)

        url_params = {
            'action': request.env.ref('social.action_social_stream_post').id,
            'view_type': 'kanban',
            'model': 'social.stream.post',
        }

        url = '/web?#%s' % url_encode(url_params)
        return werkzeug.utils.redirect(url)

    def _create_facebook_accounts(self, access_token, media, is_extended_token):
        """ Steps to create the facebook social.accounts:
        1. Fetch an extended access token (see '_get_extended_access_token' for more info)
        2. Query the accounts api with that token
        3. Extract the 'pages' contained in the json result
        4. Create a social.account with its associated token (each page has its own access token)
        4a. If the social.account was already created before, we refresh its access_token """

        extended_access_token = access_token if is_extended_token else self._get_extended_access_token(access_token, media)
        accounts_url = url_join(request.env['social.media']._FACEBOOK_ENDPOINT, "/me/accounts/")
        accounts_request = requests.get(accounts_url, params={
            'access_token': extended_access_token
        })
        json_response = accounts_request.json()

        accounts_to_create = []
        existing_accounts = self._get_existing_accounts(media, json_response)
        for account in json_response.get('data'):
            account_id = account['id']
            access_token = account.get('access_token')
            if existing_accounts.get(account_id):
                # update access token
                # TODO awa: maybe check for name/picture update?
                existing_accounts.get(account_id).write({
                    'facebook_access_token': access_token,
                    'is_media_disconnected': False
                })
            else:
                accounts_to_create.append({
                    'name': account.get('name'),
                    'media_id': media.id,
                    'has_trends': True,
                    'facebook_account_id': account_id,
                    'facebook_access_token': access_token,
                    'image': self._get_profile_image(account_id)
                })

        if accounts_to_create:
            request.env['social.account'].create(accounts_to_create)

    def _get_extended_access_token(self, access_token, media):
        """ The way that it works is Facebook sends you a token that is valid for 2 hours
        that you can automatically 'extend' to a 60 days token using the oauth/access_token endpoint.

        After those 60 days, there is absolutely no way to renew the token automatically, we have to ask
        the user's permissions again manually.
        However, using this extended token with the 'manage_pages' permission allows receiving 'Page Access Tokens'
        that are valid forever.

        More details on this mechanic: https://www.devils-heaven.com/facebook-access-tokens/ """

        facebook_app_id = request.env['ir.config_parameter'].sudo().get_param('social.facebook_app_id')
        facebook_client_secret = request.env['ir.config_parameter'].sudo().get_param('social.facebook_client_secret')
        extended_token_url = url_join(request.env['social.media']._FACEBOOK_ENDPOINT, "/oauth/access_token")
        extended_token_request = requests.post(extended_token_url, params={
            'client_id': facebook_app_id,
            'client_secret': facebook_client_secret,
            'grant_type': 'fb_exchange_token',
            'fb_exchange_token': access_token
        })
        return extended_token_request.json().get('access_token')

    def _get_profile_image(self, account_id):
        profile_image_url = url_join(request.env['social.media']._FACEBOOK_ENDPOINT, '/v3.3/%s/picture?height=300' % account_id)
        return base64.b64encode(requests.get(profile_image_url).content)

    def _get_existing_accounts(self, media_id, json_response):
        """ Returns the social.accounts already created as:
        { facebook_account_id: social.account } """

        facebook_accounts_ids = [account['id'] for account in json_response.get('data', [])]
        if facebook_accounts_ids:
            existing_accounts = request.env['social.account'].search([
                ('media_id', '=', int(media_id)),
                ('facebook_account_id', 'in', facebook_accounts_ids)
            ])

            return {
                existing_account.facebook_account_id: existing_account
                for existing_account in existing_accounts
            }

        return {}

    # ========================================================
    # Comments and likes
    # ========================================================

    @http.route(['/social_facebook/comment'], type='http', auth='user')
    def add_comment(self, post_id=None, message=None, comment_id=None, existing_attachment_id=None, is_edit=False, **kwargs):
        stream_post = request.env['social.stream.post'].browse(int(post_id))

        attachment = None
        files = request.httprequest.files.getlist('attachment')
        if files and files[0]:
            attachment = files[0]

        if comment_id:
            if is_edit:
                result = stream_post._edit_facebook_comment(message, comment_id, existing_attachment_id, attachment)
            else:
                result = stream_post._add_facebook_comment(message, comment_id, existing_attachment_id, attachment)
        else:
            result = stream_post._add_facebook_comment(message, stream_post.facebook_post_id, existing_attachment_id, attachment)

        result['formatted_created_time'] = request.env['social.stream.post']._format_facebook_published_date(result)
        return json.dumps(result)

    # ========================================================
    # Redirection to Facebook
    # ========================================================

    @http.route(['/social_facebook/redirect_to_profile/<int:account_id>/<facebook_user_id>'], type='http', auth='user')
    def facebook_redirect_to_profile(self, account_id, facebook_user_id, name=''):
        """
        All profiles are not available through a direct link so we need to
        - Try to get a direct link to their profile
        - If we can't, we perform a search on Facebook with their name
        """
        account = request.env['social.account'].browse(account_id)

        endpoint_url = url_join(request.env['social.media']._FACEBOOK_ENDPOINT, '/v4.0/%s?fields=name,link' % facebook_user_id)

        json_response = requests.get(endpoint_url, params={
            'access_token': account.facebook_access_token
        }).json()

        profile_url = json_response.get('link')
        if profile_url:
            redirect_url = profile_url
        else:
            redirect_url = 'https://www.facebook.com/search/?q=%s' % urllib.parse.quote(name)

        return werkzeug.utils.redirect(redirect_url)
