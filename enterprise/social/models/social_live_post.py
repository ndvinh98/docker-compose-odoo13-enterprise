# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SocialLivePost(models.Model):
    """ A social 'live' post, as opposed to a social.post, represents a post that is
    actually on a social.account instance.

    Basically, a social.post that is posted on 4 social.accounts will create 4 instances
    of the social.live.post. """

    _name = 'social.live.post'
    _description = 'Social Live Post'

    post_id = fields.Many2one('social.post', string="Social Post", required=True, readonly=True, ondelete="cascade")
    account_id = fields.Many2one('social.account', string="Social Account", required=True, readonly=True, ondelete="cascade")
    failure_reason = fields.Text('Failure Reason', readonly=True,
        help="""The reason why a post is not successfully posted on the Social Media (eg: connection error, duplicated post, ...).""")
    state = fields.Selection([
        ('ready', 'Ready'),
        ('posting', 'Posting'),
        ('posted', 'Posted'),
        ('failed', 'Failed')],
        string='Status', default='ready', required=True, readonly=True,
        help="""Most social.live.posts directly go from Ready to Posted/Failed since they result of a single call to the third party API.
        A 'Posting' state is also available for those that are sent through batching (like push notifications).""")
    engagement = fields.Integer("Engagement", help="Number of people engagements with the post (Likes, comments...)")

    def name_get(self):
        """ ex: [Facebook] Odoo Social: posted, [Twitter] Mitchell Admin: failed, ... """
        state_description_values = {elem[0]: elem[1] for elem in self._fields['state']._description_selection(self.env)}
        return [(live_post.id, '%s: %s' % (live_post.account_id.display_name, state_description_values.get(live_post.state))) for live_post in self]

    @api.model_create_multi
    def create(self, vals_list):
        res = super(SocialLivePost, self).create(vals_list)
        res.mapped('post_id')._check_post_completion()
        return res

    def write(self, vals):
        res = super(SocialLivePost, self).write(vals)
        if vals.get('state'):
            self.mapped('post_id')._check_post_completion()
        return res

    def action_retry_post(self):
        self._post()

    @api.model
    def refresh_statistics(self):
        self.env['social.live.post']._refresh_statistics()

    def _refresh_statistics(self):
        """ Every social module should override this method.

        This is the method responsible for fetching the post data per social media.

        It will be called manually every time we need to refresh the social.stream data:
            - social.stream creation/edition
            - 'Feed' kanban loading
            - 'Refresh' button on 'Feed' kanban
            - ...
        """
        pass

    def _post(self):
        """ Every social module should override this method.
        This will make the actual post on the related social.account through the third party API """
        pass

    def _get_utm_values(self):
        self.ensure_one()

        post_id = self.post_id
        return {
            'campaign_id': post_id.utm_campaign_id.id,
            'medium_id': self.account_id.utm_medium_id.id,
            'source_id': post_id.utm_source_id.id
        }
