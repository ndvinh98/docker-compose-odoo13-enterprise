from odoo import fields, models, api, _


class IotDevice(models.Model):
    _inherit = 'iot.device'

    qcp_test_type = fields.Char(compute='_compute_qcp_test_type')
    quality_point_ids = fields.One2many('quality.point', 'device_id')

    @api.depends('type')
    def _compute_qcp_test_type(self):
        types = {'device': 'measure', 'camera': 'picture', 'printer': 'print_label'}
        self.qcp_test_type = types.get(self.type, '')


class QualityPoint(models.Model):
    _inherit = "quality.point"

    device_id = fields.Many2one('iot.device', ondelete='restrict', domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
