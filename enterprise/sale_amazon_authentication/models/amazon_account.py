# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AmazonAccount(models.Model):
    _inherit = 'amazon.account'

    auth_token = fields.Char(
        string="Authorization Token",
        help="The MWS Authorization Token of the Amazon Seller Central account for Odoo",
        groups="base.group_system")
    # We set a default for the now unused key fields rather than making them not required to avoid
    # the error log at DB init when the ORM tries to set the 'NOT NULL' constraint on those fields.
    access_key = fields.Char(default="Do not use this field")
    secret_key = fields.Char(default="Do not use this field")

    def action_check_credentials(self, **api_keys):
        """ Check the credentials validity. Use that of the account if not included in kwargs. """
        if 'auth_token' not in api_keys:
            result = None
            for account in self:
                api_keys['auth_token'] = account.auth_token
                # The return value of super().action_check_credentials doesn't depend on the account
                # and raises if the credentials check fails. So it's fine to overwrite the result
                # value with each call.
                result = super(AmazonAccount, account).action_check_credentials(**api_keys)
            return result
        return super(AmazonAccount, self).action_check_credentials(**api_keys)

    @api.model
    def _get_api_key_field_names(self):
        """ Return a tuple of field names used to store API keys.

        We force here the authentication flow of 'public applications' which relies on the Seller ID
        and the Authorization Token. As per this override, any check for valid credentials set on
        the Access Key and on the Secret Key is effectively disabled.
        """
        return 'seller_key', 'auth_token'

    @api.model
    def _build_get_api_connector_kwargs(self, **api_keys):
        """ Build the kwargs passed to `mws_connector.get_api_connector`.

        In addition to the Authorization Token which is a valid positional argument of the library's
        `MWS` class constructor, other proxy-related parameters are included in the returned kwargs
        to be removed from it in the `make_request` overwrite and be included in the request to the
        Odoo proxy.
        """
        IrConfigParam_sudo = self.env['ir.config_parameter'].sudo()
        return {
            'proxy_url': IrConfigParam_sudo.get_param('sale_amazon_authentication.proxy_url'),
            'db_uuid': IrConfigParam_sudo.get_param('database.uuid'),
            'db_enterprise_code': IrConfigParam_sudo.get_param('database.enterprise_code'),
            'auth_token': api_keys.get('auth_token'),
        }
