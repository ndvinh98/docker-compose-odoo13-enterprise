# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
import requests
from werkzeug.urls import url_join

from odoo import _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round, float_is_zero

API_BASE_URL = 'https://api.easypost.com/v2/'


class EasypostRequest():
    "Implementation of Easypost API"

    def __init__(self, api_key, debug_logger):
        self.api_key = api_key
        self.debug_logger = debug_logger

    def _make_api_request(self, endpoint, request_type='get', data=None):
        """make an api call, return response"""
        access_url = url_join(API_BASE_URL, endpoint)
        try:
            self.debug_logger("%s\n%s\n%s" % (access_url, request_type, data if data else None), 'easypost_request_%s' % endpoint)
            if request_type == 'get':
                response = requests.get(access_url, auth=(self.api_key, ''), data=data)
            else:
                response = requests.post(access_url, auth=(self.api_key, ''), data=data)
            self.debug_logger("%s\n%s" % (response.status_code, response.text), 'easypost_response_%s' % endpoint)
            response = response.json()
            # check for any error in response
            if 'error' in response:
                raise UserError(_('Easypost returned an error: ') + response['error'].get('message'))
            return response
        except Exception as e:
            raise e

    def fetch_easypost_carrier(self):
        """ Import all carrier account from easypost
        https://www.easypost.com/docs/api.html#carrier-accounts
        It returns a dict with carrier account name and it's
        easypost id in order to generate shipments.
        e.g: {'FeDex: ca_27839172aee03918a701'}
        """
        carriers = self._make_api_request('carrier_accounts')
        carriers = {c['readable']: c['id'] for c in carriers}
        if carriers:
            return carriers
        else:
            # The user need at least one carrier on its easypost account.
            # https://www.easypost.com/account/carriers
            raise UserError(_("You have no carrier linked to your Easypost Account.\
                Please connect to Easypost, link your account to carriers and then retry."))

    def _check_required_value(self, carrier, recipient, shipper, order=False, picking=False):
        """ Check if the required value are present in order
        to process an API call.
        return True or an error if a value is missing.
        """
        # check carrier credentials
        if carrier.prod_environment and not carrier.sudo().easypost_production_api_key:
            raise UserError(_("The %s carrier is missing (Missing field(s) :\n Production API Key)") % carrier.name)
        elif not carrier.sudo().easypost_test_api_key:
            raise UserError(_("The %s carrier is missing (Missing field(s) :\n Test API Key)") % carrier.name)

        if not carrier.easypost_delivery_type:
            raise UserError(_("The %s carrier is missing (Missing field(s) :\n Delivery Carrier Type)") % carrier.name)

        if not carrier.easypost_default_packaging_id:
            raise UserError(_("The %s carrier is missing (Missing field(s) :\n Default Product Packaging)") % carrier.name)

        if not order and not picking:
            raise UserError(_("Sale Order/Stock Picking is missing."))

        # check required value for order
        if order:
            if not order.order_line:
                raise UserError(_("Please provide at least one item to ship."))
            for line in order.order_line.filtered(lambda line: not line.product_id.weight and not line.is_delivery and line.product_id.type not in ['service', 'digital'] and not line.display_type):
                raise UserError(_('The estimated price cannot be computed because the weight of your product is missing.'))

        # check required value for picking
        if picking:
            if not picking.move_lines:
                raise UserError(_("Please provide at least one item to ship."))
            if picking.move_lines.filtered(lambda line: not line.weight):
                raise UserError(_('The estimated price cannot be computed because the weight of your product is missing.'))
        return True

    def _prepare_address(self, addr_type, addr_obj):
        """ Create a dictionary with list of available
        value to easypost.
        param string: addr_type: 'from_address' for shipper
        or 'to_address' for recipient.
        param addr_obj res.partner: partner linked to order/picking
        in order to retrieve shipping information
        return str: response address id of API request to create an address.
        We do an extra API request since the address creation is free of charge.
        If there is an error about address it will be raise before the rate
        or shipment request.
        """
        addr_fields = {
            'street1': 'street', 'street2': 'street2',
            'city': 'city', 'zip': 'zip', 'phone': 'phone',
            'email': 'email'}
        address = {'order[%s][%s]' % (addr_type, field_name): addr_obj[addr_obj_field]
                   for field_name, addr_obj_field in addr_fields.items()
                   if addr_obj[addr_obj_field]}
        address['order[%s][name]' % addr_type] = addr_obj.name or addr_obj.display_name
        if addr_obj.state_id:
            address['order[%s][state]' % addr_type] = addr_obj.state_id.name
        address['order[%s][country]' % addr_type] = addr_obj.country_id.code
        if addr_obj.commercial_company_name:
            address['order[%s][company]' % addr_type] = addr_obj.commercial_company_name
        return address

    def _prepare_order_shipments(self, carrier, order):
        """ Method used in order to estimate delivery
        cost for a quotation. It estimates the price with
        the default package defined on the carrier.
        e.g: if the default package on carrier is a 10kg Fedex
        box and the customer ships 35kg it will create a shipment
        with 4 packages (3 with 10kg and the last with 5 kg.).
        It ignores reality with dimension or the fact that items
        can not be cut in multiple pieces in order to allocate them
        in different packages. It also ignores customs info.
        """
        # Max weight for carrier default package
        max_weight = carrier._easypost_convert_weight(carrier.easypost_default_packaging_id.max_weight)
        # Order weight
        total_weight = carrier._easypost_convert_weight(sum([(line.product_id.weight * line.product_uom_qty) for line in order.order_line if not line.display_type]))

        # Create shipments
        shipments = {}
        if max_weight and total_weight > max_weight:
            # Integer division for packages with maximal weight.
            total_shipment = int(total_weight // max_weight)
            # Remainder for last package.
            last_shipment_weight = float_round(total_weight % max_weight, precision_digits=1)
            for shp_id in range(0, total_shipment):
                shipments.update(self._prepare_parcel(shp_id, carrier.easypost_default_packaging_id, max_weight, carrier.easypost_label_file_type))
                shipments.update(self._options(shp_id, carrier))
            if not float_is_zero(last_shipment_weight, precision_digits=1):
                shipments.update(self._prepare_parcel(total_shipment, carrier.easypost_default_packaging_id, last_shipment_weight, carrier.easypost_label_file_type))
                shipments.update(self._options(total_shipment, carrier))
        else:
            shipments.update(self._prepare_parcel(0, carrier.easypost_default_packaging_id, total_weight, carrier.easypost_label_file_type))
            shipments.update(self._options(0, carrier))
        return shipments

    def _prepare_picking_shipments(self, carrier, picking, is_return=False):
        """ Prepare easypost order's shipments with the real
        value used in the picking. It will put everything in
        a single package if no packages are used in the picking.
        It will iterates over multiple packages if they are used.
        It returns a dict with the necessary shipments (containing
        parcel/customs info used for each stock.move.line result package.
        Move lines without package are considered to be lock together
        in a single package.
        """
        shipment = {}
        shipment_id = 0
        move_lines_with_package = picking.move_line_ids.filtered(lambda ml: ml.result_package_id)
        move_lines_without_package = picking.move_line_ids - move_lines_with_package
        if move_lines_without_package:
            # If the user didn't use a specific package we consider
            # that he put everything inside a single package.
            # The user still able to reorganise its packages if a
            # mistake happens.
            if picking.is_return_picking:
                weight = sum([ml.product_id.weight * ml.product_uom_id._compute_quantity(ml.product_qty, ml.product_id.uom_id, rounding_method='HALF-UP') for ml in move_lines_without_package])
            else:
                weight = sum([ml.product_id.weight * ml.product_uom_id._compute_quantity(ml.qty_done, ml.product_id.uom_id, rounding_method='HALF-UP') for ml in move_lines_without_package])
            weight = carrier._easypost_convert_weight(weight)
            shipment.update(self._prepare_parcel(0, carrier.easypost_default_packaging_id, weight, carrier.easypost_label_file_type))
            # Add customs info for this package.
            shipment.update(self._customs_info(0, move_lines_without_package.filtered(lambda ml: ml.product_id.type in ['product', 'consu'])))
            shipment.update(self._options(0, carrier))
            shipment_id += 1
        if move_lines_with_package:
            # Generate an easypost shipment for each package in picking.
            for package in picking.package_ids:
                # compute move line weight in package
                move_lines = picking.move_line_ids.filtered(lambda ml: ml.result_package_id == package)
                if picking.is_return_picking:
                    weight = sum([ml.product_id.weight * ml.product_uom_id._compute_quantity(ml.product_qty, ml.product_id.uom_id, rounding_method='HALF-UP') for ml in move_lines])
                else:
                    weight = package.shipping_weight
                weight = carrier._easypost_convert_weight(weight)
                # Prepare an easypost parcel with same info than package.
                shipment.update(self._prepare_parcel(shipment_id, package.packaging_id, weight=weight, label_format=carrier.easypost_label_file_type))
                # Add customs info for current shipment.
                shipment.update(self._customs_info(shipment_id, move_lines))
                shipment.update(self._options(shipment_id, carrier))
                shipment_id += 1
        if is_return:
            shipment.update({'order[is_return]': True})
        return shipment

    def _prepare_parcel(self, shipment_id, package, weight=False, label_format='pdf'):
        """ Prepare parcel for used package. (carrier default if it comes from
        an order). https://www.easypost.com/docs/api.html#parcels
        params:
        - Shipment_id int: The current easypost shipement.
        - Package 'product.packaging': Used package for shipement
        - Weight float(oz): Product's weight contained in package
        - label_format str: Format for label to print.
        return dict: a dict with necessary keys in order to create
        a easypost parcel for the easypost shipement with shipment_id
        """
        shipment = {
            'order[shipments][%d][parcel][weight]' % shipment_id: weight,
            'order[shipments][%d][options][label_format]' % shipment_id: label_format,
            'order[shipments][%d][options][label_date]' % shipment_id: datetime.datetime.now().isoformat()
        }
        if package.package_carrier_type == 'easypost':
            if package.shipper_package_code:
                shipment.update({
                    'order[shipments][%d][parcel][predefined_package]' % shipment_id: package.shipper_package_code
                })
            if not package.shipper_package_code or (package.length > 0 and package.width > 0 and package.height > 0):
                shipment.update({
                    'order[shipments][%d][parcel][length]' % shipment_id: package.length,
                    'order[shipments][%d][parcel][width]' % shipment_id: package.width,
                    'order[shipments][%d][parcel][height]' % shipment_id: package.height
                })
        else:
            raise UserError(_('Product packaging used in pack %s is not configured for easypost.') % package.display_name)
        return shipment

    def _customs_info(self, shipment_id, lines):
        """ generate a dict with customs info for each package.
        https://www.easypost.com/customs-guide.html
        Currently general customs info for all packages are not generate.
        For each shipment add a customs items by move line containing
        - Product description (care it crash if bracket are used)
        - Quantity for this product in the current package
        - Product price
        - Product price currency
        - Total weight in ounces.
        - Original country code(warehouse)
        """
        customs_info = {}
        customs_item_id = 0
        for line in lines:
            # skip service
            if line.product_id.type not in ['product', 'consu']:
                continue
            if line.picking_id.is_return_picking:
                unit_quantity = line.product_uom_id._compute_quantity(line.product_qty, line.product_id.uom_id, rounding_method='HALF-UP')
            else:
                unit_quantity = line.product_uom_id._compute_quantity(line.qty_done, line.product_id.uom_id, rounding_method='HALF-UP')
            hs_code = line.product_id.hs_code or ''
            price_unit = line.move_id.sale_line_id.price_reduce_taxinc if line.move_id.sale_line_id else line.product_id.list_price
            customs_info.update({
                'order[shipments][%d][customs_info][customs_items][%d][description]' % (shipment_id, customs_item_id): line.product_id.name,
                'order[shipments][%d][customs_info][customs_items][%d][quantity]' % (shipment_id, customs_item_id): unit_quantity,
                'order[shipments][%d][customs_info][customs_items][%d][value]' % (shipment_id, customs_item_id): unit_quantity * price_unit,
                'order[shipments][%d][customs_info][customs_items][%d][currency]' % (shipment_id, customs_item_id): line.picking_id.company_id.currency_id.name,
                'order[shipments][%d][customs_info][customs_items][%d][weight]' % (shipment_id, customs_item_id): line.env['delivery.carrier']._easypost_convert_weight(line.product_id.weight * unit_quantity),
                'order[shipments][%d][customs_info][customs_items][%d][origin_country]' % (shipment_id, customs_item_id): line.picking_id.picking_type_id.warehouse_id.partner_id.country_id.code,
                'order[shipments][%d][customs_info][customs_items][%d][hs_tariff_number]' % (shipment_id, customs_item_id): hs_code,
            })
            customs_item_id += 1
        return customs_info

    def _options(self, shipment_id, carrier):
        options = {}
        if carrier.easypost_default_service_id:
            service_otpions = carrier.easypost_default_service_id._get_service_specific_options()
            for option_name, option_value in service_otpions.items():
                options['order[shipments][%d][options][%s]' % (shipment_id, option_name)] = option_value
        return options

    def rate_request(self, carrier, recipient, shipper, order=False, picking=False, is_return=False):
        """ Create an easypost order in order to proccess
        all package at once.
        https://www.easypost.com/docs/api.html#orders
        It will process in this order:
        - recipient address (check _prepare_address for more info)
        - shipper address (check _prepare_address for more info)
        - prepare shipments (with parcel/customs info)
            - check _prepare_picking_shipments for more info in picking case
            - check _prepare_order_shipments for more info in SO case
        - Do the API request
        If a service level is defined on the delivery carrier it will
        returns the rate for this service or an error if there is no
        rate for this service.
        If there is no service level on the delivery carrier, it will
        return the cheapest rate. this behavior could be override with
        the method _sort_rates.
        return
        - an error if rates couldn't be found.
        - API response with potential warning messages.
        """
        self._check_required_value(carrier, recipient, shipper, order=order, picking=picking)

        # Dict that will contains data in
        # order to create an easypost object
        order_payload = {}

        # reference field to track Odoo customers that use easypost for postage/shipping.
        order_payload['order[reference]'] = 'odoo'

        # Add current carrier type
        order_payload['order[carrier_accounts][id]'] = carrier.easypost_delivery_type_id

        # Add addresses (recipient and shipper)
        order_payload.update(self._prepare_address('to_address', recipient))
        order_payload.update(self._prepare_address('from_address', shipper))
        if carrier.easypost_default_service_id._require_residential_address():
            order_payload['order[to_address][residential]'] = True

        # if picking then count total_weight of picking move lines, else count on order
        # easypost always takes weight in ounces(oz)
        if picking:
            order_payload.update(self._prepare_picking_shipments(carrier, picking, is_return=is_return))
        else:
            order_payload.update(self._prepare_order_shipments(carrier, order))

        # request for rate
        response = self._make_api_request("orders", "post", data=order_payload)
        error_message = False
        warning_message = False
        rate = False

        # explicitly check response for any messages
        # error message are catch during _make_api_request method
        if response.get('messages'):
            warning_message = ('\n'.join([x['carrier'] + ': ' + x['type'] + ' -- ' + x['message'] for x in response['messages']]))
            response.update({'warning_message': warning_message})

        # check response contains rate for particular service
        rates = response.get('rates')
        # When easypost returns a JSON without rates in probably
        # means that some data are missing or inconsistent.
        # However instead of returning a correct error message,
        # it will return an empty JSON or a message asking to contact
        # their support. In this case a good practice would be to check
        # the order_payload sent and try to find missing or erroneous value.
        # DON'T FORGET DEBUG MODE ON DELIVERY CARRIER.
        if not rates:
            error_message = _("It seems Easypost do not provide shipments for this order.\
                We advise you to try with another package type or service level.")
        elif rates and not carrier.easypost_default_service_id:
            # Get cheapest rate.
            rate = self._sort_rates(rates)[0]
            # Complete service level on the delivery carrier.
            carrier._generate_services(rates)
        # If the user ask for a specific service level on its carrier.
        elif rates and carrier.easypost_default_service_id:
            rate = [rate for rate in rates if rate['service'] == carrier.easypost_default_service_id.name]
            if not rate:
                error_message = _("There is no rate available for the selected service level for one of your package. Please choose another service level.")
            else:
                rate = rate[0]

        # warning_message could contains useful information
        # in order to correct the delivery carrier or SO/picking.
        if error_message and warning_message:
            error_message += warning_message

        response.update({
            'error_message': error_message,
            'rate': rate,
        })

        return response

    def send_shipping(self, carrier, recipient, shipper, picking, is_return=False):
        """ In order to ship an easypost order:
        - prepare an order by asking a rate request with correct parcel
        and customs info.
        https://www.easypost.com/docs/api.html#create-an-order
        - then buy the order with selected provider and service level.
        https://www.easypost.com/docs/api.html#buy-an-order
        - collect label and tracking data from the order buy request's
        response.
        return a dict with:
        - order data
        - selected rate
        - tracking label
        - tracking URL
        """
        # create an order
        result = self.rate_request(carrier, recipient, shipper, picking=picking, is_return=is_return)
        # check for error in result
        if result.get('error_message'):
            return result

        # buy an order
        buy_order_payload = {}
        buy_order_payload['carrier'] = result['rate']['carrier']
        buy_order_payload['service'] = result['rate']['service']
        endpoint = "orders/%s/buy" % result['id']
        response = self._make_api_request(endpoint, 'post', data=buy_order_payload)
        response = self._post_process_ship_response(response, carrier=carrier, picking=picking)
        # explicitly check response for any messages
        if response.get('messages'):
            raise UserError('\n'.join([x['carrier'] + ': ' + x['type'] + ' -- ' + x['message'] for x in response['messages']]))

        # get tracking code and lable file url
        result['track_shipments_url'] = {res['tracking_code']: res['tracker']['public_url'] for res in response['shipments']}
        result['track_label_data'] = {res['tracking_code']: res['postage_label']['label_url'] for res in response['shipments']}
        return result

    def get_tracking_link(self, order_id):
        """ Retrieve the information on the order with id 'order_id'.
        https://www.easypost.com/docs/api.html#retrieve-an-order
        Return data relative to tracker.
        """
        tracking_public_urls = []
        endpoint = "orders/%s" % order_id
        response = self._make_api_request(endpoint)
        for shipment in response.get('shipments'):
            tracking_public_urls.append([shipment['tracking_code'], shipment['tracker']['public_url']])
        return tracking_public_urls

    def _sort_rates(self, rates):
        """ Sort rates by price. This function
        can be override in order to modify the default
        rate behavior.
        """
        return sorted(rates, key=lambda rate: rate.get('rate'))

    def _post_process_ship_response(self, response, carrier=False, picking=False):
        """ Easypost manage different carriers however they don't follow a
        standard flow and some carriers could act a specific way compare to
        other. The purpose of this method is to catch problematic behavior and
        modify the returned response in order to make it standard compare to
        other carrier.
        """
        # An order for UPS will generate a rate for first shipment with the
        # rate for all shipments but compare to other carriers, it will return
        # messages for following shipments explaining that their rates is in the
        # first shipment (other carrier just return an empty list).
        if response.get('messages') and\
                carrier.easypost_delivery_type == 'UPS' and\
                len(response.get('shipments', [])) > 1:
            if len(response.get('shipments')[0].get('rates', [])) > 0 and all(s.get('messages') for s in response['shipments'][1:]):
                if picking:
                    picking.message_post(body=response.get('messages'))
                response['messages'] = False
        return response
