# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

class RentalSchedule(models.Model):
    _inherit = "sale.rental.schedule"

    lot_id = fields.Many2one('stock.production.lot', 'Serial Number', readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse', readonly=True)
    # TODO color depending on report_line_status

    def _get_product_name(self):
        return """COALESCE(lot_info.name, t.name) as product_name"""

    def _id(self):
        return """CONCAT(lot_info.lot_id, pdg.max_id, sol.id) as id"""

    def _quantity(self):
        return """
            CASE WHEN lot_info.lot_id IS NULL then sum(sol.product_uom_qty / u.factor * u2.factor) ELSE 1.0 END as product_uom_qty,
            CASE WHEN lot_info.lot_id IS NULL then sum(sol.qty_delivered / u.factor * u2.factor)
                WHEN lot_info.report_line_status = 'reserved' then 0.0
                ELSE 1.0 END as qty_delivered,
            CASE WHEN lot_info.lot_id IS NULL then sum(sol.qty_returned / u.factor * u2.factor)
                WHEN lot_info.report_line_status = 'returned' then 1.0
                ELSE 0.0 END as qty_returned
        """

    def _late(self):
        return """
            CASE when lot_info.lot_id is NULL then
                CASE WHEN sol.pickup_date < NOW() AT TIME ZONE 'UTC' AND sol.qty_delivered < sol.product_uom_qty THEN TRUE
                    WHEN sol.return_date < NOW() AT TIME ZONE 'UTC' AND sol.qty_returned < sol.qty_delivered THEN TRUE
                    ELSE FALSE
                END
            ELSE
                CASE WHEN lot_info.report_line_status = 'returned' THEN FALSE
                    WHEN lot_info.report_line_status = 'pickedup' THEN
                        CASE WHEN sol.return_date < NOW() AT TIME ZONE 'UTC' THEN TRUE
                        ELSE FALSE
                        END
                    ELSE
                        CASE WHEN sol.pickup_date < NOW() AT TIME ZONE 'UTC' THEN TRUE
                        ELSE FALSe
                        END
                END
            END as late
        """

    def _report_line_status(self):
        return """
            CASE when lot_info.lot_id is NULL then
                CASE when sol.qty_returned = sol.qty_delivered AND sol.qty_delivered = sol.product_uom_qty then 'returned'
                    when sol.qty_delivered = sol.product_uom_qty then 'pickedup'
                    else 'reserved'
                END
            ELSE lot_info.report_line_status
            END as report_line_status
        """

    def _color(self):
        """2 = orange, 4 = blue, 6 = red, 7 = green"""
        return """
            CASE when lot_info.lot_id is NULL then
                CASE WHEN sol.pickup_date < NOW() AT TIME ZONE 'UTC' AND sol.qty_delivered < sol.product_uom_qty THEN 4
                    WHEN sol.return_date < NOW() AT TIME ZONE 'UTC' AND sol.qty_returned < sol.qty_delivered THEN 6
                    when sol.qty_returned = sol.qty_delivered AND sol.qty_delivered = sol.product_uom_qty THEN 7
                    WHEN sol.qty_delivered = sol.product_uom_qty THEN 2
                    ELSE 4
                END
            ELSE
                CASE WHEN lot_info.report_line_status = 'returned' THEN 7
                    WHEN lot_info.report_line_status = 'pickedup' THEN
                        CASE WHEN sol.return_date < NOW() AT TIME ZONE 'UTC' THEN 6
                        ELSE 2
                        END
                    ELSE 4
                END
            END as color
        """

    def _with(self):
        return """
            WITH ordered_lots (lot_id, name, sol_id, report_line_status) AS
                (SELECT
                    lot.id as lot_id,
                    lot.name,
                    COALESCE(res.sale_order_line_id, pickedup.sale_order_line_id) as sol_id,
                    CASE
                        WHEN returned.stock_production_lot_id IS NOT NULL THEN 'returned'
                        WHEN pickedup.stock_production_lot_id IS NOT NULL THEN 'pickedup'
                        ELSE 'reserved'
                    END AS report_line_status
                    FROM
                        rental_reserved_lot_rel res
                    FULL OUTER JOIN rental_pickedup_lot_rel pickedup
                        ON res.sale_order_line_id=pickedup.sale_order_line_id
                        AND res.stock_production_lot_id=pickedup.stock_production_lot_id
                    LEFT OUTER JOIN rental_returned_lot_rel returned
                        ON returned.sale_order_line_id=pickedup.sale_order_line_id
                        AND returned.stock_production_lot_id=pickedup.stock_production_lot_id
                    JOIN stock_production_lot lot
                        ON res.stock_production_lot_id=lot.id
                        OR pickedup.stock_production_lot_id=lot.id
                ),
                sol_id_max (id) AS
                    (SELECT MAX(id) FROM sale_order_line),
                lot_id_max (id) AS
                    (SELECT MAX(id) FROM stock_production_lot),
                padding (max_id) AS
                    (SELECT CASE when lot_id_max > sol_id_max then lot_id_max ELSE sol_id_max END as max_id from lot_id_max, sol_id_max)
        """

    def _select(self):
        return super(RentalSchedule, self)._select() + """,
            lot_info.lot_id as lot_id,
            s.warehouse_id as warehouse_id
        """

    def _from(self):
        return super(RentalSchedule, self)._from() + """
            LEFT OUTER JOIN ordered_lots lot_info ON sol.id=lot_info.sol_id,
            padding pdg
        """

    def _groupby(self):
        return super(RentalSchedule, self)._groupby() + """,
            pdg.max_id,
            lot_info.lot_id,
            lot_info.name,
            lot_info.report_line_status"""
