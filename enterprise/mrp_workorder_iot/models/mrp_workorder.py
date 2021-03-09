# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _
from odoo.exceptions import UserError
import json


class MrpProductionWorkcenterLine(models.Model):
    _inherit = "mrp.workorder"

    ip = fields.Char(related='current_quality_check_id.point_id.device_id.iot_id.ip')
    identifier = fields.Char(related='current_quality_check_id.point_id.device_id.identifier')
    boxes = fields.Char(compute='_compute_boxes')
    device_name = fields.Char(related='current_quality_check_id.point_id.device_id.name', size=30, string='Device Name: ')

    def _compute_boxes(self):
        for wo in self:
            triggers = wo.workcenter_id.trigger_ids
            box_dict = {}
            for trigger in triggers:
                box = trigger.device_id.iot_id.ip
                box_dict.setdefault(box, [])
                box_dict[box].append([trigger.device_id.identifier, trigger.key, trigger.action])
            wo.boxes = json.dumps(box_dict)

    def action_print(self):
        quality_point_id = self.current_quality_check_id.point_id
        res = super(MrpProductionWorkcenterLine, self).action_print()

        if quality_point_id.device_id:
            res['device_id'] = quality_point_id.device_id.id

        return res


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    trigger_ids = fields.One2many('iot.trigger', 'workcenter_id', string="Triggers")


class IotTrigger(models.Model):
    _name = 'iot.trigger'
    _description = 'IOT Trigger'
    _order = 'sequence'

    sequence = fields.Integer(default=1)
    device_id = fields.Many2one('iot.device', 'Device', required=True)
    key = fields.Char('Key')
    workcenter_id = fields.Many2one('mrp.workcenter')
    action = fields.Selection([('picture', 'Take Picture'),
                               ('skip', 'Skip'),
                               ('pause', 'Pause'),
                               ('prev', 'Previous'),
                               ('next', 'Next'),
                               ('validate', 'Validate'),
                               ('cloMO', 'Close MO'),
                               ('cloWO', 'Close WO'),
                               ('finish', 'Finish'),
                               ('record', 'Record Production'),
                               ('cancel', 'Cancel'),
                               ('print-op', 'Print Operation'),
                               ('print-slip', 'Print Delivery Slip'),
                               ('print', 'Print Labels'),
                               ('pack', 'Pack'),
                               ('scrap', 'Scrap'),])

class IoTDevice(models.Model):
    _inherit = "iot.device"

    trigger_ids = fields.One2many('iot.trigger', 'device_id')
