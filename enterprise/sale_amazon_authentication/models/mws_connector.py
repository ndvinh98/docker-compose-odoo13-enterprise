# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from requests.exceptions import Timeout

from odoo import _, exceptions

from odoo.addons.sale_amazon.models import mws_connector

_logger = logging.getLogger(__name__)
_get_api_connector_base = mws_connector.get_api_connector
_get_items_data_base = mws_connector.get_items_data
_is_sent_by_amazon_base = mws_connector._is_sent_by_amazon


def _get_api_connector_patch(
        _api_class, _access_key, _secret_key, _seller_key, marketplace_code, _error_message,
        **kwargs
):
    """ Get the API object by running legacy code, then set proxy-related object attributes. """

    # Backup and pop the keys related to the proxy from the legacy 'get_api_connector' kwargs
    proxy_url = kwargs.pop('proxy_url', None)
    db_uuid = kwargs.pop('db_uuid', None)
    db_enterprise_code = kwargs.pop('db_enterprise_code', None)

    # Fallback on the legacy function to retrieve the library's MWS object
    api_object = _get_api_connector_base(
        _api_class, _access_key, _secret_key, _seller_key, marketplace_code, _error_message,
        **kwargs
    )

    # Set useful proxy-related values as object attributes to retrieve them in `make_request_patch`
    api_object.proxy_url = proxy_url
    api_object.db_uuid = db_uuid
    api_object.db_enterprise_code = db_enterprise_code
    api_object.marketplace_code = marketplace_code

    return api_object

def _get_items_data_patch(*_args, **_kwargs):
    """ Stop the synchronization loop if a Timeout error occurred when contacting the proxy.

    If the synchronization cannot be done for a given order because of a timeout on the proxy, we
    don't want to let the default behavior of failed synchronizations to happen (i.e. skipping the
    order). Instead the whole synchronization loop should be stopped until the next cron run.
    """
    try:
        return _get_items_data_base(*_args, **_kwargs)
    except Timeout:  # The proxy timed-out
        # Fake a rate limit reached error as it is also transient and this kind of error puts a stop
        # to the synchronization loop
        rate_limit_reached = True
        return [], None, rate_limit_reached

def _is_sent_by_amazon_patch(mws_error):
    """ Raise an UserError is the error originates from the Odoo proxy. Else, run legacy code. """
    if 700 <= mws_error.response.status_code <= 799:  # Custom Odoo proxy error
        _logger.exception(
            f"proxy responded with status code {mws_error.response.status_code} to: {mws_error}"
        )
        if mws_error.response.status_code == 730:  # Forbidden
            raise exceptions.UserError(
                _("You don't have an active subscription. Please buy one here: %s") %
                'https://www.odoo.com/buy'
            )
        elif mws_error.response.status_code == 740:  # Bad Request
            raise exceptions.UserError(_("The Odoo proxy received a malformed request."))
        elif mws_error.response.status_code == 750:  # Internal Error
            raise exceptions.UserError(_("The Odoo proxy encountered an internal server error."))
        else:  # This is unexpected, we should probably have a custom message for this code
            raise exceptions.UserError(_("The Odoo proxy encountered an unhandled error."))
    else:  # Delegate to legacy function
        return _is_sent_by_amazon_base(mws_error)


mws_connector.get_api_connector = _get_api_connector_patch
mws_connector.get_items_data = _get_items_data_patch
mws_connector._is_sent_by_amazon = _is_sent_by_amazon_patch
