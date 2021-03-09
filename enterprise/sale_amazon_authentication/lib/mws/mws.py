# Adapted from the python-amazon-mws library published under the UNLICENSE on
# https://github.com/python-amazon-mws/python-amazon-mws

import datetime
import json
import logging
import pprint
import requests
from requests.exceptions import HTTPError, Timeout

from odoo.exceptions import UserError

from odoo.addons.sale_amazon.lib.mws.mws import DataWrapper, DictWrapper, MWS, MWSError, XMLError, \
     remove_empty

_logger = logging.getLogger(__name__)

def make_request_patch(self, extra_data, method="GET", **kwargs):
    """
    Make request to Amazon MWS API with these parameters
    """

    # Remove all keys with an empty value because
    # Amazon's MWS does not allow such a thing.
    extra_data = remove_empty(extra_data)

    # convert all Python date/time objects to isoformat
    for key, value in extra_data.items():
        if isinstance(value, (datetime.datetime, datetime.date)):
            extra_data[key] = value.isoformat()

    params = self.get_params()
    params.update(extra_data)

    headers = {'User-Agent': 'python-amazon-mws/0.8.6 (Language=Python)'}
    headers.update(kwargs.get('extra_headers', {}))

    # =============================================================================================
    # From here, the library is patched to make the request to the Odoo proxy rather than to Amazon
    # =============================================================================================

    # The library will sometimes provide bytes instead of string. Ensure that everything is
    # converted or it won't be JSON-serializable.
    # This should only be the case for the MD5 checksum, which is entirely in ASCII. Converting
    # 'stupidly' to string should be enough for that case.
    for key in headers:
        value = headers[key]
        if isinstance(value, bytes):
            headers[key] = value.decode('utf-8')

    del params['AWSAccessKeyId']  # Use Odoo's credentials to sign requests
    url = self.proxy_url
    payload = {
        'db_uuid': self.db_uuid,
        'db_enterprise_code': self.db_enterprise_code,
        'method': method,
        'marketplace_code': self.marketplace_code,
        'uri': self.uri,
        'data': kwargs.get('body', ''),
        'headers': json.dumps(headers),
        **params,  # Original payload for the request to Amazon, minus the access key
    }
    try:
        _logger.debug('sending data to amazon proxy: %s', pprint.pformat(payload))
        response = requests.post(url, data=payload, timeout=60)  # Send request to Odoo proxy
        response.raise_for_status()
        if 700 <= response.status_code <= 799:
            raise HTTPError(response=response)

        # Amazon does not always replies with UTF-8 encoded responses, and the specified
        # encoding is sometimes wrong. Replace the response encoding by its apparent encoding
        # provided by the chardet library for the text attribute of the response to be correctly
        # decoded. See doc: https://requests.readthedocs.io/en/master/api/#requests.Response.text
        response.encoding = response.apparent_encoding
        data = response.text
        rootkey = kwargs.get('rootkey', extra_data.get("Action") + "Result")
        try:
            parsed_response = DictWrapper(data, rootkey)

        except XMLError:
            parsed_response = DataWrapper(data, response.headers)

    except (HTTPError, Timeout) as e:
        # iap-services can sometimes be a bit busy (>10s is possible)
        # in case of a time-out, we don't have a response to return
        # to the lib, raise an odoo exception directly
        if isinstance(e, Timeout):
            raise UserError(str(e))
        else:
            error = MWSError(str(e.response.text))
            error.response = e.response
            raise error

    # ==============================================================
    # From here, we resume on running the legacy code of the library
    # ==============================================================

    # Store the response object in the parsed_response for quick access
    parsed_response.response = response
    return parsed_response


MWS.make_request = make_request_patch
