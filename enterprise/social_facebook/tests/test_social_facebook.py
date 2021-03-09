# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import requests

from unittest.mock import patch

from odoo.addons.social_facebook.models.social_account import SocialAccountFacebook
from odoo.addons.social_facebook.models.social_post import SocialPostFacebook
from odoo.addons.social.tests.common import SocialCase


class SocialFacebookCase(SocialCase):
    @classmethod
    def setUpClass(cls):
        with patch.object(SocialAccountFacebook, '_compute_statistics', lambda x: None), \
             patch.object(SocialAccountFacebook, '_create_default_stream_facebook', lambda *args, **kwargs: None):
            super(SocialFacebookCase, cls).setUpClass()

    def test_post_success(self):
        self._test_post()

    def test_post_failure(self):
        self._test_post(False)

    def _test_post(self, success=True):
        self.assertEqual(self.social_post.state, 'draft')

        def _patched_post(*args, **kwargs):
            response = requests.Response()
            if success:
                response._content = json.dumps({'id': 42}).encode('utf-8')
                response.status_code = 200
            else:
                response.status_code = 404
            return response

        with patch.object(SocialPostFacebook, '_format_images_facebook', lambda *args, **kwargs: {'media_fbid': 1}), \
             patch.object(requests, 'post', _patched_post):
                self.social_post._action_post()

        self._checkPostedStatus(success)

    @classmethod
    def _get_social_media(cls):
        return cls.env.ref('social_facebook.social_media_facebook')
