# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HelpdeskTeam(models.Model):
    _inherit = "helpdesk.team"

    elearning_id = fields.Many2one('slide.channel', 'eLearning')
    elearning_url = fields.Char('Presentations URL', readonly=True, related='elearning_id.website_url')

    @api.onchange('use_website_helpdesk_slides')
    def _onchange_use_website_helpdesk_slides(self):
        if not self.use_website_helpdesk_slides:
            self.elearning_id = False
