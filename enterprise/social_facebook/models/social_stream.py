# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import dateutil.parser
import requests

from odoo import models, fields, api
from werkzeug.urls import url_join


class SocialStreamFacebook(models.Model):
    _inherit = 'social.stream'

    def _apply_default_name(self):
        for stream in self:
            if stream.media_id.media_type == 'facebook':
                if stream.account_id:
                    stream.write({'name': '%s: %s' % (stream.stream_type_id.name, stream.account_id.name)})
            else:
                super(SocialStreamFacebook, stream)._apply_default_name()

    def _fetch_stream_data(self):
        if self.media_id.media_type != 'facebook':
            return super(SocialStreamFacebook, self)._fetch_stream_data()

        if self.stream_type_id.stream_type == 'facebook_page_posts':
            return self._fetch_page_posts('feed')
        elif self.stream_type_id.stream_type == 'facebook_page_mentions':
            return self._fetch_page_posts('tagged')

    def _fetch_page_posts(self, endpoint_name):
        self.ensure_one()

        posts_endpoint_url = url_join(self.env['social.media']._FACEBOOK_ENDPOINT, "/v3.3/%s/%s" % (self.account_id.facebook_account_id, endpoint_name))
        result = requests.get(posts_endpoint_url, {
            'access_token': self.account_id.facebook_access_token,
            'fields': 'id,message,from,shares,insights.metric(post_impressions),likes.limit(1).summary(true),comments.limit(10).summary(true){message,from,like_count},attachments,created_time',
        })

        result_posts = result.json().get('data')
        if not result_posts:
            self.account_id.sudo().write({'is_media_disconnected': True})
            return False

        facebook_post_ids = [post.get('id') for post in result_posts]
        existing_posts = self.env['social.stream.post'].sudo().search([
            ('stream_id', '=', self.id),
            ('facebook_post_id', 'in', facebook_post_ids)
        ])
        existing_posts_by_facebook_post_id = {
            post.facebook_post_id: post for post in existing_posts
        }

        posts_to_create = []
        for post in result_posts:
            values = {
                'stream_id': self.id,
                'message': post.get('message'),
                'author_name': post.get('from').get('name'),
                'facebook_author_id': post.get('from').get('id'),
                'published_date': fields.Datetime.from_string(dateutil.parser.parse(post.get('created_time')).strftime('%Y-%m-%d %H:%M:%S')),
                'facebook_shares_count': post.get('shares', {}).get('count'),
                'facebook_likes_count': post.get('likes', {}).get('summary', {}).get('total_count'),
                'facebook_user_likes': post.get('likes', {}).get('summary', {}).get('has_liked'),
                'facebook_comments_count': post.get('comments', {}).get('summary', {}).get('total_count'),
                'facebook_reach': post.get('insights', {}).get('data', [{}])[0].get('values', [{}])[0].get('value'),
                'facebook_post_id': post.get('id'),
            }

            existing_post = existing_posts_by_facebook_post_id.get(post.get('id'))
            if existing_post:
                existing_post.write(values)
            else:
                # attachments are only extracted for new posts
                attachments = self._extract_facebook_attachments(post)
                if attachments or values['message']:
                    # do not create post without content
                    values.update(attachments)
                    posts_to_create.append(values)

        stream_posts = self.env['social.stream.post'].sudo().create(posts_to_create)
        return any(stream_post.stream_id.create_uid.id == self.env.uid for stream_post in stream_posts)

    @api.model
    def _extract_facebook_attachments(self, post):
        result = {}

        for attachment in post.get('attachments', {}).get('data', []):
            if attachment.get('type') == 'share':
                result.update({
                    'link_title': attachment.get('title'),
                    'link_description': attachment.get('description'),
                    'link_url': attachment.get('url'),
                })

                if attachment.get('media'):
                    result.update({
                        'link_image_url': attachment.get('media').get('image').get('src')
                    })
            elif attachment.get('type') == 'album':
                images = []
                images_urls = []
                for sub_image in attachment.get('subattachments', {}).get('data', []):
                    image_url = sub_image.get('media').get('image').get('src')
                    images.append({
                        'image_url': image_url
                    })
                    images_urls.append(image_url)

                if images:
                    result.update({
                        'stream_post_image_ids': [(0, 0, attachment) for attachment in images],
                    })
            elif attachment.get('type') == 'photo':
                result.update({
                    'stream_post_image_ids': [(0, 0, {'image_url': attachment.get('media').get('image').get('src')})],
                })

        return result
