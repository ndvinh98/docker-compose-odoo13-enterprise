# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

class CarrierType(models.TransientModel):
    _name = "delivery.carrier.easypost"
    _description = "Carrier Type"

    carrier_type = fields.Selection(selection="_get_carrier_types")
    delivery_carrier_id = fields.Many2one('delivery.carrier')

    def _get_carrier_types(self):
        if self.env.context.get('carrier_types'):
            return [(carrier, carrier) for carrier in self.env.context.get('carrier_types').keys()]
        else:
            return []

    def action_validate(self):
        if self.delivery_carrier_id.easypost_delivery_type != self.carrier_type:
            # Update delivery carrier with selected type.
            self.delivery_carrier_id.easypost_delivery_type = self.carrier_type
            self.delivery_carrier_id.easypost_delivery_type_id = self.env.context['carrier_types'][self.carrier_type]

            self.delivery_carrier_id.easypost_delivery_type = self.carrier_type
            self.delivery_carrier_id.easypost_default_packaging_id = False
            self.delivery_carrier_id.easypost_default_service_id = False

        # Contact the proxy in order to get the predefined
        # product packaging proposed on the easypost website
        # https://www.easypost.com/docs/api.html#predefined-packages
        packagings_by_carriers, services_by_carriers = self.env['delivery.carrier']._easypost_get_services_and_product_packagings()
        packagings = packagings_by_carriers.get(self.carrier_type)
        services = services_by_carriers.get(self.carrier_type)
        if packagings:
            already_existing_packages = self.env['product.packaging'].search_read([
                ('package_carrier_type', '=', 'easypost'),
                ('easypost_carrier', '=', self.carrier_type),
                ('shipper_package_code', 'in', packagings),
                ('name', 'in', packagings)
            ], ['name'])
            # Difference between the product packaging already
            # present in the database and the new one fetched
            # on the easypost documentation page.
            for packaging in set(packagings) ^ set([package['name'] for package in already_existing_packages]):
                self.env['product.packaging'].create({
                    'name': packaging,
                    'package_carrier_type': 'easypost',
                    'shipper_package_code': packaging,
                    'easypost_carrier': self.carrier_type,
                })
        if services:
            # Same than product packaging but for service
            # level https://www.easypost.com/docs/api.html#service-levels
            already_existing_services = self.env['product.packaging'].search_read([
                ('easypost_carrier', '=', self.carrier_type),
                ('name', 'in', services)
            ], ['name'])
            for service in set(services) ^ set([service['name'] for service in already_existing_services]):
                self.env['easypost.service'].create({
                    'name': service,
                    'easypost_carrier': self.carrier_type,
                })
        # Open the delivery carrier form view in edit mode,
        # the purpose is to force the user to set a product
        # packaging in order to get dimension. Mandatory for
        # shiment API request.
        action = self.env.ref('delivery.action_delivery_carrier_form').read()[0]
        action['res_id'] = self.delivery_carrier_id.id
        action['views'] = [(self.env.ref('delivery.view_delivery_carrier_form').id, 'form')]
        action['context'] = {'form_view_initial_mode': 'edit'}
        return action
