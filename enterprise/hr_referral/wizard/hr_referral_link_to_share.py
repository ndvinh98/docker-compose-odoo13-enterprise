# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import uuid

from odoo import api, fields, models


class HrReferralLinkToShare(models.TransientModel):
    _name = 'hr.referral.link.to.share'
    _description = 'Referral Link To Share'

    @api.model
    def default_get(self, default_fields):
        res = super().default_get(default_fields)
        if 'job_id' not in res:
            res['job_id'] = self.env.context.get('active_id')
        return res

    job_id = fields.Many2one('hr.job')
    channel = fields.Selection([
        ('direct', 'Link'),
        ('facebook', 'Facebook'),
        ('twitter', 'Twitter'),
        ('linkedin', 'Linkedin')], default='direct')
    url = fields.Char(readonly=True, compute='_compute_url', compute_sudo=True)

    @api.depends('channel')
    def _compute_url(self):
        self.ensure_one()

        if not self.env.user.utm_source_id:
            utm_name = ('%s-%s') % (self.env.user.name, str(uuid.uuid4())[:6])
            self.env.user.utm_source_id = self.env['utm.source'].create({'name': utm_name}).id

        if self.job_id and not self.job_id.utm_campaign_id:
            self.job_id.utm_campaign_id = self.env['utm.campaign'].create({'name': self.job_id.name}).id

        link_tracker = self.env['link.tracker'].create({
            'url': self.get_base_url() + (self.job_id.website_url or '/jobs'),
            'campaign_id': self.job_id.utm_campaign_id.id,
            'source_id': self.env.user.utm_source_id.id,
            'medium_id': self.env.ref('utm.utm_medium_%s' % self.channel).id
        })
        if self.channel == 'direct':
            self.url = link_tracker.short_url
        elif self.channel == 'facebook':
            self.url = 'https://www.facebook.com/sharer/sharer.php?u=%s' % link_tracker.short_url
        elif self.channel == 'twitter':
            self.url = 'https://twitter.com/intent/tweet?tw_p=tweetbutton&text=Amazing job offer for %s! Check it live: %s' % (self.job_id.name, link_tracker.short_url)
        elif self.channel == 'linkedin':
            self.url = 'https://www.linkedin.com/shareArticle?mini=true&url=%s' % link_tracker.short_url
