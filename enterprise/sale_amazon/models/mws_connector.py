# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
import dateutil.parser
import logging
from xml.etree import ElementTree

from odoo import exceptions

from odoo.addons.sale_amazon.lib import mws

_logger = logging.getLogger(__name__)

XMLNS = {
    'Feeds': 'http://mws.amazonaws.com/doc/2009-01-01/',
    'Orders': 'https://mws.amazonservices.com/Orders/2013-09-01',
    'Sellers': 'https://mws.amazonservices.com/Sellers/2011-07-01',
}
XSI = 'http://www.w3.org/2001/XMLSchema-instance'
FEED_ENCODING = 'iso-8859-1'


def get_api_connector(
        api_class, access_key, secret_key, seller_key, marketplace_code, error_message, **kwargs):
    """ Safely create and return a connector to the adequate regional MWS API. """
    try:
        return api_class(access_key, secret_key, seller_key, region=marketplace_code, **kwargs)
    except mws.MWSError:
        _raise_mws_error(error_message)


def _generate_feed_base(seller_key, message_type):
    """ Build the generic XML base for a feed to be sent to the MWS API. """
    root = ElementTree.Element(
        'AmazonEnvelope', {'{%s}noNamespaceSchemaLocation' % XSI: 'amzn-envelope.xsd'})
    header = ElementTree.SubElement(root, 'Header')
    ElementTree.SubElement(header, 'DocumentVersion').text = "1.01"
    ElementTree.SubElement(header, 'MerchantIdentifier').text = seller_key
    ElementTree.SubElement(root, 'MessageType').text = message_type
    message = ElementTree.SubElement(root, 'Message')
    ElementTree.SubElement(message, 'MessageID').text = str(int(datetime.utcnow().timestamp()))
    return root, message


def generate_order_cancellation_feed(seller_key, amazon_order_ref):
    """ Build the XML message to be sent as an order cancellation feed. """
    root, message = _generate_feed_base(seller_key, 'OrderAcknowledgement')
    order_acknowledgement = ElementTree.SubElement(message, 'OrderAcknowledgement')
    ElementTree.SubElement(order_acknowledgement, 'AmazonOrderID').text = amazon_order_ref
    ElementTree.SubElement(order_acknowledgement, 'StatusCode').text = 'Failure'
    return ElementTree.tostring(root, encoding=FEED_ENCODING, method='xml')


def generate_order_fulfillment_feed(
        seller_key, amazon_order_ref, items_data, carrier_name=None, tracking_number=None):
    """ Build the XML message to be sent as an order fulfillment feed. """
    root, message = _generate_feed_base(seller_key, "OrderFulfillment")
    order_fulfillment = ElementTree.SubElement(message, 'OrderFulfillment')
    ElementTree.SubElement(order_fulfillment, 'AmazonOrderID').text = amazon_order_ref
    ElementTree.SubElement(order_fulfillment, 'FulfillmentDate').text = datetime.now().isoformat()
    if carrier_name and tracking_number:
        fulfillment_data = ElementTree.SubElement(order_fulfillment, 'FulfillmentData')
        ElementTree.SubElement(fulfillment_data, 'CarrierName').text = carrier_name
        ElementTree.SubElement(fulfillment_data, 'ShipperTrackingNumber').text = tracking_number
    for amazon_item_ref, item_quantity in items_data:
        item = ElementTree.SubElement(order_fulfillment, 'Item')
        ElementTree.SubElement(item, 'AmazonOrderItemCode').text = amazon_item_ref
        ElementTree.SubElement(item, 'Quantity').text = str(int(item_quantity))
    return ElementTree.tostring(root, encoding=FEED_ENCODING, method='xml')


def do_account_credentials_check(sellers_api, error_message):
    """
    Test the seller id of an account together with the API keys and raises if invalid.
    The ListMarketplaceParticipations operation is used to verify the credentials because it
    combines a light response and a decent rate limit, allowing for several checks in a short time.
    """
    _request_response, rate_limit_reached = _send_request(
        sellers_api.list_marketplace_participations, 'Sellers', error_message)
    return rate_limit_reached


def get_available_marketplace_api_refs(sellers_api, error_message):
    """ Return all the API ids of marketplaces that can be reached from a seller account. """
    marketplace_api_refs = []
    
    # Orders are fetched one batch (of up to 100 orders) at a time.
    # If the fetched batch is full, a next_token is generated and can be used
    # to fetch the next batch with the same query params as the previous one.
    has_next, next_token = True, None
    
    rate_limit_reached = False
    while has_next and not rate_limit_reached:
        request_response, rate_limit_reached = _send_request(
            sellers_api.list_marketplace_participations, 'Sellers', error_message,
            next_token=next_token)
        if request_response:
            if not request_response.response.ok:
                _raise_requests_error(error_message, request_response.response)
            elif not rate_limit_reached:
                parsed_data = request_response.parsed
                next_token = get_string_value(parsed_data, 'NextToken')
                has_next = bool(next_token)
                marketplaces_data = get_raw_data(parsed_data, ('ListMarketplaces', 'Marketplace'))
                if marketplaces_data:
                    # Handle hypothetical data format for single-marketplace Amazon regions
                    if isinstance(marketplaces_data, dict):
                        marketplaces_data = [marketplaces_data]
                    marketplace_api_refs += [get_string_value(marketplace_data, 'MarketplaceId')
                                            for marketplace_data in marketplaces_data]
    return marketplace_api_refs, rate_limit_reached


def get_orders_data(orders_api, marketplace_api_refs, updated_after, error_message, next_token=None):
    """ Retrieve a batch of orders from Amazon Seller Central. """
    orders_data, updated_before = [], updated_after
    # The API requires to fetch orders with status PartiallyShipped if Unshipped orders are fetched
    request_response, rate_limit_reached = _send_request(
        orders_api.list_orders, 'Orders', error_message, marketplaceids=marketplace_api_refs,
        lastupdatedafter=updated_after,
        orderstatus=('Unshipped', 'PartiallyShipped', 'Shipped', 'Canceled'), next_token=next_token)
    if request_response:
        if not request_response.response.ok:
            _raise_requests_error(error_message, request_response.response)
        elif not rate_limit_reached:
            parsed_data = request_response.parsed
            updated_before = get_date_value(parsed_data, 'LastUpdatedBefore')
            next_token = get_string_value(parsed_data, 'NextToken')
            orders_parsed_data = get_raw_data(parsed_data, ('Orders', 'Order'))
            if orders_parsed_data and isinstance(orders_parsed_data, dict):  # Single element in response
                orders_data.append(orders_parsed_data)
            elif orders_parsed_data and isinstance(orders_parsed_data, list):  # Multiple elements in response
                orders_data += orders_parsed_data
    return orders_data, updated_before, next_token, rate_limit_reached


def get_items_data(orders_api, amazon_order_ref, error_message, next_token=None):
    """ Retrieve a batch of order items from Amazon Seller Central. """
    items_data = []
    request_response, rate_limit_reached = _send_request(
        orders_api.list_order_items, 'Orders', error_message, amazon_order_id=amazon_order_ref,
        next_token=next_token)
    if request_response:
        if not request_response.response.ok:
            _raise_requests_error(error_message, request_response.response)
        elif not rate_limit_reached:
            parsed_data = request_response.parsed
            next_token = get_string_value(parsed_data, 'NextToken')
            items_parsed_data = get_raw_data(parsed_data, ('OrderItems', 'OrderItem'))
            if isinstance(items_parsed_data, dict):  # Single element in response
                items_data.append(items_parsed_data)
            elif isinstance(items_parsed_data, list):  # Multiple elements in response
                items_data += items_parsed_data
    return items_data, next_token, rate_limit_reached


def submit_feed(feeds_api, xml_feed, feed_type, error_message):
    """ Send an XML feed to MWS API. Return the Amazon-defined id of the feed. """
    request_response, rate_limit_reached = _send_request(
        feeds_api.submit_feed, 'Feeds', error_message, feed=xml_feed, feed_type=feed_type)
    feed_submission_id = None
    if request_response:
        if not request_response.response.ok:
            _raise_requests_error(error_message, request_response.response)
        elif not rate_limit_reached:
            feed_submission_id = get_string_value(
                request_response.parsed, ('FeedSubmissionInfo', 'FeedSubmissionId'))
    return feed_submission_id, rate_limit_reached


def _send_request(api_function, api_section, error_message, **kwargs):
    """
    Send a request to MWS API, return the response and detect if the request is throttled.
    :param api_function: the operation to request from MWS API
    :param api_section: the operation category used to read the error with the right xml namespace
    :param error_message: the message to display if an error is raised
    :param kwargs: the parameters to pass to the operation
    """
    request_response, rate_limit_reached = None, False
    try:
        request_response = api_function(**kwargs)
    except mws.MWSError as error:
        if not _is_sent_by_amazon(error):
            # Don't try to parse response content as an XML because it's not
            _raise_requests_error(error_message, error.response)
        if _is_request_throttled(error, api_section):
            rate_limit_reached = True
        else:
            _raise_mws_error(error_message, error, api_section)
    return request_response, rate_limit_reached


def _is_sent_by_amazon(mws_error):
    """ Return True if the embedded response contains an XML-formatted error message. """
    return 'xml' in mws_error.response.text

def _is_request_throttled(mws_error, api_section):
    """ Return True if the request corresponding to the xml response is throttled. """
    xml_error_code = _get_xml_error_code(mws_error.response.text, XMLNS[api_section])
    return xml_error_code == 'RequestThrottled' or xml_error_code == 'QuotaExceeded'


def _raise_mws_error(message, mws_error=None, api_section=None):
    """ Build an error log from a MWS error response, if any, and raise it. """
    error_log = message
    if mws_error and api_section:
        error_log += " %s: %s" % (
            _get_xml_error_code(mws_error.response.text, XMLNS[api_section]),
            _get_xml_error_message(mws_error.response.text, XMLNS[api_section])
        )
    _logger.exception(error_log)
    raise exceptions.UserError(error_log)


def _raise_requests_error(message, response):
    """ Build an error log from a requests error response and raise it. """
    error_log = message + " HTTP error code: %s Response content: %s" % (
        response.status_code, response.text
    )
    raise exceptions.UserError(error_log)


def _get_xml_error_code(xml, namespace):
    """ Get the error code of the xml response returned by MWS API. """
    return _get_xml_node_content(xml, namespace, ('Error', 'Code'))


def _get_xml_error_message(xml, namespace):
    """ Get the error message of the xml response returned by MWS API. """
    return _get_xml_node_content(xml, namespace, ('Error', 'Message'))


def _get_xml_node_content(xml, namespace, key_path=()):
    """ Navigate through an xml by following the node path and return the text of the last node. """
    current = ElementTree.fromstring(xml)
    for next_key in key_path:
        current = current and current.find('{%s}%s' % (namespace, next_key))
    return current.text if current is not None else ''


def get_string_value(parsed_data, key_path=(), default_value=''):
    """ Return the value of the last key in the path as a string. """
    raw_data = get_raw_data(parsed_data, key_path)
    string_value = raw_data and isinstance(raw_data, dict) and raw_data.get('value')
    return string_value or default_value


def get_integer_value(parsed_data, key_path=(), default_value=0):
    """ Return the value of the last key in the path as an integer. """
    string_value = get_string_value(parsed_data, key_path)
    try:
        if not string_value:
            raise ValueError
        integer_value = int(string_value)
    except ValueError:
        integer_value = default_value
    return integer_value


def get_float_value(parsed_data, key_path=(), default_value=0.):
    """ Return the value of the last key in the path as a float. """
    string_value = get_string_value(parsed_data, key_path)
    try:
        float_value = float(string_value)
    except ValueError:
        float_value = default_value
    return float_value


def get_date_value(parsed_data, key_path=(), default_value=None):
    """ Return the value of the last key in the path as a datetime. """
    string_value = get_string_value(parsed_data, key_path)
    date_value = string_value and dateutil.parser.parse(string_value).replace(tzinfo=None)
    return date_value or default_value


def get_amount_value(parsed_data, key_path=(), default_value=0.):
    """ Return the value of the last key in the path as a monetary amount. """
    if not isinstance(key_path, tuple):
        key_path = (key_path,)
    return get_float_value(parsed_data, key_path + ('Amount',), default_value)


def get_currency_value(parsed_data, key_path=(), default_value=''):
    """ Return the value of the last key in the path as a monetary currency. """
    if not isinstance(key_path, tuple):
        key_path = (key_path,)
    return get_string_value(parsed_data, key_path + ('CurrencyCode',), default_value)


def get_raw_data(parsed_data, key_path=()):
    """ Navigate through an dict by following the key path and return the value of the last key. """
    if not isinstance(key_path, tuple):
        key_path = (key_path,)
    current = parsed_data
    for next_key in key_path:
        current = current and isinstance(current, dict) and current.get(next_key)
    return current
