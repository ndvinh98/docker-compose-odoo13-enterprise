# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import json

import requests
import werkzeug
from werkzeug.urls import url_encode, url_join

from odoo import http
from odoo.http import request


class SocialTwitterController(http.Controller):
    # ========================================================
    # Accounts management
    # ========================================================

    @http.route('/social_twitter/callback', type='http', auth='user')
    def twitter_account_callback(self, oauth_token=None, oauth_verifier=None, iap_twitter_consumer_key=None):
        """ When we add accounts though IAP, we copy the 'iap_twitter_consumer_key' to our media's twitter_consumer_key.
        This allows preparing the signature process and the information is not sensitive so we can take advantage of it. """
        if not request.env.user.has_group('social.group_social_manager'):
            return 'unauthorized'

        if oauth_token and oauth_verifier:
            if iap_twitter_consumer_key:
                request.env['ir.config_parameter'].sudo().set_param('social.twitter_consumer_key', iap_twitter_consumer_key)

            media = request.env['social.media'].search([('media_type', '=', 'twitter')], limit=1)

            self._create_twitter_accounts(oauth_token, oauth_verifier, media)

        url_params = {
            'action': request.env.ref('social.action_social_stream_post').id,
            'view_type': 'kanban',
            'model': 'social.stream.post',
        }

        url = '/web?#%s' % url_encode(url_params)
        return werkzeug.utils.redirect(url)

    def _create_twitter_accounts(self, oauth_token, oauth_verifier, media):
        twitter_consumer_key = request.env['ir.config_parameter'].sudo().get_param('social.twitter_consumer_key')

        twitter_access_token_url = url_join(request.env['social.media']._TWITTER_ENDPOINT, "oauth/access_token")
        response = requests.post(twitter_access_token_url, data={
            'oauth_consumer_key': twitter_consumer_key,
            'oauth_token': oauth_token,
            'oauth_verifier': oauth_verifier
        })

        response_values = {
            response_value.split('=')[0]: response_value.split('=')[1]
            for response_value in response.text.split('&')
        }

        existing_account = request.env['social.account'].search([
            ('media_id', '=', media.id),
            ('twitter_user_id', '=', response_values['user_id'])
        ])

        if existing_account:
            existing_account.write({
                'is_media_disconnected': False,
                'twitter_screen_name': response_values['screen_name'],
                'twitter_oauth_token': response_values['oauth_token'],
                'twitter_oauth_token_secret': response_values['oauth_token_secret']
            })
        else:
            twitter_account_information = self._get_twitter_account_information(
                media,
                response_values['oauth_token'],
                response_values['oauth_token_secret'],
                response_values['screen_name']
            )

            request.env['social.account'].create({
                'media_id': media.id,
                'name': twitter_account_information['name'],
                'twitter_user_id': response_values['user_id'],
                'twitter_screen_name': response_values['screen_name'],
                'twitter_oauth_token': response_values['oauth_token'],
                'twitter_oauth_token_secret': response_values['oauth_token_secret'],
                'image': base64.b64encode(requests.get(twitter_account_information['profile_image_url_https']).content)
            })

    def _get_twitter_account_information(self, media, oauth_token, oauth_token_secret, screen_name):
        twitter_account_info_url = url_join(request.env['social.media']._TWITTER_ENDPOINT, "/1.1/users/show.json")

        headers = media._get_twitter_oauth_header(
            twitter_account_info_url,
            headers={
                'oauth_token': oauth_token,
                'oauth_token_secret': oauth_token_secret,
            },
            params={'screen_name': screen_name},
            method='GET'
        )

        response = requests.get(twitter_account_info_url, params={
            'screen_name': screen_name
        }, headers=headers)
        return response.json()

    # ========================================================
    # Comments and likes
    # ========================================================

    @http.route('/social_twitter/<int:stream_id>/like_tweet', type='json')
    def like_tweet(self, stream_id, tweet_id, like):
        stream = request.env['social.stream'].browse(stream_id)
        if not stream or stream.media_id.media_type != 'twitter':
            return {}

        favorites_endpoint = url_join(request.env['social.media']._TWITTER_ENDPOINT, ('/1.1/favorites/create.json' if like else '/1.1/favorites/destroy.json'))
        headers = stream.account_id._get_twitter_oauth_header(
            favorites_endpoint,
            params={'id': tweet_id}
        )
        requests.post(
            favorites_endpoint,
            {'id': tweet_id},
            headers=headers
        )

    @http.route('/social_twitter/<int:stream_id>/comment', type='http')
    def comment(self, stream_id=None, post_id=None, comment_id=None, message=None, **kwargs):
        stream = request.env['social.stream'].browse(stream_id)
        if not stream or stream.media_id.media_type != 'twitter':
            return {}

        post = request.env['social.stream.post'].browse(int(post_id))
        tweet_id = comment_id or post.twitter_tweet_id
        message = request.env["social.live.post"]._remove_mentions(message)
        params = {
            'status': message,
            'in_reply_to_status_id': tweet_id,
            'tweet_mode': 'extended',
        }

        attachment = None
        files = request.httprequest.files.getlist('attachment')
        if files and files[0]:
            attachment = files[0]

        if attachment:
            images_attachments_ids = stream.account_id._format_bytes_to_images_twitter(attachment)
            if images_attachments_ids:
                params['media_ids'] = ','.join(images_attachments_ids)

        post_endpoint_url = url_join(request.env['social.media']._TWITTER_ENDPOINT, "/1.1/statuses/update.json")
        headers = stream.account_id._get_twitter_oauth_header(
            post_endpoint_url,
            params=params
        )
        result = requests.post(
            post_endpoint_url,
            params,
            headers=headers
        )

        tweet = result.json()

        formatted_tweet = request.env['social.media']._format_tweet(tweet)

        return json.dumps(formatted_tweet)
