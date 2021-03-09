# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from werkzeug.urls import url_join

from odoo import _, fields, models
from odoo.addons.iap import jsonrpc
from odoo.exceptions import UserError

MISSING_FIREBASE_LIB_ERROR_MESSAGE = """Push Notifications require the `firebase_admin` Python library (version >=2.17.0).
    You need to install it on your system to be able to use this module."""

_logger = logging.getLogger(__name__)
try:
    import firebase_admin
    from firebase_admin import messaging
    from firebase_admin import credentials
except ImportError:
    _logger.warning(MISSING_FIREBASE_LIB_ERROR_MESSAGE)
    firebase_admin = None


class SocialAccountPushNotifications(models.Model):
    _inherit = 'social.account'

    website_id = fields.Many2one('website', string="Website",
                                 help="This firebase configuration will only be used for the specified website", ondelete='cascade')
    firebase_use_own_account = fields.Boolean('Use your own Firebase account', related='website_id.firebase_use_own_account')
    firebase_project_id = fields.Char('Firebase Project ID', related='website_id.firebase_project_id')
    firebase_web_api_key = fields.Char('Firebase Web API Key', related='website_id.firebase_web_api_key')
    firebase_push_certificate_key = fields.Char('Firebase Push Certificate Key', related='website_id.firebase_push_certificate_key')
    firebase_sender_id = fields.Char('Firebase Sender ID', related='website_id.firebase_sender_id')
    firebase_admin_key_file = fields.Binary('Firebase Admin Key File', related='website_id.firebase_admin_key_file')

    notification_request_title = fields.Char('Notification Request Title', related='website_id.notification_request_title')
    notification_request_body = fields.Text('Notification Request Text', related='website_id.notification_request_body')
    notification_request_delay = fields.Integer('Notification Request Delay (seconds)', related='website_id.notification_request_delay')
    notification_request_icon = fields.Binary("Notification Request Icon", related='website_id.notification_request_icon')

    _sql_constraints = [('website_unique', 'unique(website_id)', 'There is already a configuration for this website.')]

    def unlink(self):
        if not self.env.user.has_group('base.group_system') and any(account.website_id for account in self):
            raise UserError(_("You can't delete a Push Notification account."))
        return super(SocialAccountPushNotifications, self).unlink()

    def _init_firebase_app(self):
        """ Initialize the firebase library before usage.
        There is no actual way to tell if the app is already initialized or not.
        And we don't want to initialize it when the server starts because it could never be used.
        So we have to check for the ValueError that triggers if the app if already initialized and ignore it. """
        self.ensure_one()

        self._check_firebase_version()
        firebase_admin_key_file_attachment = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', self.website_id._name),
            ('res_field', '=', 'firebase_admin_key_file'),
            ('res_id', '=', self.website_id.id)
        ])
        if not firebase_admin_key_file_attachment:
            raise UserError(_("Firebase Admin Key File is missing from the configuration."))

        firebase_credentials = credentials.Certificate(
            firebase_admin_key_file_attachment._full_path(firebase_admin_key_file_attachment.store_fname)
        )
        try:
            firebase_admin.initialize_app(firebase_credentials)
        except ValueError:
            # app already initialized
            pass

    def _firebase_send_message(self, data, visitors):
        if self.firebase_use_own_account:
            self._firebase_send_message_from_configuration(data, visitors)
        else:
            self._firebase_send_message_from_iap(data, visitors)

    def _firebase_send_message_from_configuration(self, data, visitors):
        """ Sends messages by batch of 100 (max limit from firebase).
        Returns a tuple containing:
        - The matched website.visitors (search_read records).
        - A list of firebase_admin.messaging.BatchResponse to be handled by the caller. """
        if not visitors:
            return [], []

        self._init_firebase_app()
        batch_size = 100
        results = []

        tokens = visitors.mapped('push_token')
        for i in range(int((len(tokens) / batch_size)) + 1):
            tokens_batch = tokens[(i * batch_size):((i + 1) * batch_size)]
            firebase_message = messaging.MulticastMessage(
                data=data,
                tokens=tokens_batch
            )
            results.append(messaging.send_multicast(firebase_message))

        return tokens, results

    def _firebase_send_message_from_iap(self, data, visitors):
        social_iap_endpoint = self.env['ir.config_parameter'].sudo().get_param(
            'social.social_iap_endpoint',
            self.env['social.media']._DEFAULT_SOCIAL_IAP_ENDPOINT
        )
        batch_size = 100

        tokens = visitors.mapped('push_token')
        data.update({'db_uuid': self.env['ir.config_parameter'].sudo().get_param('database.uuid')})
        for i in range(int((len(visitors) / batch_size)) + 1):
            tokens_batch = tokens[(i * batch_size):((i + 1) * batch_size)]
            batch_data = dict(data)
            batch_data['tokens'] = tokens_batch
            jsonrpc(url_join(social_iap_endpoint, '/iap/social_push_notifications/firebase_send_message'), params=batch_data)

        return []

    def _check_firebase_version(self):
        """ Utility method to check that the installed firebase version has needed features. """
        version_compliant = firebase_admin and messaging and credentials \
            and hasattr(firebase_admin, 'initialize_app') \
            and hasattr(messaging, 'send')

        if not version_compliant:
            raise UserError(_(MISSING_FIREBASE_LIB_ERROR_MESSAGE))
