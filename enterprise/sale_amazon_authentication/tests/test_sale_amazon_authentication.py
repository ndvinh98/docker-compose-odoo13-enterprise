# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import TransactionCase


class TestAmazonAuthentication(TransactionCase):

    def setUp(self):

        def _get_available_marketplace_api_refs_mock(*_args, **_kwargs):
            """ Return the API ref of all marketplaces without calling MWS API. """
            return self.env['amazon.marketplace'].search([]).mapped('api_ref'), False

        super().setUp()
        with patch(
            'odoo.addons.sale_amazon.models.mws_connector.get_available_marketplace_api_refs',
            new=_get_available_marketplace_api_refs_mock
        ):
            self.account = self.env['amazon.account'].create({
                'name': "TestAccountName",
                **dict.fromkeys(('seller_key', 'auth_token'), ''),
                'base_marketplace_id': 1,
                'company_id': self.env.company.id,
            })

    def test_check_credentials_auth_token_included(self):
        """ Test the credentials check with valid credentials. """

        def _action_check_credentials_mock(*_args, **_kwargs):
            """ Return True if the 'auth_token' key is included in the kwargs. """
            return 'auth_token' in _kwargs

        with patch('odoo.addons.sale_amazon.models.amazon_account.AmazonAccount'
              '.action_check_credentials',
              new=_action_check_credentials_mock):
            self.assertTrue(self.account.action_check_credentials())
