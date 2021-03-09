# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class CalendarEvent(models.Model):
    """ Model for Calendar Event """
    _inherit = 'calendar.event'

    @api.model_create_multi
    def create(self, vals_list):
        results = super().create(vals_list)
        for result in results.filtered(lambda r: r.res_model == 'hr.appraisal'):
            appraisal = self.env['hr.appraisal'].browse(result.res_id)
            if appraisal.exists():
                appraisal.write({
                    'meeting_id': result.id,
                    'date_final_interview': result.start_date if result.allday else result.start_datetime
                })
        return results
