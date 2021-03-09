# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    check_ids = fields.One2many('quality.check', 'production_id', string="Checks")
    quality_check_todo = fields.Boolean(compute='_compute_check')
    quality_check_fail = fields.Boolean(compute='_compute_check')
    quality_alert_ids = fields.One2many('quality.alert', "production_id", string="Alerts")
    quality_alert_count = fields.Integer(compute='_compute_quality_alert_count')

    def _compute_quality_alert_count(self):
        for production in self:
            production.quality_alert_count = len(production.quality_alert_ids)

    def _compute_check(self):
        for production in self:
            todo = False
            fail = False
            for check in production.check_ids:
                if check.quality_state == 'none':
                    todo = True
                elif check.quality_state == 'fail':
                    fail = True
                if fail and todo:
                    break
            production.quality_check_fail = fail
            production.quality_check_todo = todo

    def _get_quality_point_domain(self):
        return [('picking_type_id', '=', self.picking_type_id.id),
                ('company_id', '=', self.company_id.id),
                '|', ('product_id', '=', self.product_id.id),
                '&', ('product_id', '=', False),
                ('product_tmpl_id', '=', self.product_id.product_tmpl_id.id)]

    def _get_quality_check_values(self, quality_point):
        return {
                    'production_id': self.id,
                    'point_id': quality_point.id,
                    'team_id': quality_point.team_id.id,
                    'product_id': self.product_id.id,
                    'company_id': self.company_id.id,
                }

    def action_confirm(self):
        for production in self:
            points = self.env['quality.point'].search(production._get_quality_point_domain())
            for point in points:
                if point.check_execute_now():
                    self.env['quality.check'].create(production._get_quality_check_values(point))
        return super(MrpProduction, self).action_confirm()

    def button_quality_alert(self):
        self.ensure_one()
        action = self.env.ref('quality_control.quality_alert_action_check').read()[0]
        action['views'] = [(False, 'form')]
        action['context'] = {
            'default_company_id': self.company_id.id,
            'default_product_id': self.product_id.id,
            'default_product_tmpl_id': self.product_id.product_tmpl_id.id,
            'default_production_id': self.id,
        }
        return action

    def button_mark_done(self):
        for order in self:
            if any([(x.quality_state == 'none') for x in order.check_ids]):
                raise UserError(_('You still need to do the quality checks!'))
        return super(MrpProduction, self).button_mark_done()

    def open_quality_alert_mo(self):
        self.ensure_one()
        action = self.env.ref('quality_control.quality_alert_action_check').read()[0]
        action['context'] = {
            'default_company_id': self.company_id.id,
            'default_product_id': self.product_id.id,
            'default_product_tmpl_id': self.product_id.product_tmpl_id.id,
            'default_production_id': self.id,
            }
        action['domain'] = [('id', 'in', self.quality_alert_ids.ids)]
        action['views'] = [(False, 'tree'),(False,'form')]
        if self.quality_alert_count == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = self.quality_alert_ids.id
        return action

    def check_quality(self):
        self.ensure_one()
        checks = self.check_ids.filtered(lambda x: x.quality_state == 'none')
        if checks:
            action_rec = self.env.ref('quality_control.quality_check_action_small')
            if action_rec:
                action = action_rec.read([])[0]
                action['context'] = self.env.context
                action['res_id'] = checks[0].id
                return action

    def action_cancel(self):
        res = super(MrpProduction, self).action_cancel()
        self.sudo().mapped('check_ids').filtered(lambda x: x.quality_state == 'none').unlink()
        return res
