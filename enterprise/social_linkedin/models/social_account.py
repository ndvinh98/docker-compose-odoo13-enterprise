# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import requests
from odoo import models, fields


class SocialAccountLinkedin(models.Model):
    _inherit = 'social.account'

    linkedin_account_id = fields.Char(string='LinkedIn Account ID/URN',
        readonly=True, help='LinkedIn Account ID/URN')
    linkedin_access_token = fields.Char(string='LinkedIn access token',
        readonly=True, help='The access token is used to perform request to the REST API')

    def _bearer_headers(self):
        headers = {
            'Authorization': 'Bearer ' + self.linkedin_access_token,
            'cache-control': 'no-cache',
            'X-Restli-Protocol-Version': '2.0.0'
        }

        return headers

    def _get_linkedin_accounts(self, linkedin_access_token):
        """
        Make an API call to get all LinkedIn accounts linked to
        the actual access token (personal account, company page...).

        :return: all accounts linked to the access token
        """
        response = requests.get(
            'https://api.linkedin.com/v2/me?projection='
            + '(id,localizedLastName,localizedFirstName,'
            + 'profilePicture(displayImage~:playableStreams))',
            headers={
                'Authorization': 'Bearer ' + linkedin_access_token,
                'cache-control': 'no-cache',
                'X-Restli-Protocol-Version': '2.0.0'
            }
        ).json()

        if ('id' in response and 'localizedLastName' in response
           and 'localizedFirstName' in response):
            linkedin_account_id = 'urn:li:person:' + response['id']

            try:
                image_url = response['profilePicture']['displayImage~']['elements'][0]['identifiers'][0]['identifier']
                linkedin_profile_image = base64.b64encode(requests.get(image_url).content)
            except Exception:
                linkedin_profile_image = ''

            # TODO - STD: add each companies page
            return [{
                'name': response['localizedLastName'] + ' ' + response['localizedFirstName'],
                'linkedin_account_id': linkedin_account_id,
                'linkedin_access_token': linkedin_access_token,
                'image': linkedin_profile_image
            }]

        return []

    def _create_linkedin_accounts(self, access_token, media):
        linkedin_accounts = self._get_linkedin_accounts(access_token)
        social_accounts = self.search([
            ('media_id', '=', media.id),
            ('linkedin_account_id', 'in', [l.get('linkedin_account_id') for l in linkedin_accounts])])

        existing_accounts = {
            account.linkedin_account_id: account
            for account in social_accounts
            if account.linkedin_account_id
        }

        accounts_to_create = []
        for account in linkedin_accounts:
            if account['linkedin_account_id'] in existing_accounts:
                existing_accounts[account['linkedin_account_id']].write({
                    'linkedin_access_token': account.get('linkedin_access_token'),
                    'is_media_disconnected': False,
                    'image': account.get('image')
                })
            else:
                account.update({
                    'media_id': media.id,
                    'is_media_disconnected': False,
                    'has_trends': False,
                    'has_account_stats': False
                })
                accounts_to_create.append(account)

        self.create(accounts_to_create)
