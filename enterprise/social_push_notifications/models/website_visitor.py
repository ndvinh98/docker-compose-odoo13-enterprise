# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.exceptions import UserError


class WebsiteVisitor(models.Model):
    _inherit = 'website.visitor'

    push_token = fields.Char('Push Subscription', readonly=True, index=True)
    has_push_notifications = fields.Boolean('Push Notifications', compute='_compute_has_push_notifications')

    @api.depends('push_token')
    def _compute_has_push_notifications(self):
        for visitor in self:
            visitor.has_push_notifications = bool(visitor.push_token)

    def action_send_push_notification(self):
        """ Opens social media post form prefilled with selected website.visitor
         and push notification activated."""
        # validate if push notification are allowed for all selected visitors
        if all(visitor.push_token for visitor in self):
            push_media = self.env['social.media'].search([('media_type', '=', 'push_notifications')])
            action = self.env.ref('social.action_social_post').read()[0]
            action['views'] = [[False, 'form']]
            action['context'] = {
                'default_visitor_domain': "[('push_token', '!=', False), ('id', 'in', %s)]" % self.ids,
                'default_account_ids': push_media.account_ids.ids,
            }
            return action
        else:
            raise UserError(_("Some selected visitors do not allow push notifications."))
