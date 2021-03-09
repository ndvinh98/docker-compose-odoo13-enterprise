# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.modules import module as modules
import odoo
import json
import zipfile
import io
import json

class IoTController(http.Controller):

    @http.route('/iot/get_drivers', type='http', auth='public', csrf=False)
    def download_drivers(self, mac, auto):
        # Check mac is of one of the IoT Boxes
        box = request.env['iot.box'].sudo().search([('identifier', '=', mac)], limit=1)
        if not box or (auto == 'True' and not box.drivers_auto_update):
            return ''

        zip_list = []
        for module in modules.get_modules():
            for file in modules.get_module_filetree(module, 'drivers').keys():
                if file.startswith('.') or file.startswith('_'):
                    continue
                # zip it
                zip_list.append((modules.get_resource_path(module, 'drivers', file), file))
        file_like_object = io.BytesIO()
        zipfile_ob = zipfile.ZipFile(file_like_object, 'w')
        for zip in zip_list:
            zipfile_ob.write(zip[0], zip[1]) # In order to remove the absolute path
        zipfile_ob.close()
        return file_like_object.getvalue()

    @http.route('/iot/keyboard_layouts', type='http', auth='public', csrf=False)
    def load_keyboard_layouts(self, available_layouts):
        if not request.env['iot.keyboard.layout'].sudo().search_count([]):
            request.env['iot.keyboard.layout'].sudo().create(json.loads(available_layouts))
        return ''

    # Return home screen
    @http.route('/iot/box/<string:identifier>/screen_url', type='http', auth='public')
    def get_url(self, identifier):
        urls = {}
        iotbox = request.env['iot.box'].sudo().search([('identifier', '=', identifier)], limit=1)
        if iotbox:
            iot_devices = iotbox.device_ids.filtered(lambda device: device.type == 'display')
            for device in iot_devices:
                urls[device.identifier] = device.screen_url
        return json.dumps(urls)

    @http.route('/iot/setup', type='json', auth='public')
    def update_box(self, **kwargs):
        """
        This function receives a dict from the iot box with information from it 
        as well as devices connected and supported by this box.
        This function create the box and the devices and set the status (connected / disconnected)
         of devices linked with this box
        """
        if kwargs:
            # Box > V19
            iot_box = kwargs['iot_box']
            devices = kwargs['devices']
        else:
            # Box < V19
            data = request.jsonrequest
            iot_box = data
            devices = data['devices']

         # Update or create box
        box = request.env['iot.box'].sudo().search([('identifier', '=', iot_box['identifier'])], limit=1)
        if box:
            box = box[0]
            box.ip = iot_box['ip']
            box.name = iot_box['name']
        else:
            iot_token = request.env['ir.config_parameter'].sudo().search([('key', '=', 'iot_token')], limit=1)
            if iot_token.value.strip('\n') == iot_box['token']:
                box = request.env['iot.box'].sudo().create({
                    'name': iot_box['name'],
                    'identifier': iot_box['identifier'],
                    'ip': iot_box['ip'],
                    'version': iot_box['version'],
                })

        # Update or create devices
        if box:
            previously_connected_iot_devices = request.env['iot.device'].sudo().search([
                ('iot_id', '=', box.id),
                ('connected', '=', True)
            ])
            connected_iot_devices = request.env['iot.device'].sudo()
            for device_identifier in devices:
                available_types = [s[0] for s in request.env['iot.device']._fields['type'].selection]
                available_connections = [s[0] for s in request.env['iot.device']._fields['connection'].selection]

                data_device = devices[device_identifier]
                if data_device['type'] in available_types and data_device['connection'] in available_connections:
                    if data_device['connection'] == 'network':
                        device = request.env['iot.device'].sudo().search([('identifier', '=', device_identifier)])
                    else:
                        device = request.env['iot.device'].sudo().search([('iot_id', '=', box.id), ('identifier', '=', device_identifier)])
                
                    # If an `iot.device` record isn't found for this `device`, create a new one.
                    if not device:
                        device = request.env['iot.device'].sudo().create({
                            'iot_id': box.id,
                            'name': data_device['name'],
                            'identifier': device_identifier,
                            'type': data_device['type'],
                            'manufacturer': data_device['manufacturer'],
                            'connection': data_device['connection'],
                        })
                    elif device and device.type != data_device.get('type'):
                        device.write({
                        'name': data_device.get('name'),
                        'type': data_device.get('type'),
                        'manufacturer': data_device.get('manufacturer')
                        })

                    connected_iot_devices |= device
            # Mark the received devices as connected, disconnect the others.
            connected_iot_devices.write({'connected': True})
            (previously_connected_iot_devices - connected_iot_devices).write({'connected': False})
