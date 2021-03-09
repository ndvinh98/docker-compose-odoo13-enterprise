# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
from binascii import Error as binascii_error

from odoo import models, fields, api, _


class SocialPostPushNotifications(models.Model):
    _inherit = 'social.post'

    display_push_notification_attributes = fields.Boolean('Display Push Notifications Attributes', compute="_compute_display_push_notification_attributes")
    push_notification_title = fields.Char('Push Notification Title')
    push_notification_target_url = fields.Char('Push Target URL')
    push_notification_image = fields.Binary("Push Icon Image", help="This icon will be displayed in the browser notification")

    display_push_notifications_preview = fields.Boolean('Display Push Notifications Preview', compute='_compute_display_push_notifications_preview')
    push_notifications_preview = fields.Html('Push Notifications Preview', compute='_compute_push_notifications_preview')

    use_visitor_timezone = fields.Boolean("Send at Visitors' Timezone", default=True,
        help="e.g: If you post at 15:00, visitors will receive the post at 15:00 their time.")
    visitor_domain = fields.Char(string="Visitor Domain", default=[['push_token', '!=', False]], help="Domain to send push notifications to visitors.")

    @api.depends('message', 'account_ids.media_id.media_type')
    def _compute_display_push_notifications_preview(self):
        for post in self:
            post.display_push_notifications_preview = post.message \
                and ('push_notifications' in post.account_ids.media_id.mapped('media_type'))

    @api.depends('message', 'push_notification_title', 'push_notification_image')
    def _compute_push_notifications_preview(self):
        for post in self:
            icon = False
            icon_url = False
            if post.push_notification_image:
                try:
                    base64.b64decode(post.push_notification_image, validate=True)
                    icon = post.push_notification_image
                except binascii_error:
                    if post.id or (post._origin and post._origin.id):
                        icon_url = '/web/image/social.post/%s/push_notification_image' % (post.id if post.id else post._origin.id)

            post.push_notifications_preview = self.env.ref('social_push_notifications.push_notifications_preview').render({
                'title': post.push_notification_title or _('New Message'),
                'icon': icon,
                'icon_url': icon_url,
                'message': post.message,
                'host_name': self.env['ir.config_parameter'].sudo().get_param('web.base.url') or 'https://myapp.com'
            })

    @api.depends('account_ids.media_id.media_type')
    def _compute_display_push_notification_attributes(self):
        for post in self:
            post.display_push_notification_attributes = 'push_notifications' in post.account_ids.media_id.mapped('media_type')

    @api.model_create_multi
    def create(self, vals_list):
        """ Assign a default push_notification_target_url is none specified and we can extract one from the message """
        for i in range(len(vals_list)):
            if not vals_list[i].get('push_notification_target_url'):
                extracted_url = self._extract_url_from_message(vals_list[i]['message'])
                if extracted_url:
                    vals_list[i]['push_notification_target_url'] = extracted_url
        return super(SocialPostPushNotifications, self).create(vals_list)

    def write(self, vals):
        """ Assign a default push_notification_target_url is none specified and we can extract one from the message """
        if not any(post.push_notification_target_url for post in self) and vals.get('message'):
            extracted_url = self._extract_url_from_message(vals['message'])
            if extracted_url:
                vals['push_notification_target_url'] = extracted_url
        return super(SocialPostPushNotifications, self).write(vals)

    @api.model
    def _cron_publish_scheduled(self):
        """ This method is overridden to gather all pending push live.posts ('ready' state) and post them.
        This is done in the cron job instead of instantly to avoid blocking the 'Post' action of the user
        indefinitely.

        The related social.post will remain 'pending' until all live.posts are processed. """

        super(SocialPostPushNotifications, self)._cron_publish_scheduled()

        ready_live_posts = self.env['social.live.post'].search([
            ('state', 'in', ['ready', 'posting'])
        ])
        push_notifications_live_posts = ready_live_posts.filtered(
            lambda post: post.account_id.media_type == 'push_notifications'
        )
        push_notifications_live_posts.write({
            'state': 'posting'
        })
        push_notifications_live_posts._post_push_notifications()
