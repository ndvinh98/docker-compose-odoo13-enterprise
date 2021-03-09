# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from odoo import models, api, fields
from odoo.osv import expression


class SocialPostTwitter(models.Model):
    _inherit = 'social.post'

    display_twitter_preview = fields.Boolean('Display Twitter Preview', compute='_compute_display_twitter_preview')
    twitter_preview = fields.Html('Twitter Preview', compute='_compute_twitter_preview')

    @api.depends('live_post_ids.twitter_tweet_id')
    def _compute_stream_posts_count(self):
        super(SocialPostTwitter, self)._compute_stream_posts_count()
        for post in self:
            twitter_tweet_ids = [twitter_tweet_id for twitter_tweet_id in post.live_post_ids.mapped('twitter_tweet_id') if twitter_tweet_id]
            if twitter_tweet_ids:
                post.stream_posts_count += self.env['social.stream.post'].search_count(
                    [('twitter_tweet_id', 'in', twitter_tweet_ids)]
                )

    @api.depends('message', 'account_ids.media_id.media_type')
    def _compute_display_twitter_preview(self):
        for post in self:
            post.display_twitter_preview = post.message and ('twitter' in post.account_ids.media_id.mapped('media_type'))

    @api.depends('message', 'scheduled_date', 'image_ids')
    def _compute_twitter_preview(self):
        for post in self:
            message = self.env["social.live.post"]._remove_mentions(post.message or "")
            post.twitter_preview = self.env.ref('social_twitter.twitter_preview').render({
                'message': message,
                'images': [
                    image.datas if not image.id
                    else base64.b64encode(open(image._full_path(image.store_fname), 'rb').read()) for image in post.image_ids
                ]
            })

    def _get_stream_post_domain(self):
        domain = super(SocialPostTwitter, self)._get_stream_post_domain()
        twitter_tweet_ids = [twitter_tweet_id for twitter_tweet_id in self.live_post_ids.mapped('twitter_tweet_id') if twitter_tweet_id]
        if twitter_tweet_ids:
            return expression.OR([domain, [('twitter_tweet_id', 'in', twitter_tweet_ids)]])
        else:
            return domain
