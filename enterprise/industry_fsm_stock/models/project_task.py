# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.osv import expression


class Task(models.Model):
    _inherit = "project.task"

    def action_fsm_view_material(self):
        """Override to remove tracked products from the domain.
        """
        action = super(Task, self).action_fsm_view_material()
        action['domain'] = expression.AND([action.get('domain', []), [('tracking', '=', 'none')]])
        return action

    def action_fsm_validate(self):
        result = super(Task, self).action_fsm_validate()

        for task in self:
            if task.allow_billable and task.sale_order_id:
                task.sudo()._validate_stock()
        return result

    def _validate_stock(self):
        # need to re-run _action_launch_stock_rule, since the sale order can already be confirmed
        previous_product_uom_qty = {line.id: line.product_uom_qty for line in self.sale_order_id.order_line}
        self.sale_order_id.order_line._action_launch_stock_rule(previous_product_uom_qty=previous_product_uom_qty)
        for picking in self.sale_order_id.picking_ids:
            for move in picking.move_lines.filtered(lambda ml: ml.state != 'done'):
                for move_line in move.move_line_ids:
                    move_line.qty_done = move_line.product_uom_qty

        # context key used to not create backorders
        self.sale_order_id.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel']).with_context(cancel_backorder=True).action_done()
