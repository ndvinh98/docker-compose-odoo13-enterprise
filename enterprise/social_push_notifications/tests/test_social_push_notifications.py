# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from firebase_admin import messaging

from unittest.mock import patch

from odoo.addons.social.tests.common import SocialCase
from odoo.addons.social_push_notifications.models.social_account import SocialAccountPushNotifications


class SocialPushNotificationsCase(SocialCase):
    @classmethod
    def setUpClass(cls):
        super(SocialPushNotificationsCase, cls).setUpClass()
        cls.social_accounts.write({'firebase_use_own_account': True})

    def test_post(self):
        # Create some visitors with or without push_token in different timezone
        timezones = ['Europe/Brussels', 'America/New_York', 'Asia/Vladivostok']
        Visitor = self.env['website.visitor']
        visitor_vals = []
        for i in range(0, 3):
            visitor_vals.append({
                'name': timezones[i],
                'timezone': timezones[i],
                'push_token': 'fake_token_%s' % i if i != 0 else False,
            })
        visitors = Visitor.create(visitor_vals)
        self.social_post.create_uid.write({'tz': timezones[0]})

        self.assertEqual(self.social_post.state, 'draft')

        self.social_post._action_post()

        live_posts = self.env['social.live.post'].search([('post_id', '=', self.social_post.id)])
        # make sure live_posts' create_date is after 'now'
        live_posts.write({'create_date': live_posts[0].create_date - datetime.timedelta(minutes=1)})
        self.assertEqual(len(live_posts), 2)

        self.assertTrue(all(live_post.state == 'ready' for live_post in live_posts))
        self.assertEqual(self.social_post.state, 'posting')

        responses = [self._makeSendResponse() for i in range(2)]

        def _patched_send_multicast(*args, **kwargs):
            return messaging.BatchResponse(
                responses
            )

        # Post for visitor for which their timezone allows to receive the push notification (if their time > time of the one who created the post)
        with patch.object(SocialAccountPushNotifications, '_init_firebase_app', lambda *args, **kwargs: None), \
                patch.object(messaging, 'send_multicast', _patched_send_multicast):
            live_posts._post_push_notifications()

        self.assertFalse(all(live_post.state == 'posted' for live_post in live_posts))
        self.assertEqual(self.social_post.state, 'posting')

        # simulate that everyone can receive the push notif (because their time >= time of the one who created the post)
        visitors.write({'timezone': self.env.user.tz})

        with patch.object(SocialAccountPushNotifications, '_init_firebase_app', lambda *args, **kwargs: None), \
                patch.object(messaging, 'send_multicast', _patched_send_multicast):
            live_posts._post_push_notifications()

        self._checkPostedStatus(True)

    def _makeSendResponse(self):
        return messaging.SendResponse(None, None)

    @classmethod
    def _get_social_media(cls):
        return cls.env.ref('social_push_notifications.social_media_push_notifications')
