# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
from binascii import a2b_base64
import io
import logging
import re
import requests
from lxml import html
from PyPDF2 import PdfFileWriter, PdfFileReader
from xml.etree import ElementTree as etree
from werkzeug.urls import url_join

from odoo import _
from odoo.exceptions import UserError
from odoo.tools import float_round

_logger = logging.getLogger(__name__)


COUNTRIES_WITHOUT_POSTCODES = [
    'AO', 'AG', 'AW', 'BS', 'BZ', 'BJ', 'BW', 'BF', 'BI', 'CM', 'CF', 'KM',
    'CG', 'CD', 'CK', 'CI', 'DJ', 'DM', 'GQ', 'ER', 'FJ', 'TF', 'GM', 'GH',
    'GD', 'GN', 'GY', 'HK', 'IE', 'JM', 'KE', 'KI', 'MO', 'MW', 'ML', 'MR',
    'MU', 'MS', 'NR', 'AN', 'NU', 'KP', 'PA', 'QA', 'RW', 'KN', 'LC', 'ST',
    'SC', 'SL', 'SB', 'SO', 'ZA', 'SR', 'SY', 'TZ', 'TL', 'TK', 'TO', 'TT',
    'TV', 'UG', 'AE', 'VU', 'YE', 'ZW'
]

def _grams(kilograms):
    return int(kilograms * 1000)


class BpostRequest():

    def __init__(self, prod_environment, debug_logger):
        self.debug_logger = debug_logger
        if prod_environment:
            self.base_url = 'https://api-parcel.bpost.be/services/shm/'
        else:
            self.base_url = 'https://api-parcel.bpost.be/services/shm/'

    def check_required_value(self, recipient, delivery_nature, shipper, order=False, picking=False):
        recipient_required_fields = ['city', 'country_id']
        if recipient.country_id.code not in COUNTRIES_WITHOUT_POSTCODES:
            recipient_required_fields.append('zip')
        if not recipient.street and not recipient.street2:
            recipient_required_fields.append('street')
        shipper_required_fields = ['city', 'zip', 'country_id']
        if not shipper.street and not shipper.street2:
            shipper_required_fields.append('street')

        res = [field for field in recipient_required_fields if not recipient[field]]
        if res:
            return _("The recipient address is incomplete or wrong (Missing field(s):  \n %s)") % ", ".join(res).replace("_id", "")
        if recipient.country_id.code == "BE" and delivery_nature == 'International':
            return _("bpost International is used only to ship outside Belgium. Please change the delivery method into bpost Domestic.")
        if recipient.country_id.code != "BE" and delivery_nature == 'Domestic':
            return _("bpost Domestic is used only to ship inside Belgium. Please change the delivery method into bpost International.")

        res = [field for field in shipper_required_fields if not shipper[field]]
        if res:
            return _("The address of your company/warehouse is incomplete or wrong (Missing field(s):  \n %s)") % ", ".join(res).replace("_id", "")
        if shipper.country_id.code != 'BE':
            return _("Your company/warehouse address must be in Belgium to ship with bpost")

        if order:
            if order.order_line and all(order.order_line.mapped(lambda l: l.product_id.type in ['service', 'digital'])):
                return _("The estimated shipping price cannot be computed because all your products are service/digital.")
            if not order.order_line:
                return _("Please provide at least one item to ship.")
            if order.order_line.filtered(lambda line: not line.product_id.weight and not line.is_delivery and line.product_id.type not in ['service', 'digital'] and not line.display_type):
                return _('The estimated shipping cannot be computed because the weight of your product is missing.')
        return False

    def _parse_address(self, partner):
        if partner.street and partner.street2:
            street = '%s %s' % (partner.street, partner.street2)
        else:
            street = partner.street or partner.street2
        match = re.match(r'^(.*?)(\S*\d+\S*)?\s*$', street)
        street = match.group(1)
        street_number = match.group(2)  # None if no number found
        if street_number and len(street_number) > 8:
            street = match.group(0)
            street_number = None
        return (street, street_number)

    def rate(self, order, carrier):
        weight = sum([(line.product_id.weight * line.product_qty) for line in order.order_line if not line.display_type]) or 0.0
        weight_in_kg = carrier._bpost_convert_weight(weight)
        return self._get_rate(carrier, weight_in_kg, order.partner_shipping_id.country_id)

    def _get_rate(self, carrier, weight, country):
        '''@param carrier: a record of the delivery.carrier
           @param weight: in kilograms
           @param country: a record of the destination res.country'''

        # Surprisingly, bpost does not require to send other data while asking for prices;
        # they simply return a price grid for all activated products for this account.
        code, response = self._send_request('rate', None, carrier)
        if code == 401 and response:
            # If the authentication fails, the server returns plain HTML instead of XML
            error_page = html.fromstring(response)
            error_message = error_page.body.text_content()
            raise UserError(_("Authentication error -- wrong credentials\n(Detailed error: %s)") % error_message)
        else:
            xml_response = etree.fromstring(response)

        # Find price by product and country
        price = 0.0
        ns = {'ns1': 'http://schema.post.be/shm/deepintegration/v3/'}
        bpost_delivery_type = carrier.bpost_domestic_deliver_type if carrier.bpost_delivery_nature == 'Domestic' else carrier.bpost_international_deliver_type
        for delivery_method in xml_response.findall('ns1:deliveryMethod/[@name="home or office"]/ns1:product/[@name="%s"]/ns1:price' % bpost_delivery_type, ns):
            if delivery_method.attrib['countryIso2Code'] == country.code:
                price = float(self._get_price_by_weight(_grams(weight), delivery_method))/100
                sale_price_digits = carrier.env['decimal.precision'].precision_get('Product Price')
                price = float_round(price, precision_digits=sale_price_digits)
        if not price:
            raise UserError(_("bpost did not return prices for this destination country."))

        # If delivery on saturday is enabled, there are additional fees
        additional_fees = 0.0
        if carrier.bpost_saturday is True:
            for option_price in xml_response.findall('ns1:deliveryMethod/[@name="home or office"]/ns1:product/[@name="%s"]/ns1:option/[@name="Saturday"]' % bpost_delivery_type, ns):
                additional_fees = float(option_price.attrib['price'])

        return price + additional_fees

    def _get_price_by_weight(self, weight, price):
        if weight <= 2000:
            return price.attrib['priceLessThan2']
        elif weight <= 5000:
            return price.attrib['price2To5']
        elif weight <= 10000:
            return price.attrib['price5To10']
        elif weight <= 20000:
            return price.attrib['price10To20']
        elif weight <= 30000:
            return price.attrib['price20To30']
        else:
            raise UserError(_("Packages over 30 Kg are not accepted by bpost."))

    def send_shipping(self, picking, carrier, with_return_label, is_return_label=False):
        # Get price of label
        if is_return_label:
            shipping_weight_in_kg = 0.0
            for move in picking.move_lines:
                shipping_weight_in_kg += move.product_qty * move.product_id.weight
        else:
            shipping_weight_in_kg = carrier._bpost_convert_weight(picking.shipping_weight)
        price = self._get_rate(carrier, shipping_weight_in_kg, picking.partner_id.country_id)

        # Announce shipment to bpost
        reference_id = str(picking.name.replace("/", "", 2))[:50]
        sender_partner_id = picking.picking_type_id.warehouse_id.partner_id
        ss, sn = self._parse_address(sender_partner_id)
        rs, rn = self._parse_address(picking.partner_id)
        if carrier.bpost_shipment_type in ('SAMPLE', 'GIFT', 'DOCUMENTS'):
            shipping_value = 100
        else:
            shipping_value = 0
            for line in picking.move_line_ids :
                price_unit = line.move_id.sale_line_id.price_reduce_taxinc or line.product_id.list_price
                shipping_value += price_unit * line.qty_done
            shipping_value = max(min(int(shipping_value*100), 2500000), 100) # according to bpost, 100 <= parcelValue <= 2500000

        # bpsot only allow a zip with a size of 8 characters. In some country
        # (e.g. brazil) the postalCode could be longer than 8. In this case we
        # set the zip in the locality.
        receiver_postal_code = picking.partner_id.zip
        receiver_locality = picking.partner_id.city

        # Some country do not use zip code (Saudi Arabia, Congo, ...). Bpost
        # always require at least a zip or a PO box.
        if not receiver_postal_code:
            receiver_postal_code = '/'
        elif len(receiver_postal_code) > 8:
            receiver_locality = '%s %s' % (receiver_locality, receiver_postal_code)
            receiver_postal_code = '/'

        if picking.partner_id.state_id:
            receiver_locality = '%s, %s' % (receiver_locality, picking.partner_id.state_id.display_name)


        values = {'accountId': carrier.sudo().bpost_account_number,
                  'reference': reference_id,
                  'sender': {'_record': sender_partner_id,
                             'streetName': ss,
                             'number': sn,
                             },
                  'receiver': {'_record': picking.partner_id,
                               'company': picking.partner_id.commercial_partner_id.name if picking.partner_id.commercial_partner_id != picking.partner_id else '',
                               'streetName': rs,
                               'number': rn,
                               'locality': receiver_locality,
                               'postalCode': receiver_postal_code,
                               },
                  'is_domestic': carrier.bpost_delivery_nature == 'Domestic',
                  'weight': str(_grams(shipping_weight_in_kg)),
                  # domestic
                  'product': 'bpack Easy Retour' if is_return_label else carrier.bpost_domestic_deliver_type,
                  'saturday': carrier.bpost_saturday,
                  # international
                  'international_product': carrier.bpost_international_deliver_type,
                  'parcelValue': shipping_value,
                  'contentDescription': ' '.join([
                     "%d %s" % (line.qty_done, re.sub('[\W_]+', '', line.product_id.name or '')) for line in picking.move_line_ids
                  ])[:50],
                  'shipmentType': carrier.bpost_shipment_type,
                  'parcelReturnInstructions': carrier.bpost_parcel_return_instructions,
                  }
        if is_return_label:
            tmp = values['sender']
            values['sender'] = values['receiver']
            values['receiver'] = tmp
            values['receiver']['company'] = picking.company_id.name
        xml = carrier.env['ir.qweb'].render('delivery_bpost.bpost_shipping_request', values)
        code, response = self._send_request('send', xml, carrier)
        if code != 201 and response:
            try:
                root = etree.fromstring(response)
                ns = {'ns1': 'http://schema.post.be/shm/deepintegration/v3/'}
                for errors_return in root.findall("ns1:error", ns):
                    raise UserError(errors_return.text)
            except etree.ParseError:
                    raise UserError(response)

        # Grab printable label and tracking code
        code, response2 = self._send_request('label', None, carrier, reference=reference_id, with_return_label=with_return_label)
        root = etree.fromstring(response2)
        ns = {'ns1': 'http://schema.post.be/shm/deepintegration/v3/'}
        for labels in root.findall('ns1:label', ns):
            if with_return_label:
                main_label, return_label = self._split_labels(labels, ns)
            else:
                main_label = {
                    'tracking_code': labels.find("ns1:barcode", ns).text,
                    'label': a2b_base64(labels.find("ns1:bytes", ns).text)
                }
                return_label = False
        return {
            'price': price,
            'main_label': main_label,
            'return_label': return_label
        }

    def _split_labels(self, labels, ns):

        def _get_page(src_pdf, num):
            with io.BytesIO(base64.b64decode(src_pdf)) as stream:
                try:
                    pdf = PdfFileReader(stream)
                    writer = PdfFileWriter()
                    writer.addPage(pdf.getPage(num))
                    stream2 = io.BytesIO()
                    writer.write(stream2)
                    return a2b_base64(base64.b64encode(stream2.getvalue()))
                except Exception:
                    _logger.error('Error ')
                    return False

        barcodes = labels.findall("ns1:barcode", ns)
        src_pdf = labels.find("ns1:bytes", ns).text
        main_barcode = {
            'tracking_code': barcodes[0].text,
            'label': _get_page(src_pdf, 0)
        }

        return_barcode = False
        if len(barcodes) > 1:
            return_barcode = {
                'tracking_code': barcodes[1].text,
                'label': _get_page(src_pdf, 1)
            }

        return (main_barcode, return_barcode)

    def _send_request(self, action, xml, carrier, reference=None, with_return_label=False):
        supercarrier = carrier.sudo()
        passphrase = supercarrier._bpost_passphrase()
        METHODS = {'rate': 'GET',
                   'send': 'POST',
                   'label': 'GET'}
        HEADERS = {'rate': {'authorization': 'Basic %s' % passphrase,
                            'accept': 'application/vnd.bpost.shm-productConfiguration-v3.1+XML'},
                   'send': {'authorization': 'Basic %s' % passphrase,
                            'content-Type': 'application/vnd.bpost.shm-order-v3.3+XML'},
                   'label': {'authorization': 'Basic %s' % passphrase,
                             'accept': 'application/vnd.bpost.shm-label-%s-v3+XML' % ('pdf' if carrier.bpost_label_format == 'PDF' else 'image'),
                             'content-Type': 'application/vnd.bpost.shm-labelRequest-v3+XML'}}
        label_url = url_join(self.base_url, '%s/orders/%s/labels/%s' % (supercarrier.bpost_account_number, reference, carrier.bpost_label_stock_type))
        if with_return_label:
            label_url += '/withReturnLabels'
        URLS = {'rate': url_join(self.base_url, '%s/productconfig' % supercarrier.bpost_account_number),
                'send': url_join(self.base_url, '%s/orders' % supercarrier.bpost_account_number),
                'label': label_url}
        self.debug_logger("%s\n%s\n%s" % (URLS[action], HEADERS[action], xml.decode('utf-8') if xml else None), 'bpost_request_%s' % action)
        try:
            response = requests.request(METHODS[action], URLS[action], headers=HEADERS[action], data=xml, timeout=15)
        except requests.exceptions.Timeout:
            raise UserError(_('The BPost shipping service is unresponsive, please retry later.'))
        self.debug_logger("%s\n%s" % (response.status_code, response.text), 'bpost_response_%s' % action)

        return response.status_code, response.text
