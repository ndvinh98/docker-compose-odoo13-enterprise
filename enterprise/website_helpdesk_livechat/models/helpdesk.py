# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
from odoo import api, fields, models, _


class HelpdeskTeam(models.Model):
    _inherit = ['helpdesk.team']

    feature_livechat_channel_id = fields.Many2one('im_livechat.channel', string='Live Chat Channel', compute='_get_livechat_channel', store=True)
    feature_livechat_web_page = fields.Char(related='feature_livechat_channel_id.web_page', string='Live Chat Test Page', readonly=True)
    is_canned_response = fields.Boolean()

    @api.depends('use_website_helpdesk_livechat')
    def _get_livechat_channel(self):
        LiveChat = self.env['im_livechat.channel']
        for team in self:
            if team.name and team.use_website_helpdesk_livechat:
                channel = LiveChat.search([('name', '=', team.name)])
                if not channel:
                    if team.member_ids:
                        channel = LiveChat.create({'name': team.name, 'user_ids': [(6, _, team.member_ids.ids)]})
                    else:
                        channel = LiveChat.create({'name': team.name})
                team.feature_livechat_channel_id = channel
            else:
                team.feature_livechat_channel_id = False


class MailChannel(models.Model):
    _inherit = 'mail.channel'

    # ------------------------------------------------------
    #  Commands
    # ------------------------------------------------------

    def _define_command_helpdesk(self):
        return {'help': _("Create a new helpdesk ticket")}

    def _execute_command_helpdesk(self, **kwargs):
        key = kwargs.get('body').split()
        partner = self.env.user.partner_id
        msg = _('Something is missing or wrong in command')
        channel_partners = self.env['mail.channel.partner'].search([('partner_id', '!=', partner.id), ('channel_id', '=', self.id)], limit=1)
        if key[0].lower() == '/helpdesk':
            if len(key) == 1:
                if self.channel_type == 'channel':
                    msg = _("You are in channel <b>#%s</b>.") % self.name
                    if self.public == 'private':
                        msg += _(" This channel is private. People must be invited to join it.")
                else:
                    msg = _("You are in a private conversation with <b>@%s</b>.") % channel_partners.partner_id.name
                msg += _("""<br><br>
                    You can create a new ticket by typing <b>/helpdesk "ticket title"</b>.<br>
                    You can search ticket by typing <b>/helpdesk_search "Keywords1 Keywords2 etc"</b><br>
                    """)
            else:
                list_value = key[1:]
                description = ''
                for message in self.channel_message_ids.sorted(key=lambda r: r.id):
                    name = message.author_id.name or 'Anonymous'
                    description += '%s: ' % name + '%s\n' % re.sub('<[^>]*>', '', message.body)
                team = self.env['helpdesk.team'].search([('member_ids', 'in', self._uid)], order='sequence', limit=1)
                team_id = team.id if team else False
                helpdesk_ticket = self.env['helpdesk.ticket'].create({
                    'name': ' '.join(list_value),
                    'user_id': self.env.user.id,
                    'description': description,
                    'partner_id': channel_partners.partner_id.id,
                    'team_id': team_id,
                })
                link_ticket = '<a href="#" data-oe-id='+str(helpdesk_ticket.id)+' data-oe-model="helpdesk.ticket">'+helpdesk_ticket.name+'</a>'
                msg = _("Created a new ticket and request: %s") % link_ticket
        return self._send_transient_message(partner, msg)

    def _define_command_helpdesk_search(self):
        return {'help': _("Search for a helpdesk ticket")}

    def _execute_command_helpdesk_search(self, **kwargs):
        key = kwargs.get('body').split()
        partner = self.env.user.partner_id
        msg = _('Something is missing or wrong in command')
        if key[0].lower() == '/helpdesk_search':
            if len(key) == 1:
                msg = _('You can search ticket by typing <b>/helpdesk_search "Keywords1 Keywords2 etc"</b><br>')
            else:
                list_value = key[1:]
                Keywords = re.findall('\w+', ' '.join(list_value))
                HelpdeskTag = self.env['helpdesk.tag']
                for Keyword in Keywords:
                    HelpdeskTag |= HelpdeskTag.search([('name', 'ilike', Keyword)])
                tickets = self.env['helpdesk.ticket'].search([('tag_ids', 'in', HelpdeskTag.ids)], limit=10)
                if not tickets:
                    for Keyword in Keywords:
                        tickets |= self.env['helpdesk.ticket'].search([('name', 'ilike', Keyword)], order="id desc", limit=10)
                        if len(tickets) > 10:
                            break
                if tickets:
                    link_tickets = ['<br/><a href="#" data-oe-id='+str(ticket.id)+' data-oe-model="helpdesk.ticket">#'+ticket.name+'</a>' for ticket in tickets]
                    msg = _('We found some matched ticket(s) related to the search query: %s') % ''.join(link_tickets)
                else:
                    msg = _('No tickets found related to the search query. <br> make sure to use the right format: (/helpdesk_search Keyword1 Keyword2 etc...)')
        return self._send_transient_message(partner, msg)
