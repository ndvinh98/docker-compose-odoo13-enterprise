# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from hashlib import sha1
import hmac
import random

from odoo import api, fields, models


def github_tokenize(db_secret, db_uuid):
    return hmac.new(db_secret.encode('utf-8'), db_uuid.encode('utf-8'), sha1).hexdigest()


class GithubRepository(models.Model):

    _name = 'mail.channel.github'
    _inherit = 'mail.thread'
    _description = 'Email Github Channel'

    def _default_secret(self):
        chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
        return ''.join(random.SystemRandom().choice(chars) for _ in range(20))

    name = fields.Char("Repository name", required=True, help="Complete name of the github repository. e.i.: my-username/my-public-repo")
    github_repository_id = fields.Char("Repository ID")
    channel_ids = fields.Many2many("mail.channel", string="Channels")
    secret = fields.Char("Secret", default=_default_secret)
    url_token = fields.Char("Payload URL", compute="_compute_url_token", help="URL to put as the payload target when configuring GitHub webhook")

    def _compute_url_token(self):
        db_secret = self.env['ir.config_parameter'].sudo().get_param('database.secret')
        db_uuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        baseurl = self.env['ir.config_parameter'].get_param('web.base.url')

        for repository in self:
            repository.url_token = baseurl + "/mail_github/payload/" + github_tokenize(db_secret, db_uuid)

    @api.model
    def create(self, values):
        """ We don't want the creator of the repo to be have needaction when a message_post is done. """
        return super(GithubRepository, self.with_context(mail_create_nosubscribe=True)).create(values)
