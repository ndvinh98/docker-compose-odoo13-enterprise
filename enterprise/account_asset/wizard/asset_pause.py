# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class AssetPause(models.TransientModel):
    _name = 'account.asset.pause'
    _description = 'Pause Asset'

    date = fields.Date(string='Pause date', required=True, default=fields.Date.today())
    asset_id = fields.Many2one('account.asset', required=True)

    def do_action(self):
        for record in self:
            record.asset_id.pause(pause_date=record.date)
