# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.http import request

class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        res = super(IrHttp, self).session_info()
        if request.env.user.has_group('base.group_user'):
            company_id = res['company_id']
            res['company_currency_id'] = request.env['res.company'].browse(company_id).currency_id.id if company_id else None
            res['companies_currency_id'] = {comp.id: comp.currency_id.id for comp in request.env.user.company_ids}
        return res
