# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import api, models, _
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = "stock.move"

    def _action_confirm(self, merge=True, merge_into=False):
        moves = super(StockMove, self)._action_confirm(merge=merge, merge_into=merge_into)
        if self.env.context.get('skip_check'):
            # Skip checks if extra moves were created during transfer
            return moves

        moves._create_quality_checks()
        return moves

    def _create_quality_checks(self):
        # Used to avoid duplicated quality points
        quality_points_list = set([])

        pick_moves = defaultdict(lambda: self.env['stock.move'])
        for move in self:
            pick_moves[move.picking_id] |= move

        for picking, moves in pick_moves.items():
            for check in picking.sudo().check_ids:
                point_key = (check.picking_id.id, check.point_id.id, check.team_id.id, check.product_id.id)
                quality_points_list.add(point_key)
            quality_points = self.env['quality.point'].sudo().search([
                ('picking_type_id', '=', picking.picking_type_id.id),
                '|', ('product_id', 'in', moves.mapped('product_id').ids),
                '&', ('product_id', '=', False), ('product_tmpl_id', 'in', moves.mapped('product_id').mapped('product_tmpl_id').ids)])
            for point in quality_points:
                if point.check_execute_now():
                    if point.product_id:
                        point_key = (picking.id, point.id, point.team_id.id, point.product_id.id)
                        if point_key in quality_points_list:
                            continue
                        self.env['quality.check'].sudo().create({
                            'picking_id': picking.id,
                            'point_id': point.id,
                            'team_id': point.team_id.id,
                            'product_id': point.product_id.id,
                            'company_id': picking.company_id.id,
                        })
                        quality_points_list.add(point_key)
                    else:
                        products = picking.move_lines.filtered(lambda move: move.product_id.product_tmpl_id == point.product_tmpl_id).mapped('product_id')
                        for product in products:
                            point_key = (picking.id, point.id, point.team_id.id, product.id)
                            if point_key in quality_points_list:
                                continue
                            self.env['quality.check'].sudo().create({
                                'picking_id': picking.id,
                                'point_id': point.id,
                                'team_id': point.team_id.id,
                                'product_id': product.id,
                                'company_id': picking.company_id.id,
                            })
                            quality_points_list.add(point_key)
