# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import requests
from werkzeug.urls import url_join

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round

from .easypost_request import EasypostRequest

class DeliverCarrier(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(selection_add=[('easypost', 'Easypost')])
    easypost_test_api_key = fields.Char("Test API Key", groups="base.group_system", help="Enter your API test key from Easypost account.")
    easypost_production_api_key = fields.Char("Production API Key", groups="base.group_system", help="Enter your API production key from Easypost account")
    easypost_delivery_type = fields.Char('Easypost Carrier Type')
    easypost_delivery_type_id = fields.Char('Easypost Carrier Type ID, technical for API request')
    easypost_default_packaging_id = fields.Many2one("product.packaging", string="Default Package Type for Easypost", domain="[('easypost_carrier', '=', easypost_delivery_type)]")
    easypost_default_service_id = fields.Many2one("easypost.service", string="Default Service Level", help="If not set, the less expensive available service level will be chosen.", domain="[('easypost_carrier', '=', easypost_delivery_type)]")
    easypost_label_file_type = fields.Selection([
        ('PNG', 'PNG'), ('PDF', 'PDF'),
        ('ZPL', 'ZPL'), ('EPL2', 'EPL2')],
        string="Easypost Label File Type", default='PDF')
    
    def _compute_can_generate_return(self):
        super(DeliverCarrier, self)._compute_can_generate_return()
        for carrier in self:
            if carrier.delivery_type == 'easypost':
                carrier.can_generate_return = True

    def action_get_carrier_type(self):
        """ Return the list of carriers configured by the customer
        on its easypost account.
        """
        if self.delivery_type == 'easypost' and self.sudo().easypost_production_api_key:
            ep = EasypostRequest(self.sudo().easypost_production_api_key, self.log_xml)
            carriers = ep.fetch_easypost_carrier()
            if carriers:
                action = self.env.ref('delivery_easypost.act_delivery_easypost_carrier_type').read()[0]
                action['context'] = {
                    'carrier_types': carriers,
                    'default_delivery_carrier_id': self.id,
                }
                return action
        else:
            raise UserError('A production key is required in order to load your easypost carriers.')

    def easypost_rate_shipment(self, order):
        """ Return the rates for a quotation/SO."""
        ep = EasypostRequest(self.sudo().easypost_production_api_key if self.prod_environment else self.sudo().easypost_test_api_key, self.log_xml)
        response = ep.rate_request(self, order.partner_shipping_id, order.warehouse_id.partner_id, order)
        # Return error message
        if response.get('error_message'):
            return {
                'success': False,
                'price': 0.0,
                'error_message': response.get('error_message'),
                'warning_message': False
            }

        # Update price with the order currency
        rate = response.get('rate')
        if order.currency_id.name == rate['currency']:
            price = float(rate['rate'])
        else:
            quote_currency = self.env['res.currency'].search([('name', '=', rate['currency'])], limit=1)
            price = quote_currency._convert(float(rate['rate']), order.currency_id, self.env.company, fields.Date.today())

        return {
            'success': True,
            'price': price,
            'error_message': False,
            'warning_message': response.get('warning_message', False)
        }

    def easypost_send_shipping(self, pickings):
        """ It creates an easypost order and buy it with the selected rate on
        delivery method or cheapest rate if it is not set. It will use the
        packages used with the put in pack functionality or a single package if
        the user didn't use packages.
        Once the order is purchased. It will post as message the tracking
        links and the shipping labels.
        """
        res = []
        ep = EasypostRequest(self.sudo().easypost_production_api_key if self.prod_environment else self.sudo().easypost_test_api_key, self.log_xml)
        for picking in pickings:
            result = ep.send_shipping(self, picking.partner_id, picking.picking_type_id.warehouse_id.partner_id, picking=picking)
            if result.get('error_message'):
                raise UserError(_(result['error_message']))
            rate = result.get('rate')
            if rate['currency'] == picking.company_id.currency_id.name:
                price = float(rate['rate'])
            else:
                quote_currency = self.env['res.currency'].search([('name', '=', rate['currency'])], limit=1)
                price = quote_currency._convert(float(rate['rate']), picking.company_id.currency_id, self.env.company, fields.Date.today())

            # return tracking information
            carrier_tracking_link = ""
            for track_number, tracker_url in result.get('track_shipments_url').items():
                carrier_tracking_link += '<a href=' + tracker_url + '>' + track_number + '</a><br/>'

            carrier_tracking_ref = ' + '.join(result.get('track_shipments_url').keys())

            labels = []
            for track_number, label_url in result.get('track_label_data').items():
                label = requests.get(label_url)
                labels.append(('LabelEasypost-%s.%s' % (track_number, self.easypost_label_file_type), label.content))

            logmessage = _("Shipment created into Easypost<br/>"
                           "<b>Tracking Numbers:</b> %s<br/>") % (carrier_tracking_link)
            pickings.message_post(body=logmessage, attachments=labels)

            shipping_data = {'exact_price': price,
                             'tracking_number': carrier_tracking_ref}
            res = res + [shipping_data]
            # store order reference on picking
            picking.ep_order_ref = result.get('id')
            if picking.carrier_id.return_label_on_delivery:
                self.get_return_label(picking)
        return res

    def easypost_get_return_label(self, pickings, tracking_number=None, origin_date=None):
        ep = EasypostRequest(self.sudo().easypost_production_api_key if self.prod_environment else self.sudo().easypost_test_api_key, self.log_xml)
        result = ep.send_shipping(self, pickings.partner_id, pickings.picking_type_id.warehouse_id.partner_id, picking=pickings, is_return=True)
        if result.get('error_message'):
            raise UserError(_(result['error_message']))
        rate = result.get('rate')
        if rate['currency'] == pickings.company_id.currency_id.name:
            price = rate['rate']
        else:
            quote_currency = self.env['res.currency'].search([('name', '=', rate['currency'])], limit=1)
            price = quote_currency._convert(float(rate['rate']), pickings.company_id.currency_id, self.env.company, fields.Date.today())

        # return tracking information
        carrier_tracking_link = ""
        for track_number, tracker_url in result.get('track_shipments_url').items():
            carrier_tracking_link += '<a href=' + tracker_url + '>' + track_number + '</a><br/>'

        carrier_tracking_ref = ' + '.join(result.get('track_shipments_url').keys())

        labels = []
        for track_number, label_url in result.get('track_label_data').items():
            label = requests.get(label_url)
            labels.append(('%s-%s-%s.%s' % (self.get_return_label_prefix(), 'blablabla', track_number, self.easypost_label_file_type), label.content))
        pickings.message_post(body='Return Label', attachments=labels)


    def easypost_get_tracking_link(self, picking):
        """ Returns the tracking links from a picking. Easypost reutrn one
        tracking link by package. It specific to easypost since other delivery
        carrier use a single link for all packages.
        """
        ep = EasypostRequest(self.sudo().easypost_production_api_key if self.prod_environment else self.sudo().easypost_test_api_key, self.log_xml)
        tracking_urls = ep.get_tracking_link(picking.ep_order_ref)
        return len(tracking_urls) == 1 and tracking_urls[0][1] or json.dumps(tracking_urls)

    def easypost_cancel_shipment(self, pickings):
        # Note: Easypost API not provide shipment/order cancel mechanism
        raise UserError(_("You can't cancel Easypost shipping."))

    def _easypost_get_services_and_product_packagings(self):
        """ Get the list of services and product packagings by carrier
        type. They are stored in 2 dict stored in 2 distinct static json file.
        The dictionaries come from an easypost doc parsing since packages and
        services list are not available with an API request. The purpose of a
        json is to replace the static file request by an API request if easypost
        implements a way to do it.
        """
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        response_package = requests.get(url_join(base_url, '/delivery_easypost/static/data/packagings_by_carriers.json'))
        response_service = requests.get(url_join(base_url, '/delivery_easypost/static/data/services_by_carriers.json'))
        packages = response_package.json()
        services = response_service.json()
        return packages, services

    @api.onchange('delivery_type')
    def _onchange_delivery_type(self):
        if self.delivery_type == 'easypost':
            self = self.sudo()
            if not self.easypost_test_api_key or not self.easypost_production_api_key:
                carrier = self.env['delivery.carrier'].search([('delivery_type', '=', 'easypost'), ('company_id', '=', self.env.company.id)], limit=1)
                if carrier.easypost_test_api_key and not self.easypost_test_api_key:
                    self.easypost_test_api_key = carrier.easypost_test_api_key
                if carrier.easypost_production_api_key and not self.easypost_production_api_key:
                    self.easypost_production_api_key = carrier.easypost_production_api_key

    def _generate_services(self, rates):
        """ When a user do a rate request easypost returns
        a rates for each service available. However some services
        could not be guess before a first API call. This method
        complete the list of services for the used carrier type.
        """
        services_name = [rate.get('service') for rate in rates]
        existing_services = self.env['easypost.service'].search_read([
            ('name', 'in', services_name),
            ('easypost_carrier', '=', self.easypost_delivery_type)
        ], ["name"])
        for service_name in set([service['name'] for service in existing_services]) ^ set(services_name):
            self.env['easypost.service'].create({
                'name': service_name,
                'easypost_carrier': self.easypost_delivery_type
            })

    def _easypost_convert_weight(self, weight):
        """ Each API request for easypost required
        a weight in pounds.
        """
        weight_uom_id = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()
        weight_in_pounds = weight_uom_id._compute_quantity(weight, self.env.ref('uom.product_uom_lb'))
        weigth_in_ounces = float_round((weight_in_pounds * 16), precision_digits=1)
        return weigth_in_ounces
