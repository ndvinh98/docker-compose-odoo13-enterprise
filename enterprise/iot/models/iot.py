import base64
import requests

from odoo import api, fields, models, exceptions, _
from odoo.models import AbstractModel

# ----------------------------------------------------------
# Models for client
# ----------------------------------------------------------
class IotBox(models.Model):
    _name = 'iot.box'
    _description = 'IoT Box'

    name = fields.Char('Name', readonly=True)
    identifier = fields.Char(string='Identifier (Mac Address)', readonly=True)
    device_ids = fields.One2many('iot.device', 'iot_id', string="Devices", readonly=True)
    device_count = fields.Integer(compute='_compute_device_count')
    ip = fields.Char('Domain Address', readonly=True)
    ip_url = fields.Char('IoT Box Home Page', readonly=True, compute='_compute_ip_url')
    screen_url = fields.Char('Screen URL', help="Url of the page that will be displayed by hdmi port of the box.")
    drivers_auto_update = fields.Boolean('Automatic drivers update', help='Automatically update drivers when the IoT Box boots', default=True)
    version = fields.Char('Image Version', readonly=True)
    company_id = fields.Many2one('res.company', 'Company')

    def _compute_ip_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        if base_url[:5] == 'https':
            url = 'https://%s'
        else:
            url = 'http://%s:8069'

        for box in self:
            if not box.ip:
                box.ip_url = False
            else:
                box.ip_url = url % box.ip

    def _compute_device_count(self):
        for box in self:
            box.device_count = len(box.device_ids)


class IotDevice(models.Model):
    _name = 'iot.device'
    _description = 'IOT Device'

    iot_id = fields.Many2one('iot.box', string='IoT Box', required = True)
    name = fields.Char('Name')
    identifier = fields.Char(string='Identifier', readonly=True)
    type = fields.Selection([
        ('printer', 'Printer'),
        ('camera', 'Camera'),
        ('keyboard', 'Keyboard'),
        ('scanner', 'Barcode Scanner'),
        ('device', 'Device'),
        ('payment', 'Payment Terminal'),
        ('scale', 'Scale'),
        ('display', 'Display'),
        ('fiscal_data_module', 'Fiscal Data Module'),
        ], readonly=True, default='device', string='Type',
        help="Type of device.")
    manufacturer = fields.Char(string='Manufacturer', readonly=True)
    connection = fields.Selection([
        ('network', 'Network'),
        ('direct', 'USB'),
        ('bluetooth', 'Bluetooth'),
        ('serial', 'Serial'),
        ('hdmi', 'Hdmi'),
        ], readonly=True, string="Connection",
        help="Type of connection.")
    report_ids = fields.One2many('ir.actions.report', 'device_id', string='Reports')
    iot_ip = fields.Char(related="iot_id.ip")
    company_id = fields.Many2one('res.company', 'Company', related="iot_id.company_id")
    connected = fields.Boolean(string='Status', help='If device is connected to the IoT Box', readonly=True)
    keyboard_layout = fields.Many2one('iot.keyboard.layout', string='Keyboard Layout')
    screen_url = fields.Char('Screen URL', help="URL of the page that will be displayed by the device, leave empty to use the customer facing display of the POS.")

    def name_get(self):
        return [(i.id, "[" + i.iot_id.name +"] " + i.name) for i in self]


class IrActionReport(models.Model):
    _inherit = 'ir.actions.report'

    device_id = fields.Many2one('iot.device', string='IoT Device', domain="[('type', '=', 'printer')]",
                                help='When setting a device here, the report will be printed through this device on the IoT Box')

    def iot_render(self, res_ids, data=None):
        if self.mapped('device_id'):
            device = self.mapped('device_id')[0]
        else:
            device = self.env['iot.device'].browse(data['device_id'])
        datas = self.render(res_ids, data=data)
        data_bytes = datas[0]
        data_base64 = base64.b64encode(data_bytes)
        return device.iot_id.ip, device.identifier, data_base64

    def report_action(self, docids, data=None, config=True):
        result = super(IrActionReport, self).report_action(docids, data, config)
        if result.get('type') != 'ir.actions.report':
            return result
        device = self.device_id
        if data and data.get('device_id'):
            device = self.env['iot.device'].browse(data['device_id'])

        result['id'] = self.id
        result['device_id'] = device.identifier
        return result

class PublisherWarrantyContract(models.AbstractModel):
    _inherit = "publisher_warranty.contract"
    _description = 'Publisher Warranty Contract For IoT Box'

    @api.model
    def _get_message(self):
        msg = super(PublisherWarrantyContract, self)._get_message()
        msg['IoTBox'] = self.env['iot.box'].search_count([])
        return msg

class KeyboardLayout(models.Model):
    _name = 'iot.keyboard.layout'
    _description = 'Keyboard Layout'

    name = fields.Char('Name')
    layout = fields.Char('Layout')
    variant = fields.Char('Variant')
