# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import requests
import base64

from odoo import models, api, fields
from odoo.osv import expression
from werkzeug.urls import url_join


class SocialPostFacebook(models.Model):
    _inherit = 'social.post'

    display_facebook_preview = fields.Boolean('Display Facebook Preview', compute='_compute_display_facebook_preview')
    facebook_preview = fields.Html('Facebook Preview', compute='_compute_facebook_preview')

    @api.depends('live_post_ids.facebook_post_id')
    def _compute_stream_posts_count(self):
        super(SocialPostFacebook, self)._compute_stream_posts_count()
        for post in self:
            facebook_post_ids = [facebook_post_id for facebook_post_id in post.live_post_ids.mapped('facebook_post_id') if facebook_post_id]
            if facebook_post_ids:
                post.stream_posts_count += self.env['social.stream.post'].search_count(
                    [('facebook_post_id', 'in', facebook_post_ids)]
                )

    @api.depends('message', 'account_ids.media_id.media_type')
    def _compute_display_facebook_preview(self):
        for post in self:
            post.display_facebook_preview = post.message and ('facebook' in post.account_ids.media_id.mapped('media_type'))

    @api.depends('message', 'scheduled_date', 'image_ids')
    def _compute_facebook_preview(self):
        for post in self:
            post.facebook_preview = self.env.ref('social_facebook.facebook_preview').render({
                'message': post.message,
                'published_date': post.scheduled_date if post.scheduled_date else fields.Datetime.now(),
                'images': [
                    image.datas if not image.id
                    else base64.b64encode(open(image._full_path(image.store_fname), 'rb').read()) for image in post.image_ids
                ]
            })

    def _get_stream_post_domain(self):
        domain = super(SocialPostFacebook, self)._get_stream_post_domain()
        facebook_post_ids = [facebook_post_id for facebook_post_id in self.live_post_ids.mapped('facebook_post_id') if facebook_post_id]
        if facebook_post_ids:
            return expression.OR([domain, [('facebook_post_id', 'in', facebook_post_ids)]])
        else:
            return domain

    def _format_images_facebook(self, facebook_account_id, facebook_access_token):
        self.ensure_one()

        formatted_images = []
        for image in self.image_ids:
            facebook_photo_endpoint_url = url_join(self.env['social.media']._FACEBOOK_ENDPOINT, '/v3.2/%s/photos' % facebook_account_id)

            post_result = requests.request('POST', facebook_photo_endpoint_url, params={
                'published': 'false',
                'access_token': facebook_access_token
            }, files={'source': ('source', open(image._full_path(image.store_fname), 'rb'), image.mimetype)})

            formatted_images.append({'media_fbid': post_result.json().get('id')})

        return formatted_images
