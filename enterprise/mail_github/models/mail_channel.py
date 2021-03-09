# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class Channel(models.Model):

    _inherit = "mail.channel"

    github_repo_ids = fields.Many2many("mail.channel.github", string="Repositories", help="The Github repositories the channel will follow")
    github_enabled = fields.Boolean("Enable listening to Github repositories")
