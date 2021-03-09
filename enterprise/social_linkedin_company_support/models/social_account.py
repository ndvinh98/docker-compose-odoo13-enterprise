# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import requests
from odoo import models
from werkzeug.urls import url_join


class SocialAccountLinkedin(models.Model):
    _inherit = 'social.account'

    _LINKEDIN_ORGANIZATION_PROJECTION = 'localizedName,vanityName,logoV2(original~:playableStreams)'

    def _get_linkedin_accounts(self, linkedin_access_token):
        """Overwrite existing method to link company pages and not personal account."""
        response = requests.get(
            url_join(self.env['social.media']._LINKEDIN_ENDPOINT, 'organizationAcls'),
            params={
                'q': 'roleAssignee',
                'role': 'ADMINISTRATOR',
                'projection': '(elements*(*,organization~(%s)))' % self.env['social.account']._LINKEDIN_ORGANIZATION_PROJECTION,
            },
            headers={
                'Authorization': 'Bearer ' + linkedin_access_token,
                'cache-control': 'no-cache',
                'X-Restli-Protocol-Version': '2.0.0'
            }).json()

        accounts = []
        if 'elements' in response and isinstance(response.get('elements'), list):
            for organization in response.get('elements'):
                image_url = self._extract_linkedin_picture_url(organization.get('organization~'))
                image_data = requests.get(image_url).content if image_url else None
                accounts.append({
                    'name': organization.get('organization~', {}).get('localizedName'),
                    'linkedin_account_id': organization.get('organization'),
                    'linkedin_access_token': linkedin_access_token,
                    'image': base64.b64encode(image_data) if image_data else False,
                })

        return accounts

    def _extract_linkedin_picture_url(self, json_data):
        """The LinkedIn API returns a very complicated and nested structure for author/company information.
        This method acts as a helper to extract the image URL from the passed data."""
        elements = None
        if json_data and 'logoV2' in json_data:
            # company picture
            elements = json_data.get('logoV2', {}).get('original~', {})
        elif json_data and 'profilePicture' in json_data:
            # personal picture
            elements = json_data.get('profilePicture', {}).get('displayImage~', {})
        if elements:
            return elements.get('elements', [{}])[0].get('identifiers', [{}])[0].get('identifier', '')
        return ''
