# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class SocialAccount(models.Model):
    """ A social.account represents an actual account on the related social.media.
    Ex: A Facebook Page or a Twitter Account.

    These social.accounts will then be used to send generic social.posts to multiple social.accounts.
    They are also used to display a 'dashboard' of statistics on the 'Feed' view.

    Account statistic fields are 'computed' manually through the _compute_statistics method
    that is overridden by each actual social module implementations (social_facebook, social_twitter, ...).
    The statistics computation is run manually when visualizing the Feed. """

    _name = 'social.account'
    _description = 'Social Account'
    _inherits = {'utm.medium': 'utm_medium_id'}

    active = fields.Boolean("Active", default=True)
    media_id = fields.Many2one('social.media', string="Social Media", required=True, readonly=True,
        help="Related Social Media (Facebook, Twitter, ...).", ondelete='cascade')
    media_type = fields.Selection(related='media_id.media_type')
    stats_link = fields.Char("Stats Link", compute='_compute_stats_link',
        help="Link to the external Social Account statistics")
    image = fields.Image("Image", max_width=128, max_height=128, readonly=True)
    is_media_disconnected = fields.Boolean('Link with external Social Media is broken')

    audience = fields.Integer("Audience", readonly=True,
        help="General audience of the Social Account (Page Likes, Account Follows, ...).")
    audience_trend = fields.Float("Audience Trend", readonly=True, digits=(3, 0),
        help="Percentage of increase/decrease of the audience over a defined period.")
    engagement = fields.Integer("Engagement", readonly=True,
        help="Number of people engagements with your posts (Likes, Comments, ...).")
    engagement_trend = fields.Float("Engagement Trend", readonly=True, digits=(3, 0),
        help="Percentage of increase/decrease of the engagement over a defined period.")
    stories = fields.Integer("Stories", readonly=True,
        help="Number of stories created from your posts (Shares, Re-tweets, ...).")
    stories_trend = fields.Float("Stories Trend", readonly=True, digits=(3, 0),
        help="Percentage of increase/decrease of the stories over a defined period.")
    has_trends = fields.Boolean("Has Trends?",
        help="Defines whether this account has statistics tends or not.")
    has_account_stats = fields.Boolean("Has Account Stats", default=True, required=True,
        help="""Defines whether this account has Audience/Engagements/Stories stats.
        Account with stats are displayed on the dashboard.""")
    utm_medium_id = fields.Many2one('utm.medium', string="UTM Medium", required=True, help="Every time an account is created, a utm.medium is also created and linked to the account")

    def _compute_statistics(self):
        """ Every social module should override this method if it 'has_account_stats'.
        As the values depend on third party data, it's compute triggered manually that stores the data on the
        various stats fields (audience, engagement, stories) as well as related trends fields (if 'has_trends'). """
        pass

    def _compute_stats_link(self):
        """ Every social module should override this method.
        The 'stats_link' is an external link to the actual social.media statistics for this account.
        Ex: https://www.facebook.com/Odoo-Social-557894618055440/insights """
        pass

    def name_get(self):
        """ ex: [Facebook] Odoo Social, [Twitter] Mitchell Admin, ... """
        return [(account.id, '[%s] %s' % (account.media_id.name, account.name if account.name else '')) for account in self]

    @api.model_create_multi
    def create(self, vals_list):
        res = super(SocialAccount, self).create(vals_list)
        res._compute_statistics()
        return res

    @api.model
    def refresh_statistics(self):
        """ Will re-compute the statistics of all active accounts. """
        all_accounts = self.env['social.account'].search([('has_account_stats', '=', True)]).sudo()
        all_accounts._compute_statistics()
        return [{
            'id': account.id,
            'name': account.name,
            'is_media_disconnected': account.is_media_disconnected,
            'audience': account.audience,
            'audience_trend': account.audience_trend,
            'engagement': account.engagement,
            'engagement_trend': account.engagement_trend,
            'stories': account.stories,
            'stories_trend': account.stories_trend,
            'has_trends': account.has_trends,
            'media_id': [account.media_id.id],
            'stats_link': account.stats_link
        } for account in all_accounts]
