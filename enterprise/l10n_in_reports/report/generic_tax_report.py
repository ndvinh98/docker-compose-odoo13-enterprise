# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api

class generic_tax_report(models.AbstractModel):
    _inherit = 'account.generic.tax.report'

    @api.model
    def _get_options(self, previous_options=None):
        # We want the filter_journals option to only be available if country is India
        if self.env.company.country_id.code == 'IN':
            self.filter_journals = True
        return super()._get_options(previous_options)
