# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
import requests

from odoo import models, fields, api
from werkzeug.urls import url_join


class SocialLivePostTwitter(models.Model):
    _inherit = 'social.live.post'

    twitter_tweet_id = fields.Char('Twitter tweet id')

    def _refresh_statistics(self):
        super(SocialLivePostTwitter, self)._refresh_statistics()
        accounts = self.env['social.account'].search([('media_type', '=', 'twitter')])
        endpoint_name = 'statuses/user_timeline'
        for account in accounts:
            query_params = {
                'user_id': account.twitter_user_id,
                'tweet_mode': 'extended',
                'count': 100
            }
            tweets_endpoint_url = url_join(self.env['social.media']._TWITTER_ENDPOINT, "/1.1/%s.json" % endpoint_name)
            headers = account._get_twitter_oauth_header(
                tweets_endpoint_url,
                params=query_params,
                method='GET'
            )
            result = requests.get(
                tweets_endpoint_url,
                query_params,
                headers=headers
            )

            result_tweets = result.json()
            if isinstance(result_tweets, dict) and result_tweets.get('errors') or result_tweets is None:
                account.sudo().write({'is_media_disconnected': True})
                return

            tweets_ids = [tweet.get('id_str') for tweet in result_tweets]
            existing_live_posts = self.env['social.live.post'].sudo().search([
                ('twitter_tweet_id', 'in', tweets_ids)
            ])

            existing_live_posts_by_tweet_id = {
                live_post.twitter_tweet_id: live_post for live_post in existing_live_posts
            }

            for tweet in result_tweets:
                existing_live_post = existing_live_posts_by_tweet_id.get(tweet.get('id_str'))
                if existing_live_post:
                    likes_count = tweet.get('favorite_count', 0)
                    retweets_count = tweet.get('retweet_count', 0)
                    existing_live_post.write({
                        'engagement': likes_count + retweets_count
                    })

    def _post(self):
        twitter_live_posts = self.filtered(lambda post: post.account_id.media_type == 'twitter')
        super(SocialLivePostTwitter, (self - twitter_live_posts))._post()

        twitter_live_posts._post_twitter()

    def _post_twitter(self):
        post_endpoint_url = url_join(self.env['social.media']._TWITTER_ENDPOINT, "/1.1/statuses/update.json")

        for live_post in self:
            account = live_post.account_id
            post = live_post.post_id

            message = self._remove_mentions(post.message)
            params = {
                'status': self.env['link.tracker'].sudo()._convert_links_text(message, live_post._get_utm_values()),
            }

            images_attachments_ids = account._format_attachments_to_images_twitter(post.image_ids)
            if images_attachments_ids:
                params['media_ids'] = ','.join(images_attachments_ids)

            headers = account._get_twitter_oauth_header(
                post_endpoint_url,
                params=params
            )
            result = requests.post(
                post_endpoint_url,
                params,
                headers=headers
            )

            if (result.status_code == 200):
                live_post.twitter_tweet_id = result.json().get('id_str')
                values = {
                    'state': 'posted',
                    'failure_reason': False
                }
            else:
                values = {
                    'state': 'failed',
                    'failure_reason': result.text
                }

            live_post.write(values)

    @api.model
    def _remove_mentions(self, message):
        """Remove mentions in the Tweet message."""
        return re.sub(r'(^|[^\w\#])@(\w)', r'\1@ \2', message)
