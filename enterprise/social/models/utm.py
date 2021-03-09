# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class UtmCampaign(models.Model):
    _inherit = 'utm.campaign'

    social_post_ids = fields.One2many('social.post', 'utm_campaign_id', string="All related social media posts")
    social_posts_count = fields.Integer(compute="_compute_social_posts_count", string='Social Media Posts')
    social_engagement = fields.Integer(compute="_compute_social_engagement", string='Number of interactions (likes, shares, comments ...) with the social posts')

    def _compute_social_engagement(self):
        campaigns_engagement = {campaign.id: 0 for campaign in self}

        posts_data = self.env['social.post'].search_read(
            [('utm_campaign_id', 'in', self.ids)],
            ['utm_campaign_id', 'engagement']
        )

        for datum in posts_data:
            campaign_id = datum['utm_campaign_id'][0]
            campaigns_engagement[campaign_id] += datum['engagement']

        for campaign in self:
            campaign.social_engagement = campaigns_engagement[campaign.id]

    def _compute_social_posts_count(self):
        post_data = self.env['social.post'].read_group(
            self._get_campaign_social_posts_domain(),
            ['utm_campaign_id'], ['utm_campaign_id']
        )

        mapped_data = {datum['utm_campaign_id'][0]: datum['utm_campaign_id_count'] for datum in post_data}

        for campaign in self:
            campaign.social_posts_count = mapped_data.get(campaign.id, 0)

    def action_create_new_post(self):
        action = self.env.ref('social.action_social_post').read()[0]
        action['views'] = [[False, 'form']]
        action['context'] = {
            'default_utm_campaign_id': self.id,
            'default_account_ids': self.env['social.account'].search(self._get_social_media_accounts_domain()).ids
        }
        return action

    def action_redirect_to_social_media_posts(self):
        action = self.env.ref('social.action_social_post').read()[0]
        action['domain'] = self._get_campaign_social_posts_domain()
        action['context'] = {
            "searchpanel_default_state": "posted",
            "default_utm_campaign_id": self.id
        }
        return action

    def _get_campaign_social_posts_domain(self):
        """This method will need to be overriden in social_push_notifications to filter out posts who only are push notifications"""
        return [('utm_campaign_id', 'in', self.ids)]

    def _get_social_media_accounts_domain(self):
        """This method will need to be overriden in social_push_notifications to filter out push_notifications medium"""
        return []
