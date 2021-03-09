# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime

from werkzeug.exceptions import NotFound

from odoo import http
from odoo.http import request


class WebsiteHelpdesk(http.Controller):

    @http.route(['/helpdesk/rating'], type='http', auth="public", website=True)
    def index(self, **kw):
        teams = request.env['helpdesk.team'].sudo().search([('use_rating', '=', True), ('portal_show_rating', '=', True)])
        values = {'teams': teams}
        return request.render('helpdesk.index', values)

    @http.route(['/helpdesk/rating/<model("helpdesk.team"):team>'], type='http', auth="public", website=True)
    def page(self, team, project_id=None, **kw):
        user = request.env.user
        # to avoid giving any access rights on helpdesk team to the public user, let's use sudo
        # and check if the user should be able to view the team (team managers only if it's not published or has no rating)
        if not (team.use_rating and team.portal_show_rating) and not user.has_group('helpdesk.group_helpdesk_manager'):
            raise NotFound()
        tickets = request.env['helpdesk.ticket'].sudo().search([('team_id', '=', team.id)])
        domain = [
            ('res_model', '=', 'helpdesk.ticket'), ('res_id', 'in', tickets.ids),
            ('consumed', '=', True), ('rating', '>=', 1),
        ]
        ratings = request.env['rating.rating'].search(domain, order="id desc", limit=100)

        yesterday = (datetime.date.today()-datetime.timedelta(days=-1)).strftime('%Y-%m-%d 23:59:59')
        stats = {}
        for x in (7, 30, 90):
            todate = (datetime.date.today()-datetime.timedelta(days=x)).strftime('%Y-%m-%d 00:00:00')
            domdate = domain + [('create_date', '<=', yesterday), ('create_date', '>=', todate)]
            stats[x] = {1: 0, 5: 0, 10: 0}
            rating_stats = request.env['rating.rating'].read_group(domdate, [], ['rating'])
            total = sum(st['rating_count'] for st in rating_stats)
            for rate in rating_stats:
                stats[x][rate['rating']] = (rate['rating_count'] * 100) / total
        values = {
            'team': team,
            'ratings': ratings,
            'stats': stats,
        }
        return request.render('helpdesk.team_rating_page', values)
