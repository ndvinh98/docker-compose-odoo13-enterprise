# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import request
from odoo.addons.website_helpdesk.controllers.main import WebsiteHelpdesk


class WebsiteHelpdesk(WebsiteHelpdesk):

    def get_helpdesk_team_data(self, team, search=None):
        result = super(WebsiteHelpdesk, self).get_helpdesk_team_data(team, search)
        result['channel'] = team.elearning_id
        domain = []
        if search:
            domain += [('name', 'ilike', search)]
        if team.elearning_id:
            domain += [('channel_id', '=', result['channel'].id)]
            slides = request.env['slide.slide'].search(domain)
            result['slides'] = slides[:7]
            result['slides_limit'] = len(slides)
            result['search'] = search
        return result
