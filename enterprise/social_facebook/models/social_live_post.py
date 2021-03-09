# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import requests

from odoo import models, fields
from werkzeug.urls import url_join


class SocialLivePostFacebook(models.Model):
    _inherit = 'social.live.post'

    facebook_post_id = fields.Char('Actual Facebook ID of the post')

    def _refresh_statistics(self):
        super(SocialLivePostFacebook, self)._refresh_statistics()
        accounts = self.env['social.account'].search([('media_type', '=', 'facebook')])

        for account in accounts:
            posts_endpoint_url = url_join(self.env['social.media']._FACEBOOK_ENDPOINT, "/v3.3/%s/%s" % (account.facebook_account_id, 'feed'))
            result = requests.get(posts_endpoint_url, {
                'access_token': account.facebook_access_token,
                'fields': 'id,shares,insights.metric(post_impressions),likes.limit(1).summary(true),comments.summary(true)'
            })

            result_posts = result.json().get('data')
            if not result_posts:
                account.sudo().write({'is_media_disconnected': True})
                return

            facebook_post_ids = [post.get('id') for post in result_posts]
            existing_live_posts = self.env['social.live.post'].sudo().search([
                ('facebook_post_id', 'in', facebook_post_ids)
            ])

            existing_live_posts_by_facebook_post_id = {
                live_post.facebook_post_id: live_post for live_post in existing_live_posts
            }

            for post in result_posts:
                existing_live_post = existing_live_posts_by_facebook_post_id.get(post.get('id'))
                if existing_live_post:
                    likes_count = post.get('likes', {}).get('summary', {}).get('total_count', 0)
                    shares_count = post.get('shares', {}).get('count', 0)
                    comments_count = post.get('comments', {}).get('summary', {}).get('total_count', 0)
                    existing_live_post.write({
                        'engagement': likes_count + shares_count + comments_count,
                    })

    def _post(self):
        facebook_live_posts = self.filtered(lambda post: post.account_id.media_type == 'facebook')
        super(SocialLivePostFacebook, (self - facebook_live_posts))._post()

        facebook_live_posts._post_facebook()

    def _post_facebook(self):
        for live_post in self:
            account = live_post.account_id
            post_endpoint_url = url_join(self.env['social.media']._FACEBOOK_ENDPOINT, "/v3.3/%s/feed" % account.facebook_account_id)

            post = live_post.post_id

            message_with_shortened_urls = self.env['link.tracker'].sudo()._convert_links_text(post.message, live_post._get_utm_values())

            params = {
                'message': message_with_shortened_urls,
                'access_token': account.facebook_access_token
            }

            if post.image_ids and len(post.image_ids) == 1:
                # if you have only 1 image, you have to use another endpoint with different parameters...
                params['caption'] = params['message']
                photos_endpoint_url = url_join(self.env['social.media']._FACEBOOK_ENDPOINT, '/v3.3/%s/photos' % account.facebook_account_id)
                image = post.image_ids[0]
                result = requests.request('POST', photos_endpoint_url, params=params,
                    files={'source': ('source', open(image._full_path(image.store_fname), 'rb'), image.mimetype)})
            else:
                if post.image_ids:
                    images_attachments = post._format_images_facebook(account.facebook_account_id, account.facebook_access_token)
                    if images_attachments:
                        for index, image_attachment in enumerate(images_attachments):
                            params.update({'attached_media[' + str(index) + ']': json.dumps(image_attachment)})

                link_url = self.env['social.post']._extract_url_from_message(message_with_shortened_urls)
                # can't combine with images
                if link_url and not post.image_ids:
                    params.update({'link': link_url})

                result = requests.post(post_endpoint_url, params)

            if (result.status_code == 200):
                live_post.facebook_post_id = result.json().get('id', False)
                values = {
                    'state': 'posted',
                    'failure_reason': False
                }
            else:
                values = {
                    'state': 'failed',
                    'failure_reason': json.loads(result.text or '{}').get('error', {}).get('message', '')
                }

            live_post.write(values)
