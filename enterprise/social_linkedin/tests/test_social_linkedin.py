# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import requests

from unittest.mock import patch
from odoo.addons.social.tests.common import SocialCase
from odoo.addons.social_linkedin.models.social_live_post import SocialLivePostLinkedin


class SocialLinkedinCase(SocialCase):
    @classmethod
    def setUpClass(cls):
        super(SocialLinkedinCase, cls).setUpClass()
        cls.social_accounts.write({'linkedin_access_token': 'ABCD'})

    def test_post_success(self):
        self._test_post()

    def test_post_failure(self):
        self._test_post(False)

    def _test_post(self, success=True):
        self.assertEqual(self.social_post.state, 'draft')

        def _patched_post(*args, **kwargs):
            response = requests.Response()
            if success:
                response._content = b'{"id": "42"}'
                response.status_code = 200
            else:
                response._content = b'{"serviceErrorCode": 65600}'
                response.status_code = 404
            return response

        with patch.object(requests, 'post', _patched_post), \
             patch.object(SocialLivePostLinkedin, '_likedin_upload_image', lambda *a, **kw: 'fake_image_urn'):
            self.social_post._action_post()

        self._checkPostedStatus(success)

        if success:
            self.assertTrue(
                all([not account.is_media_disconnected for account in self.social_post.account_ids]),
                'Accounts should not be marked disconnected if post is successful')
        else:
            self.assertTrue(
                all([account.is_media_disconnected for account in self.social_post.account_ids]),
                'Accounts should be marked disconnected if post has failed')

    def test_post_image(self):
        """
        Check the priority of the ``post type``
        The first priority is image
        """
        self.social_post.message = 'A message https://odoo.com'
        self.assertTrue(self.social_post.image_ids)
        self._test_post_type('IMAGE')

    def test_post_urls(self):
        """
        Check the priority of the ``post type``
        The second priority is urls
        """
        self.social_post.message = 'A message https://odoo.com'
        self.social_post.image_ids = False
        self._test_post_type('ARTICLE')

    def test_post_text(self):
        """
        Check the priority of the ``post type``
        The last priority is text
        """
        self.social_post.message = 'A message without URL'
        self.social_post.image_ids = False
        self._test_post_type('NONE')

    def _test_post_type(self, expected_post_type):
        self.assertEqual(self.social_post.state, 'draft')

        def _patched_post(*args, **kwargs):
            response = requests.Response()
            response._content = b'{"id": "42"}'
            response.status_code = 200

            post_type = (kwargs.get('json', {})
                         .get('specificContent', {})
                         .get('com.linkedin.ugc.ShareContent', {})
                         .get('shareMediaCategory', ''))

            responses.append(post_type)
            return response

        responses = []
        with patch.object(requests, 'post', _patched_post), \
             patch.object(SocialLivePostLinkedin, '_likedin_upload_image', lambda *a, **kw: 'fake_image_urn'):
            self.social_post._action_post()

        self.assertTrue(responses)
        self.assertTrue(all([response == expected_post_type for response in responses]),
                        'The post type must be [%s]' % expected_post_type)

    @classmethod
    def _get_social_media(cls):
        return cls.env.ref('social_linkedin.social_media_linkedin')
