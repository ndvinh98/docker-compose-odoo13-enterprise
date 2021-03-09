# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    fsm_quantity = fields.Integer('Material Quantity', compute="_compute_fsm_quantity")

    def _compute_fsm_quantity(self):
        task_id = self.env.context.get('fsm_task_id')
        if task_id:
            task = self.env['project.task'].browse(task_id)
            product_map = {sol.product_id.id: sol.product_uom_qty for sol in task.sudo().sale_order_id.order_line}

            for product in self:
                product.fsm_quantity = product_map.get(product.id, 0)
        else:
            self.fsm_quantity = False

    def fsm_add_quantity(self):
        task_id = self.env.context.get('fsm_task_id')
        if task_id:
            task = self.env['project.task'].browse(task_id)

            # don't add material on confirmed SO to avoid inconsistence with the stock picking
            if task.fsm_done:
                return False

            # project user with no sale rights should be able to add materials
            SaleOrderLine = self.env['sale.order.line']
            if self.user_has_groups('project.group_project_user'):
                task = task.sudo()
                SaleOrderLine = SaleOrderLine.sudo()

            sale_line = SaleOrderLine.search([('order_id', '=', task.sale_order_id.id), ('product_id', '=', self.id)], limit=1)

            if sale_line:  # existing line: increment ordered qty (and delivered, if delivered method)
                vals = {
                    'product_uom_qty': sale_line.product_uom_qty + 1
                }
                if sale_line.qty_delivered_method == 'manual':
                    vals['qty_delivered'] = sale_line.qty_delivered + 1
                sale_line.with_context(fsm_no_message_post=True).write(vals)
            else:  # create new SOL
                vals = {
                    'order_id': task.sale_order_id.id,
                    'product_id': self.id,
                    'product_uom_qty': 1,
                    'product_uom': self.uom_id.id,
                }
                if self.service_type == 'manual':
                    vals['qty_delivered'] = 1

                # Note: force to False to avoid changing planned hours when modifying product_uom_qty on SOL
                # for materials. Set the current task for service to avoid re-creating a task on SO cnofirmation.
                if self.type == 'service':
                    vals['task_id'] = task_id
                else:
                    vals['task_id'] = False
                if task.sale_order_id.pricelist_id.discount_policy == 'without_discount':
                    sol = SaleOrderLine.new(vals)
                    sol._onchange_discount()
                    vals.update({'discount': sol.discount or 0.0})
                sale_line = SaleOrderLine.create(vals)

        return True

    def fsm_remove_quantity(self):
        task_id = self.env.context.get('fsm_task_id')
        if task_id:
            task = self.env['project.task'].browse(task_id)

            # don't remove material on confirmed SO to avoid inconsistence with the stock picking
            if task.fsm_done:
                return False

            # project user with no sale rights should be able to remove materials
            SaleOrderLine = self.env['sale.order.line']
            if self.user_has_groups('project.group_project_user'):
                task = task.sudo()
                SaleOrderLine = SaleOrderLine.sudo()

            sale_line = SaleOrderLine.search([('order_id', '=', task.sale_order_id.id), ('product_id', '=', self.id)], limit=1)
            if sale_line:
                vals = {
                    'product_uom_qty': sale_line.product_uom_qty - 1
                }
                if sale_line.qty_delivered_method == 'manual':
                    vals['qty_delivered'] = sale_line.qty_delivered - 1

                if vals['product_uom_qty'] <= 0 and task.sale_order_id.state != 'sale':
                    sale_line.unlink()
                else:
                    sale_line.with_context(fsm_no_message_post=True).write(vals)

        return True
