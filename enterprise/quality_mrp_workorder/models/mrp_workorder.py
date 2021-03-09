# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _
from odoo.exceptions import UserError


class MrpProductionWorkcenterLine(models.Model):
    _inherit = "mrp.workorder"

    measure = fields.Float(related='current_quality_check_id.measure', readonly=False)
    measure_success = fields.Selection(related='current_quality_check_id.measure_success', readonly=False)
    norm_unit = fields.Char(related='current_quality_check_id.norm_unit', readonly=False)

    def do_pass(self):
        self.ensure_one()
        self.current_quality_check_id.do_pass()
        return self._next()

    def do_fail(self):
        self.ensure_one()
        self.current_quality_check_id.do_fail()
        return self._next()

    def do_measure(self):
        self.ensure_one()
        self.current_quality_check_id.do_measure()
        return self._next()

    def _next(self, continue_production=False):
        self.ensure_one()
        old_check_id = self.current_quality_check_id
        result = super(MrpProductionWorkcenterLine, self)._next(continue_production=continue_production)
        if old_check_id.quality_state == 'fail':
            return old_check_id.show_failure_message()
        return result

    def button_quality_alert(self):
        self.ensure_one()
        action = self.env.ref('quality_control.quality_alert_action_check').read()[0]
        action['target'] = 'new'
        action['views'] = [(False, 'form')]
        action['context'] = {
            'default_company_id': self.company_id.id,
            'default_product_id': self.product_id.id,
            'default_product_tmpl_id': self.product_id.product_tmpl_id.id,
            'default_workorder_id': self.id,
            'default_production_id': self.production_id.id,
            'default_workcenter_id': self.workcenter_id.id,
            'discard_on_footer_button': True,
        }
        return action
