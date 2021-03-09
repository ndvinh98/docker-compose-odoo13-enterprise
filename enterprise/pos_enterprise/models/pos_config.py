# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def _is_installed_pos_iot(self):
        installed = self.env['ir.module.module'].sudo().search_count([('name', '=', 'pos_iot'), ('state', '=', 'installed')])
        self.is_installed_pos_iot = True if installed else False

    module_pos_iot = fields.Boolean('IoT Box', default=False)
    is_installed_pos_iot = fields.Boolean('Pos IoT is installed', compute=_is_installed_pos_iot)

    @api.model
    def default_get(self, fields):
        vals = super(PosConfig, self).default_get(fields)
        if 'is_installed_pos_iot' in fields:
            installed = self.env['ir.module.module'].sudo().search_count([('name', '=', 'pos_iot'), ('state', '=', 'installed')])
            vals['is_installed_pos_iot'] = True if installed else False
        return vals

    @api.onchange('module_pos_iot')
    def onchange_module_pos_iot(self):
        self.is_posbox = self.module_pos_iot
