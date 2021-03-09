# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import requests
from werkzeug.urls import url_join

from odoo import http, _
from odoo.http import request


class SocialPushNotificationsController(http.Controller):
    @http.route('/social_push_notifications/fetch_push_configuration', type='json', auth='public')
    def fetch_push_configuration(self):
        """ Fetches the firebase push configuration for the current website (if any). """
        current_website = request.env['website'].get_current_website()
        if not current_website or not current_website.firebase_enable_push_notifications:
            return {}

        title = current_website.notification_request_title or _("Want to discover new versions?")
        body = current_website.notification_request_body or _("Enable push notifications to be notified about new features and events.")
        delay = current_website.notification_request_delay or 3

        if current_website.notification_request_icon:
            icon = '/web/image/website/%s/notification_request_icon/48x48' % current_website.id
        else:
            icon = '/mail/static/src/img/odoobot_transparent.png'

        if not current_website.firebase_use_own_account \
           and (not current_website.firebase_project_id or
           not current_website.firebase_web_api_key or
           not current_website.firebase_push_certificate_key or
           not current_website.firebase_sender_id):
            self._register_iap_firebase_info(current_website)

        return {
            'notification_request_title': title,
            'notification_request_body': body,
            'notification_request_delay': delay,
            'notification_request_icon': icon,
            'firebase_project_id': current_website.firebase_project_id,
            'firebase_web_api_key': current_website.firebase_web_api_key,
            'firebase_push_certificate_key': current_website.firebase_push_certificate_key,
            'firebase_sender_id': current_website.firebase_sender_id
        }

    def _register_iap_firebase_info(self, current_website):
        social_iap_endpoint = request.env['ir.config_parameter'].sudo().get_param(
            'social.social_iap_endpoint',
            request.env['social.media']._DEFAULT_SOCIAL_IAP_ENDPOINT
        )
        result = requests.get(url_join(social_iap_endpoint, 'iap/social_push_notifications/get_firebase_info'), {
            'db_uuid': request.env['ir.config_parameter'].sudo().get_param('database.uuid')
        })

        if result.status_code == 200:
            result_json = result.json()
            current_website.sudo().write({
                'firebase_project_id': result_json['firebase_project_id'],
                'firebase_web_api_key': result_json['firebase_web_api_key'],
                'firebase_push_certificate_key': result_json['firebase_push_certificate_key'],
                'firebase_sender_id': result_json['firebase_sender_id'],
            })

    @http.route('/social_push_notifications/register', type='json', auth='public', website=True)
    def register(self, token):
        """ Store the firebase token on the website visitor.
        If the visitor does not exists yet, create one and return the signed website.visitor id
        to store it in cookie.

        Will also clean the token from other visitors if necessary. """

        res = {}

        Visitor = request.env['website.visitor'].sudo()
        visitor_sudo = Visitor._get_visitor_from_request(force_create=True)
        if request.httprequest.cookies.get('visitor_uuid', '') != visitor_sudo.access_token:
            res['visitor_uuid'] = visitor_sudo.access_token

        visitor_sudo.write({'push_token': token})

        # check if other visitors already had this token
        other_visitors_sudo = Visitor.search([('push_token', '=', token), ('id', '!=', visitor_sudo.id)])
        # If yes, clean other visitors
        if other_visitors_sudo:
            other_visitors_sudo.write({'push_token': False})

        return res

    @http.route('/social_push_notifications/unregister', type='json', auth='public')
    def unregister(self, token):
        if token:
            request.env['website.visitor'].sudo().search([('push_token', '=', token)]).write({'push_token': False})
