# -*- coding: utf-8 -*-

from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        result = super(IrHttp, self).session_info()
        if request.env.user.has_group('base.group_user'):
            result.update(
                ocn_token_key=request.env.user.partner_id.ocn_token,
                fcm_project_id=self.env['ir.config_parameter'].sudo().get_param('odoo_ocn.project_id', False),
                inbox_action=request.env.ref('mail.action_discuss').id,
            )
        return result
