# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools


class l10nBeMealVoucherReport(models.Model):
    _name = "l10n_be.meal.voucher.report"
    _description = 'Meal Voucher Summary / Report'
    _auto = False

    employee_id = fields.Many2one('hr.employee', string="Employee", readonly=True)
    day = fields.Date(readonly=True)

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)

        self._cr.execute("""
            CREATE or REPLACE view %s as (

                SELECT
                    row_number() OVER() AS id,
                    b.date_start_day::date AS day,
                    b.employee_id
                FROM (
                     /* Split work entry by day */
                    SELECT
                        b1.employee_id AS employee_id,
                        GREATEST(s, b1.date_start) AS date_start_day,
                        LEAST(s + interval '1 day', b1.date_stop) AS date_stop_day
                    FROM
                        hr_work_entry b1
                    CROSS JOIN generate_series(date_trunc('day', b1.date_start), date_trunc('day', b1.date_stop), interval '1 day') s
                    INNER JOIN hr_work_entry_type t ON t.id = b1.work_entry_type_id
                    WHERE t.meal_voucher = TRUE AND b1.state='validated'
                ) AS b
                GROUP BY b.employee_id, b.date_start_day::date, b.date_stop_day::date
                HAVING SUM(date_part('hour', b.date_stop_day - b.date_start_day)) >= 3
            );
        """ % self._table)
