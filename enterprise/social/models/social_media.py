# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SocialMedia(models.Model):
    """ A social.media represents the actual Media, ex: Facebook, Twitter, etc...
    As opposed to social.account that represents an existing account on this media.
    Ex: Odoo Social Facebook Page, Mitchell Admin Twitter Account, ...

    The social.media is used to store global media configuration (API keys, ...).
    It's also used to install the modules related to that social media (social_facebook, social_twitter, ...). """

    _name = 'social.media'
    _description = 'Social Media'
    _inherit = ['mail.thread']

    _DEFAULT_SOCIAL_IAP_ENDPOINT = 'https://iap-services.odoo.com'

    name = fields.Char('Name', readonly=True, required=True, translate=True)
    description = fields.Char('Description', readonly=True)
    image = fields.Binary('Image', readonly=True)
    media_type = fields.Selection([], readonly=True,
        help="Used to make comparisons when we need to restrict some features to a specific media ('facebook', 'twitter', ...).")
    account_ids = fields.One2many('social.account', 'media_id', string="Social Accounts")
    accounts_count = fields.Integer('# Accounts', compute='_compute_accounts_count')
    has_streams = fields.Boolean('Streams Enabled', default=True, readonly=True, required=True,
        help="Controls if social streams are handled on this social media.")
    can_link_accounts = fields.Boolean('Can link accounts ?', default=True, readonly=True, required=True,
        help="Controls if we can link accounts or not.")
    stream_type_ids = fields.One2many('social.stream.type', 'media_id', string="Stream Types")

    def _compute_accounts_count(self):
        for media in self:
            media.accounts_count = len(media.account_ids)

    def action_add_account(self):
        """ Every social module should override this method.
        Usually redirects to the social media links that allows accounts to be read by our app. """
        pass
