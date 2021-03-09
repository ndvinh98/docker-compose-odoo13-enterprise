# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from .dhl_request import DHLProvider

from odoo import models, fields, _
from odoo.tools import float_repr

class Providerdhl(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(selection_add=[('dhl', "DHL")])

    dhl_SiteID = fields.Char(string="DHL SiteID", groups="base.group_system")
    dhl_password = fields.Char(string="DHL Password", groups="base.group_system")
    dhl_account_number = fields.Char(string="DHL Account Number", groups="base.group_system")
    dhl_package_dimension_unit = fields.Selection([('I', 'Inches'),
                                                   ('C', 'Centimeters')],
                                                  default='C',
                                                  string='Package Dimension Unit')
    dhl_package_weight_unit = fields.Selection([('L', 'Pounds'),
                                                ('K', 'Kilograms')],
                                               default='K',
                                               string="Package Weight Unit")
    dhl_default_packaging_id = fields.Many2one('product.packaging', string='DHL Default Packaging Type')
    dhl_region_code = fields.Selection([('AP', 'Asia Pacific'),
                                        ('AM', 'America'),
                                        ('EU', 'Europe')],
                                       default='AM',
                                       string='Region')
    # Nowadays hidden, by default it's the D, couldn't find any documentation on other services
    dhl_product_code = fields.Selection([('0', '0 - Logistics Services'),
                                         ('1', '1 - Domestic Express 12:00'),
                                         ('2', '2 - B2C'),
                                         ('3', '3 - B2C'),
                                         ('4', '4 - Jetline'),
                                         ('5', '5 - Sprintline'),
                                         ('6', '6 - Secureline'),
                                         ('7', '7 - Express Easy'),
                                         ('8', '8 - Express Easy'),
                                         ('9', '9 - Europack'),
                                         ('A', 'A - Auto Reversals'),
                                         ('B', 'B - Break Bulk Express'),
                                         ('C', 'C - Medical Express'),
                                         ('D', 'D - Express Worldwide'),
                                         ('E', 'E - Express 9:00'),
                                         ('F', 'F - Freight Worldwide'),
                                         ('G', 'G - Domestic Economy Select'),
                                         ('H', 'H - Economy Select'),
                                         ('I', 'I - Break Bulk Economy'),
                                         ('J', 'J - Jumbo Box'),
                                         ('K', 'K - Express 9:00'),
                                         ('L', 'L - Express 10:30'),
                                         ('M', 'M - Express 10:30'),
                                         ('N', 'N - Domestic Express'),
                                         ('O', 'O - DOM Express 10:30'),
                                         ('P', 'P - Express Worldwide'),
                                         ('Q', 'Q - Medical Express'),
                                         ('R', 'R - GlobalMail Business'),
                                         ('S', 'S - Same Day'),
                                         ('T', 'T - Express 12:00'),
                                         ('U', 'U - Express Worldwide'),
                                         ('V', 'V - Europack'),
                                         ('W', 'W - Economy Select'),
                                         ('X', 'X - Express Envelope'),
                                         ('Y', 'Y - Express 12:00'),
                                         ('Z', 'Z - Destination Charges'),
                                         ],
                                        default='D',
                                        string='DHL Product')
    dhl_dutiable = fields.Boolean(string="Dutiable Material", help="Check this if your package is dutiable.")
    dhl_duty_payment = fields.Selection([('S', 'Sender'), ('R', 'Recipient')], required=True, default="S")
    dhl_label_image_format = fields.Selection([
        ('EPL2', 'EPL2'),
        ('PDF', 'PDF'),
        ('ZPL2', 'ZPL2'),
    ], string="Label Image Format", default='PDF')
    dhl_label_template = fields.Selection([
        ('8X4_A4_PDF', '8X4_A4_PDF'),
        ('8X4_thermal', '8X4_thermal'),
        ('8X4_A4_TC_PDF', '8X4_A4_TC_PDF'),
        ('6X4_thermal', '6X4_thermal'),
        ('6X4_A4_PDF', '6X4_A4_PDF'),
        ('8X4_CI_PDF', '8X4_CI_PDF'),
        ('8X4_CI_thermal', '8X4_CI_thermal'),
        ('8X4_RU_A4_PDF', '8X4_RU_A4_PDF'),
        ('6X4_PDF', '6X4_PDF'),
        ('8X4_PDF', '8X4_PDF')
    ], string="Label Template", default='8X4_A4_PDF')

    def _compute_can_generate_return(self):
        super(Providerdhl, self)._compute_can_generate_return()
        for carrier in self:
            if carrier.delivery_type == 'dhl':
                carrier.can_generate_return = True

    def dhl_rate_shipment(self, order):
        res = self._rate_shipment_vals(order=order)
        return res

    def _rate_shipment_vals(self, order=False, picking=False):
        if picking:
            order = picking.sale_id
            warehouse_partner_id = picking.picking_type_id.warehouse_id.partner_id
            currency_id = order.currency_id or picking.company_id.currency_id
            destination_partner_id = picking.partner_id
            if order:
                total_value = sum([line.product_id.lst_price * line.product_qty for line in order.order_line if not line.display_type])
            else:
                total_value = sum([line.product_id.lst_price * line.product_qty for line in picking.move_lines])
        else:
            warehouse_partner_id = order.warehouse_id.partner_id
            currency_id = order.currency_id or order.company_id.currency_id
            total_value = sum([line.product_id.lst_price * line.product_qty for line in order.order_line if not line.display_type])
            destination_partner_id = order.partner_id

        rating_request = {}
        srm = DHLProvider(self.log_xml, request_type="rate", prod_environment=self.prod_environment)
        check_value = srm.check_required_value(self, destination_partner_id, warehouse_partner_id, order=order, picking=picking)
        if check_value:
            return {'success': False,
                    'price': 0.0,
                    'error_message': check_value,
                    'warning_message': False}
        site_id = self.sudo().dhl_SiteID
        password = self.sudo().dhl_password
        rating_request['Request'] = srm._set_request(site_id, password)
        rating_request['From'] = srm._set_dct_from(warehouse_partner_id)
        if picking:
            rating_request['BkgDetails'] = srm._set_dct_bkg_details_from_picking(picking)
        else:
            total_weight = sum([line.product_qty * line.product_id.weight for line in order.order_line if not line.display_type])
            rating_request['BkgDetails'] = srm._set_dct_bkg_details(total_weight, self, order.company_id.partner_id)
        rating_request['To'] = srm._set_dct_to(destination_partner_id)
        if self.dhl_dutiable:
            rating_request['Dutiable'] = srm._set_dct_dutiable(total_value, currency_id.name)
        real_rating_request = {}
        real_rating_request['GetQuote'] = rating_request
        real_rating_request['schemaVersion'] = 2.0
        response = srm._process_rating(real_rating_request)

        available_product_code = []
        shipping_charge = False
        qtd_shp = response.findall('GetQuoteResponse/BkgDetails/QtdShp')
        if qtd_shp:
            for q in qtd_shp:
                charge = q.find('ShippingCharge').text
                global_product_code = q.find('GlobalProductCode').text
                if global_product_code == self.dhl_product_code and charge:
                    shipping_charge = charge
                    shipping_currency = q.find('CurrencyCode') or False
                    shipping_currency = shipping_currency and shipping_currency.text
                    break;
                else:
                    available_product_code.append(global_product_code)
        else:
            condition = response.find('GetQuoteResponse/Note/Condition')
            if condition:
                condition_code = condition.find('ConditionCode').text
                if condition_code == '410301':
                    return {
                        'success': False,
                        'price': 0.0,
                        'error_message': "%s.\n%s" % (_(condition.find('ConditionData').text), _("Hint: The destination may not require the dutiable option.")),
                        'warning_message': False,
                    }
                elif condition_code in ['420504', '420505', '420506']:
                    return {
                        'success': False,
                        'price': 0.0,
                        'error_message': "%s." % (_(condition.find('ConditionData').text)),
                        'warning_message': False,
                    }
        if shipping_charge:
            if order:
                order_currency = order.currency_id
            else:
                order_currency = picking.sale_id.currency_id or picking.company_id.currency_id
            if not shipping_currency or order_currency.name == shipping_currency:
                price = float(shipping_charge)
            else:
                quote_currency = self.env['res.currency'].search([('name', '=', shipping_currency)], limit=1)
                price = quote_currency._convert(float(shipping_charge), order_currency, order.company_id or picking.company_id, order.date_order or fields.Date.today())
            return {'success': True,
                    'price': price,
                    'error_message': False,
                    'warning_message': False}

        if available_product_code:
            return {'success': False,
                    'price': 0.0,
                    'error_message': (_("There is no price available for this shipping, you should rather try with the DHL product %s") % available_product_code[0]),
                    'warning_message': False}

    def dhl_send_shipping(self, pickings):
        res = []
        for picking in pickings:
            shipment_request = {}
            srm = DHLProvider(self.log_xml, request_type="ship", prod_environment=self.prod_environment)
            site_id = self.sudo().dhl_SiteID
            password = self.sudo().dhl_password
            account_number = self.sudo().dhl_account_number
            shipment_request['Request'] = srm._set_request(site_id, password)
            shipment_request['RegionCode'] = srm._set_region_code(self.dhl_region_code)
            shipment_request['PiecesEnabled'] = srm._set_pieces_enabled(True)
            shipment_request['RequestedPickupTime'] = srm._set_requested_pickup_time(True)
            shipment_request['Billing'] = srm._set_billing(account_number, "S", self.dhl_duty_payment, self.dhl_dutiable)
            shipment_request['Consignee'] = srm._set_consignee(picking.partner_id)
            shipment_request['Shipper'] = srm._set_shipper(account_number, picking.company_id.partner_id, picking.picking_type_id.warehouse_id.partner_id)
            total_value = sum([line.product_id.lst_price * line.product_uom_qty for line in picking.move_lines])
            currency_name = picking.sale_id.currency_id.name or picking.company_id.currency_id.name
            if self.dhl_dutiable:
                shipment_request['Dutiable'] = srm._set_dutiable(total_value, currency_name)
            shipment_request['ShipmentDetails'] = srm._set_shipment_details(picking)
            shipment_request['LabelImageFormat'] = srm._set_label_image_format(self.dhl_label_image_format)
            shipment_request['Label'] = srm._set_label(self.dhl_label_template)
            shipment_request['schemaVersion'] = 6.2
            shipment_request['LanguageCode'] = 'en'
            dhl_response = srm._process_shipment(shipment_request)
            traking_number = dhl_response.AirwayBillNumber
            logmessage = (_("Shipment created into DHL <br/> <b>Tracking Number : </b>%s") % (traking_number))
            picking.message_post(body=logmessage, attachments=[('LabelDHL-%s.%s' % (traking_number, self.dhl_label_image_format), dhl_response.LabelImage[0].OutputImage)])
            shipping_data = {
                'exact_price': 0,
                'tracking_number': traking_number,
            }
            rate = self._rate_shipment_vals(picking=picking)
            shipping_data['exact_price'] = rate['price']
            if self.return_label_on_delivery:
                self.get_return_label(picking)
            res = res + [shipping_data]

        return res

    def dhl_get_return_label(self, picking, tracking_number=None, origin_date=None):
        shipment_request = {}
        srm = DHLProvider(self.log_xml, request_type="ship", prod_environment=self.prod_environment)
        site_id = self.sudo().dhl_SiteID
        password = self.sudo().dhl_password
        account_number = self.sudo().dhl_account_number
        shipment_request['Request'] = srm._set_request(site_id, password)
        shipment_request['RegionCode'] = srm._set_region_code(self.dhl_region_code)
        shipment_request['PiecesEnabled'] = srm._set_pieces_enabled(True)
        shipment_request['RequestedPickupTime'] = srm._set_requested_pickup_time(True)
        shipment_request['Billing'] = srm._set_billing(account_number, "S", "S", self.dhl_dutiable)
        shipment_request['Consignee'] = srm._set_consignee(picking.picking_type_id.warehouse_id.partner_id)
        shipment_request['Shipper'] = srm._set_shipper(account_number, picking.partner_id, picking.partner_id)
        total_value = sum([line.product_id.lst_price * line.product_uom_qty for line in picking.move_lines])
        currency_name = picking.sale_id.currency_id.name or picking.company_id.currency_id.name
        if self.dhl_dutiable:
            shipment_request['Dutiable'] = srm._set_dutiable(total_value, currency_name)
        shipment_request['ShipmentDetails'] = srm._set_shipment_details(picking)
        shipment_request['LabelImageFormat'] = srm._set_label_image_format(self.dhl_label_image_format)
        shipment_request['Label'] = srm._set_label(self.dhl_label_template)
        shipment_request['SpecialService'] = []
        shipment_request['SpecialService'].append(srm._set_return())
        shipment_request['schemaVersion'] = 6.2
        shipment_request['LanguageCode'] = 'en'
        dhl_response = srm._process_shipment(shipment_request)
        traking_number = dhl_response.AirwayBillNumber
        logmessage = (_("Shipment created into DHL <br/> <b>Tracking Number : </b>%s") % (traking_number))
        picking.message_post(body=logmessage, attachments=[('%s-%s-%s.%s' % (self.get_return_label_prefix(), traking_number, 1, self.dhl_label_image_format), dhl_response.LabelImage[0].OutputImage)])
        shipping_data = {
            'exact_price': 0,
            'tracking_number': traking_number,
        }
        return shipping_data

    def dhl_get_tracking_link(self, picking):
        return 'http://www.dhl.com/en/express/tracking.html?AWB=%s' % picking.carrier_tracking_ref

    def dhl_cancel_shipment(self, picking):
        # Obviously you need a pick up date to delete SHIPMENT by DHL. So you can't do it if you didn't schedule a pick-up.
        picking.message_post(body=_(u"You can't cancel DHL shipping without pickup date."))
        picking.write({'carrier_tracking_ref': '',
                       'carrier_price': 0.0})

    def _dhl_convert_weight(self, weight, unit):
        weight_uom_id = self.env['product.template']._get_weight_uom_id_from_ir_config_parameter()
        if unit == 'L':
            weight = weight_uom_id._compute_quantity(weight, self.env.ref('uom.product_uom_lb'), round=False)
        else:
            weight = weight_uom_id._compute_quantity(weight, self.env.ref('uom.product_uom_kgm'), round=False)
        return float_repr(weight, 3)
