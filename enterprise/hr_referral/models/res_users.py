# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    hr_referral_level_id = fields.Many2one('hr.referral.level', groups="hr.group_hr_user")
    hr_referral_onboarding_page = fields.Boolean(groups="hr.group_hr_user")
    referral_point_ids = fields.One2many('hr.referral.points', 'ref_user_id')
    utm_source_id = fields.Many2one('utm.source', 'Source', ondelete='cascade', groups="hr.group_hr_user")

    @api.model
    def action_complete_onboarding(self, complete):
        if not self.env.user:
            return
        self.env.user.hr_referral_onboarding_page = bool(complete)
