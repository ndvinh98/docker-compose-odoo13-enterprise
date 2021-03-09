# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

import requests
from werkzeug.urls import url_join

from odoo import api, fields, models

TWITTER_IMAGES_UPLOAD_ENDPOINT = "https://upload.twitter.com/1.1/media/upload.json"


class SocialAccountTwitter(models.Model):
    _inherit = 'social.account'

    twitter_user_id = fields.Char('Twitter User ID')
    twitter_screen_name = fields.Char('Twitter Screen ID')
    twitter_oauth_token = fields.Char('Twitter OAuth Token')
    twitter_oauth_token_secret = fields.Char('Twitter OAuth Token Secret')

    def _compute_statistics(self):
        """ See methods '_get_last_tweets_stats' for more info about Twitter stats. """

        twitter_accounts = self.filtered(lambda account: account.media_type == 'twitter')
        super(SocialAccountTwitter, (self - twitter_accounts))._compute_statistics()

        for account in twitter_accounts:
            account_stats = account._get_account_stats()
            last_tweets_stats = account._get_last_tweets_stats()

            if account_stats and last_tweets_stats:
                account.write({
                    'audience': account_stats.get('followers_count'),
                    'engagement': last_tweets_stats['engagement'],
                    'stories': last_tweets_stats['stories'],
                })

    def _compute_stats_link(self):
        twitter_accounts = self.filtered(lambda account: account.media_type == 'twitter')
        super(SocialAccountTwitter, (self - twitter_accounts))._compute_stats_link()

        for account in twitter_accounts:
            account.stats_link = "https://analytics.twitter.com/user/%s" % account.twitter_screen_name

    @api.model_create_multi
    def create(self, vals_list):
        res = super(SocialAccountTwitter, self).create(vals_list)
        res.filtered(lambda account: account.media_type == 'twitter')._create_default_stream_twitter()
        return res

    def twitter_search_users(self, query):
        """ Used to autocomplete the 'follow' stream user search """

        user_search_endpoint = url_join(self.env['social.media']._TWITTER_ENDPOINT, "/1.1/users/search.json")
        params = {'count': 5, 'q': query}
        headers = self._get_twitter_oauth_header(
            user_search_endpoint,
            params=params,
            method='GET'
        )
        result = requests.get(
            user_search_endpoint,
            params,
            headers=headers
        )
        return result.json()

    def _create_default_stream_twitter(self):
        """ This will create a stream of type 'Twitter Follow' for each added accounts.
        It helps with onboarding to have your tweets show up on the 'Feed' view as soon as you have configured your accounts."""

        if not self:
            return

        own_tweets_stream_type_id = self.env.ref('social_twitter.stream_type_twitter_follow').id
        streams_to_create = []
        for account in self:
            # we have to create a matching social.twitter.account for each stream
            twitter_followed_account = self.env['social.twitter.account'].create({
                'name': account.name,
                'twitter_id': account.twitter_user_id,
                'image': account.image
            })
            streams_to_create.append({
                'media_id': account.media_id.id,
                'stream_type_id': own_tweets_stream_type_id,
                'account_id': account.id,
                'twitter_followed_account_id': twitter_followed_account.id
            })
        self.env['social.stream'].create(streams_to_create)

    def _get_account_stats(self):
        """ Query the account information to retrieve the Twitter audience (= followers count). """

        self.ensure_one()

        twitter_account_info_url = url_join(self.env['social.media']._TWITTER_ENDPOINT, "/1.1/users/show.json")
        headers = self._get_twitter_oauth_header(
            twitter_account_info_url,
            params={'screen_name': self.twitter_screen_name},
            method='GET'
        )

        result = requests.get(
            twitter_account_info_url,
            params={'screen_name': self.twitter_screen_name},
            headers=headers
        )

        if isinstance(result.json(), dict) and result.json().get('errors'):
            self.sudo().write({'is_media_disconnected': True})
            return False

        return result.json()

    def _get_last_tweets_stats(self):
        """ To properly retrieve statistics and trends, we would need an Enterprise 'Engagement API' access.
        See: https://developer.twitter.com/en/docs/metrics/get-tweet-engagement/overview

        Since we don't have access, we use the last 200 user tweets (max for one request) to aggregate
        the data we are able to retrieve. """

        self.ensure_one()

        tweets_endpoint_url = url_join(self.env['social.media']._TWITTER_ENDPOINT, "/1.1/statuses/user_timeline.json")
        params = {
            'count': 200,
            'user_id': self.twitter_user_id
        }
        headers = self._get_twitter_oauth_header(
            tweets_endpoint_url,
            params=params,
            method='GET'
        )
        result = requests.get(
            tweets_endpoint_url,
            params,
            headers=headers
        )

        if isinstance(result.json(), dict) and result.json().get('errors'):
            self.sudo().write({'is_media_disconnected': True})
            return False

        last_tweets_stats = {
            'engagement': 0,
            'stories': 0
        }
        for tweet in result.json():
            last_tweets_stats['engagement'] += tweet.get('favorite_count')
            last_tweets_stats['stories'] += tweet.get('retweet_count')

        return last_tweets_stats

    def _get_twitter_oauth_header(self, url, headers={}, params={}, method='POST'):
        self.ensure_one()
        headers.update({
            'oauth_token': self.twitter_oauth_token,
            'oauth_token_secret': self.twitter_oauth_token_secret,
        })
        return self.media_id._get_twitter_oauth_header(url, headers=headers, params=params, method=method)

    def _format_attachments_to_images_twitter(self, image_ids):
        return self._format_images_twitter([{
            'bytes': base64.decodebytes(image.datas),
            'file_size': image.file_size,
            'mimetype': image.mimetype
        } for image in image_ids])

    def _format_bytes_to_images_twitter(self, attachment):
        bytes_data = attachment.read()
        return self._format_images_twitter([{'bytes': bytes_data, 'file_size': len(bytes_data), 'mimetype': attachment.content_type}])

    def _format_images_twitter(self, image_ids):
        """ Twitter needs a special kind of uploading to process images.
        It's done in 3 steps:
        - initialize upload transaction
        - send bytes
        - finalize upload transaction.

        More information: https://developer.twitter.com/en/docs/media/upload-media/api-reference/post-media-upload.html """

        self.ensure_one()

        if not image_ids:
            return False

        media_ids = []
        for image in image_ids:
            media_id = self._init_twitter_upload(image)
            self._process_twitter_upload(image, media_id)
            self._finish_twitter_upload(media_id)
            media_ids.append(media_id)

        return media_ids

    def _init_twitter_upload(self, image):
        data = {
            'command': 'INIT',
            'total_bytes': image['file_size'],
            'media_category': 'tweet_gif' if image['mimetype'] == 'image/gif' else 'tweet_image',
            'media_type': image['mimetype'],
        }
        headers = self._get_twitter_oauth_header(
            TWITTER_IMAGES_UPLOAD_ENDPOINT,
            params=data
        )
        result = requests.post(
            TWITTER_IMAGES_UPLOAD_ENDPOINT,
            data=data,
            headers=headers,
        )
        return result.json().get('media_id_string')

    def _process_twitter_upload(self, image, media_id):
        params = {
            'command': 'APPEND',
            'media_id': media_id,
            'segment_index': 0,
        }
        files = {
            'media': image['bytes']
        }
        headers = self._get_twitter_oauth_header(
            TWITTER_IMAGES_UPLOAD_ENDPOINT,
            params=params
        )
        requests.post(
            TWITTER_IMAGES_UPLOAD_ENDPOINT,
            params=params,
            files=files,
            headers=headers,
        )

    def _finish_twitter_upload(self, media_id):
        data = {
            'command': 'FINALIZE',
            'media_id': media_id,
        }
        headers = self._get_twitter_oauth_header(
            TWITTER_IMAGES_UPLOAD_ENDPOINT,
            params=data
        )
        requests.post(
            TWITTER_IMAGES_UPLOAD_ENDPOINT,
            data=data,
            headers=headers,
        )
