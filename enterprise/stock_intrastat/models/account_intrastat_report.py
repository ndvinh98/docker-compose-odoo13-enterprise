# -*- coding: utf-8 -*-

from odoo import api, exceptions, fields, models


class IntrastatReport(models.AbstractModel):
    _inherit = 'account.intrastat.report'

    @api.model
    def _fill_missing_values(self, vals, cache=None):
        vals = super(IntrastatReport, self)._fill_missing_values(vals, cache)

        # Erase the company region code by the warehouse region code, if any
        invoice_ids = [row['invoice_id'] for row in vals]
        if cache is None:
            cache = {}

        # If the region codes do not apply on the warehouses, no need to search for stock moves
        warehouses = self.env['stock.warehouse'].with_context(active_test=False).search([])
        regions = warehouses.mapped('intrastat_region_id')
        if not regions:
            return vals

        # If all moves are from the same region, assign its code to all values
        if len(regions) == 1 and all(wh.intrastat_region_id for wh in warehouses):
            for val in vals:
                val['region_code'] = regions.code
            return vals

        for index, invoice in enumerate(self.env['account.move'].browse(invoice_ids)):
            stock_moves = invoice._stock_account_get_last_step_stock_moves()
            if stock_moves:
                warehouse = stock_moves[0].warehouse_id or stock_moves[0].picking_id.picking_type_id.warehouse_id
                cache_key = 'warehouse_region_%d' % warehouse.id
                if not cache.get(cache_key) and warehouse.intrastat_region_id.code:
                    # Cache the computed value to avoid performance loss.
                    cache[cache_key] = warehouse.intrastat_region_id.code
                if cache.get(cache_key):
                    vals[index]['region_code'] = cache[cache_key]
        return vals
