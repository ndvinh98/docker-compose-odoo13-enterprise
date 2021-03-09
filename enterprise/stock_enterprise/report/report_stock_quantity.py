# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo import api, models
from odoo.osv import expression
from odoo.tools import date_utils


class ReportStockQuantity(models.Model):
    _inherit = 'report.stock.quantity'

    @api.model
    def read_grid(self, row_fields, col_field, cell_field, domain=None, range=None, readonly_field=None, orderby=None):
        if not orderby:
            orderby = 'product_id, state'
        read_grid = super(ReportStockQuantity, self).read_grid(row_fields,
            col_field, cell_field, domain=domain, range=range,
            readonly_field=readonly_field, orderby=orderby)
        return read_grid

    @api.model
    def action_open_moves(self, product_id, state, date):
        date = datetime.strptime(date, '%Y-%m-%d')
        product = self.env['product.product'].browse(product_id)
        domain = [('product_id', '=', product_id)]
        if state in ('in', 'out'):
            domain = expression.AND([domain, [('date_expected', '>=', date)]])
        domain = expression.AND([domain, [('date_expected', '<', date_utils.add(date, days=1))]])
        domain = expression.AND([domain, [('state', 'not in', ['draft', 'cancel', 'done'])]])
        internal, loc_domain_in, loc_domain_out = product._get_domain_locations()
        if state == 'in':
            loc_domain = loc_domain_in
        elif state == 'out':
            loc_domain = loc_domain_out
        else:
            loc_domain = expression.OR([loc_domain_in, loc_domain_out])
        domain = expression.AND([domain, loc_domain])

        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'tree',
            'res_model': 'stock.move',
            'name': '%s %s' % (product.display_name, state),
            'views': [
                (self.env.ref('stock_enterprise.stock_enterprise_move_tree_view').id, 'list'),
            ],
            'domain': domain,
            'context': self.env.context,
        }
