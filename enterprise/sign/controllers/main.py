# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import io
import logging
import mimetypes
import re
import werkzeug

from PyPDF2 import PdfFileReader

from odoo import http, _
from odoo.http import request
from odoo.addons.web.controllers.main import content_disposition
from odoo.addons.iap.models.iap import InsufficientCreditError

_logger = logging.getLogger()


class Sign(http.Controller):

    def get_document_qweb_context(self, id, token):
        sign_request = http.request.env['sign.request'].sudo().browse(id).exists()
        if not sign_request:
            if token:
                return http.request.render('sign.deleted_sign_request')
            else:
                return http.request.not_found()

        current_request_item = None
        if token:
            current_request_item = sign_request.request_item_ids.filtered(lambda r: r.access_token == token)
            if not current_request_item and sign_request.access_token != token and http.request.env.user.id != sign_request.create_uid.id:
                return http.request.render('sign.deleted_sign_request')
        elif sign_request.create_uid.id != http.request.env.user.id:
            return http.request.not_found()

        sign_item_types = http.request.env['sign.item.type'].sudo().search_read([])
        if current_request_item:
            for item_type in sign_item_types:
                if item_type['auto_field']:
                    fields = item_type['auto_field'].split('.')
                    auto_field = current_request_item.partner_id
                    for field in fields:
                        if auto_field and field in auto_field:
                            auto_field = auto_field[field]
                        else:
                            auto_field = ""
                            break
                    item_type['auto_field'] = auto_field

            if current_request_item.state != 'completed':
                """ When signer attempts to sign the request again,
                its localisation should be reset.
                We prefer having no/approximative (from geoip) information
                than having wrong old information (from geoip/browser)
                on the signer localisation.
                """
                current_request_item.write({
                    'latitude': request.session['geoip'].get('latitude') if 'geoip' in request.session else 0,
                    'longitude': request.session['geoip'].get('longitude') if 'geoip' in request.session else 0,
                })

        sr_values = http.request.env['sign.request.item.value'].sudo().search([('sign_request_id', '=', sign_request.id)])
        item_values = {}
        for value in sr_values:
            item_values[value.sign_item_id.id] = value.value

        Log = request.env['sign.log'].sudo()
        vals = Log._prepare_vals_from_item(current_request_item) if current_request_item else Log._prepare_vals_from_request(sign_request)
        vals['action'] = 'open'
        vals = Log._update_vals_with_http_request(vals)
        Log.create(vals)

        return {
            'sign_request': sign_request,
            'current_request_item': current_request_item,
            'token': token,
            'nbComments': len(sign_request.message_ids.filtered(lambda m: m.message_type == 'comment')),
            'isPDF': (sign_request.template_id.attachment_id.mimetype.find('pdf') > -1),
            'webimage': re.match('image.*(gif|jpe|jpg|png)', sign_request.template_id.attachment_id.mimetype),
            'hasItems': len(sign_request.template_id.sign_item_ids) > 0,
            'sign_items': sign_request.template_id.sign_item_ids,
            'item_values': item_values,
            'role': current_request_item.role_id.id if current_request_item else 0,
            'readonly': not (current_request_item and current_request_item.state == 'sent'),
            'sign_item_types': sign_item_types,
            'sign_item_select_options': sign_request.template_id.sign_item_ids.mapped('option_ids'),
        }

    # -------------
    #  HTTP Routes
    # -------------
    @http.route(["/sign/document/<int:id>"], type='http', auth='user')
    def sign_document_user(self, id, **post):
        return self.sign_document_public(id, None)

    @http.route(["/sign/document/mail/<int:id>/<token>"], type='http', auth='public')
    def sign_document_from_mail(self, id, token):
        sign_request = request.env['sign.request'].sudo().browse(id)
        if not sign_request:
            return http.request.render('sign.deleted_sign_request')
        current_request_item = sign_request.request_item_ids.filtered(lambda r: r.access_token == token)
        current_request_item.access_via_link = True
        return werkzeug.redirect('/sign/document/%s/%s' % (id, token))

    @http.route(["/sign/document/<int:id>/<token>"], type='http', auth='public')
    def sign_document_public(self, id, token, **post):
        document_context = self.get_document_qweb_context(id, token)
        if not isinstance(document_context, dict):
            return document_context

        return http.request.render('sign.doc_sign', document_context)

    @http.route(['/sign/download/<int:id>/<token>/<download_type>'], type='http', auth='public')
    def download_document(self, id, token, download_type, **post):
        sign_request = http.request.env['sign.request'].sudo().browse(id).exists()
        if not sign_request or sign_request.access_token != token:
            return http.request.not_found()

        document = None
        if download_type == "log":
            report_action = http.request.env.ref('sign.action_sign_request_print_logs').sudo()
            pdf_content, __ = report_action.render_qweb_pdf(sign_request.id)
            pdfhttpheaders = [
                ('Content-Type', 'application/pdf'),
                ('Content-Length', len(pdf_content)),
                ('Content-Disposition', 'attachment; filename=' + "Activity Logs.pdf;")
            ]
            return request.make_response(pdf_content, headers=pdfhttpheaders)
        elif download_type == "origin":
            document = sign_request.template_id.attachment_id.datas
        elif download_type == "completed":
            document = sign_request.completed_document
            if not document: # if the document is completed but the document is encrypted
                return http.redirect_with_hash('/sign/password/%(request_id)s/%(access_token)s' % {'request_id': id, 'access_token': token})

        if not document:
            # Shouldn't it fall back on 'origin' download type?
            return http.redirect_with_hash("/sign/document/%(request_id)s/%(access_token)s" % {'request_id': id, 'access_token': token})

        # Avoid to have file named "test file.pdf (V2)" impossible to open on Windows.
        # This line produce: test file (V2).pdf
        extension = '.' + sign_request.template_id.attachment_id.mimetype.replace('application/', '').replace(';base64', '')
        filename = sign_request.reference.replace(extension, '') + extension

        return http.request.make_response(
            base64.b64decode(document),
            headers = [
                ('Content-Type', mimetypes.guess_type(filename)[0] or 'application/octet-stream'),
                ('Content-Disposition', content_disposition(filename))
            ]
        )

    @http.route(['/sign/<link>'], type='http', auth='public')
    def share_link(self, link, **post):
        template = http.request.env['sign.template'].sudo().search([('share_link', '=', link)], limit=1)
        if not template:
            return http.request.not_found()

        sign_request = http.request.env['sign.request'].with_user(template.create_uid).create({
            'template_id': template.id,
            'reference': "%(template_name)s-public" % {'template_name': template.attachment_id.name},
            'favorited_ids': [(4, template.create_uid.id)],
        })

        request_item = http.request.env['sign.request.item'].sudo().create({'sign_request_id': sign_request.id, 'role_id': template.sign_item_ids.mapped('responsible_id').id})
        sign_request.action_sent()

        return http.redirect_with_hash('/sign/document/%(request_id)s/%(access_token)s' % {'request_id': sign_request.id, 'access_token': request_item.access_token})

    @http.route(['/sign/password/<int:sign_request_id>/<token>'], type='http', auth='public')
    def check_password_page(self, sign_request_id, token, **post):
        values = http.request.params.copy()
        request_item = http.request.env['sign.request.item'].sudo().search([
            ('sign_request_id', '=', sign_request_id),
            ('state', '=', 'completed'),
            ('sign_request_id.access_token', '=', token)], limit=1)
        if not request_item:
            return http.request.not_found()

        if 'password' not in http.request.params:
            return http.request.render('sign.encrypted_ask_password')

        password = http.request.params['password']
        template_id = request_item.sign_request_id.template_id

        old_pdf = PdfFileReader(io.BytesIO(base64.b64decode(template_id.attachment_id.datas)), strict=False, overwriteWarnings=False)
        if old_pdf.isEncrypted and not old_pdf.decrypt(password):
            values['error'] = _("Wrong password")
            return http.request.render('sign.encrypted_ask_password', values)

        request_item.sign_request_id.generate_completed_document(password)
        request_item.sign_request_id.send_completed_document()
        return http.redirect_with_hash('/sign/document/%(request_id)s/%(access_token)s' % {'request_id': sign_request_id, 'access_token': token})

    # -------------
    #  JSON Routes
    # -------------
    @http.route(["/sign/get_document/<int:id>/<token>"], type='json', auth='user')
    def get_document(self, id, token):
        return http.Response(template='sign._doc_sign', qcontext=self.get_document_qweb_context(id, token)).render()

    @http.route(['/sign/new_partners'], type='json', auth='user')
    def new_partners(self, partners=[]):
        ResPartner = http.request.env['res.partner']
        pIDs = []
        for p in partners:
            existing = ResPartner.search([('email', '=', p[1])], limit=1)
            pIDs.append(existing.id if existing else ResPartner.create({'name': p[0], 'email': p[1]}).id)
        return pIDs

    @http.route(['/sign/get_signature/<int:request_id>/<item_access_token>'], type='json', auth='public')
    def sign_get_user_signature(self, request_id, item_access_token, signature_type='signature'):
        sign_request_item = http.request.env['sign.request.item'].sudo().search([
            ('sign_request_id', '=', request_id),
            ('access_token', '=', item_access_token)
        ])
        if not sign_request_item:
            return False

        sign_request_user = http.request.env['res.users'].sudo().search([('partner_id', '=', sign_request_item.partner_id.id)], limit=1)
        if sign_request_user and signature_type == 'signature':
            return sign_request_user.sign_signature
        elif sign_request_user and signature_type == 'initial':
            return sign_request_user.sign_initials
        return False

    @http.route(['/sign/send_public/<int:id>/<token>'], type='json', auth='public')
    def make_public_user(self, id, token, name=None, mail=None):
        sign_request = http.request.env['sign.request'].sudo().search([('id', '=', id), ('access_token', '=', token)])
        if not sign_request or len(sign_request.request_item_ids) != 1 or sign_request.request_item_ids.partner_id:
            return False

        ResPartner = http.request.env['res.partner'].sudo()
        partner = ResPartner.search([('email', '=', mail)], limit=1)
        if not partner:
            partner = ResPartner.create({'name': name, 'email': mail})
        sign_request.request_item_ids[0].write({'partner_id': partner.id})

    @http.route([
        '/sign/send-sms/<int:id>/<token>/<phone_number>',
        ], type='json', auth='public')
    def send_sms(self, id, token, phone_number):
        request_item = http.request.env['sign.request.item'].sudo().search([('sign_request_id', '=', id), ('access_token', '=', token), ('state', '=', 'sent')], limit=1)
        if not request_item:
            return False
        if request_item.role_id and request_item.role_id.sms_authentification:
            request_item.sms_number = phone_number
            try:
                request_item._send_sms()
            except InsufficientCreditError:
                _logger.warning('Unable to send SMS: no more credits')
                http.request.env['mail.activity'].sudo().create({
                    'activity_type_id': http.request.env.ref('mail.mail_activity_data_todo').id,
                    'note': _("%s couldn't sign the document due to an insufficient credit error." % (request_item.partner_id.display_name)),
                    'user_id': request_item.sign_request_id.create_uid.id,
                    'res_id': request_item.sign_request_id.id,
                    'res_model_id': http.request.env['ir.model'].sudo().search([('model', '=', request_item.sign_request_id._name)], limit=1).id,
                })
                return False
        return True

    @http.route([
        '/sign/sign/<int:id>/<token>',
        '/sign/sign/<int:id>/<token>/<sms_token>'
        ], type='json', auth='public')
    def sign(self, id, token, sms_token=False, signature=None):
        request_item = http.request.env['sign.request.item'].sudo().search([('sign_request_id', '=', id), ('access_token', '=', token), ('state', '=', 'sent')], limit=1)
        if not request_item:
            return False
        if request_item.role_id and request_item.role_id.sms_authentification:
            if not sms_token:
                return {
                    'sms': True
                }
            if sms_token != request_item.sms_token:
                return False
            if sms_token == request_item.sms_token:
                request_item.sign_request_id._message_log(body=_('%s validated the signature by SMS with the phone number %s.') % (request_item.partner_id.display_name, request_item.sms_number))

        if not request_item.sign(signature):
            return False

        # mark signature as done in next activity
        user_ids = http.request.env['res.users'].search([('partner_id', '=', request_item.partner_id.id)])
        sign_users = user_ids.filtered(lambda u: u.has_group('sign.group_sign_user'))
        for sign_user in sign_users:
            request_item.sign_request_id.activity_feedback(['mail.mail_activity_data_todo'], user_id=sign_user.id)

        Log = request.env['sign.log'].sudo()
        vals = Log._prepare_vals_from_item(request_item)
        vals['action'] = 'sign'
        vals['token'] = token
        vals = Log._update_vals_with_http_request(vals)
        Log.create(vals)
        request_item.action_completed()
        return True

    @http.route(['/sign/password/<int:sign_request_id>'], type='json', auth='public')
    def check_password(self, sign_request_id, password=None):
        request_item = http.request.env['sign.request.item'].sudo().search([
            ('sign_request_id', '=', sign_request_id),
            ('state', '=', 'completed')], limit=1)
        if not request_item:
            return False
        template_id = request_item.sign_request_id.template_id

        old_pdf = PdfFileReader(io.BytesIO(base64.b64decode(template_id.attachment_id.datas)), strict=False, overwriteWarnings=False)
        if old_pdf.isEncrypted and not old_pdf.decrypt(password):
            return False

        # if the password is correct, we generate document and send it
        request_item.sign_request_id.generate_completed_document(password)
        request_item.sign_request_id.send_completed_document()
        return True

    @http.route(['/sign/encrypted/<int:sign_request_id>'], type='json', auth='public')
    def check_encrypted(self, sign_request_id):
        request_item = http.request.env['sign.request.item'].sudo().search([('sign_request_id', '=', sign_request_id)], limit=1)
        if not request_item:
            return False

        # we verify that the document is completed by all signor
        if request_item.sign_request_id.nb_total != request_item.sign_request_id.nb_closed:
            return False
        template_id = request_item.sign_request_id.template_id

        old_pdf = PdfFileReader(io.BytesIO(base64.b64decode(template_id.attachment_id.datas)), strict=False, overwriteWarnings=False)
        return True if old_pdf.isEncrypted else False

    @http.route(['/sign/save_location/<int:id>/<token>'], type='json', auth='public')
    def save_location(self, id, token, latitude=0, longitude=0):
        sign_request_item = http.request.env['sign.request.item'].sudo().search([('sign_request_id', '=', id), ('access_token', '=', token)], limit=1)
        sign_request_item.write({'latitude': latitude, 'longitude': longitude})
