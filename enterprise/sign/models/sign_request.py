# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import io
import os
import time
import uuid

from PyPDF2 import PdfFileReader, PdfFileWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.rl_config import TTFSearchPath
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase.pdfmetrics import stringWidth
from werkzeug.urls import url_join
from random import randint

from odoo import api, fields, models, http, _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, formataddr, config, get_lang
from odoo.exceptions import UserError

TTFSearchPath.append(os.path.join(config["root_path"], "..", "addons", "web", "static", "src", "fonts", "sign"))


def _fix_image_transparency(image):
    """ Modify image transparency to minimize issue of grey bar artefact.

    When an image has a transparent pixel zone next to white pixel zone on a
    white background, this may cause on some renderer grey line artefacts at
    the edge between white and transparent.

    This method sets transparent pixel to white transparent pixel which solves
    the issue for the most probable case. With this the issue happen for a
    black zone on black background but this is less likely to happen.
    """
    pixels = image.load()
    for x in range(image.size[0]):
        for y in range(image.size[1]):
            if pixels[x, y] == (0, 0, 0, 0):
                pixels[x, y] = (255, 255, 255, 0)

class SignRequest(models.Model):
    _name = "sign.request"
    _description = "Signature Request"
    _rec_name = 'reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    def _default_access_token(self):
        return str(uuid.uuid4())

    def _expand_states(self, states, domain, order):
        return [key for key, val in type(self).state.selection]

    template_id = fields.Many2one('sign.template', string="Template", required=True)
    reference = fields.Char(required=True, string="Document Name", help="This is how the document will be named in the mail")

    access_token = fields.Char('Security Token', required=True, default=_default_access_token, readonly=True)

    request_item_ids = fields.One2many('sign.request.item', 'sign_request_id', string="Signers")
    state = fields.Selection([
        ("sent", "Sent"),
        ("signed", "Fully Signed"),
        ("canceled", "Canceled")
    ], default='sent', tracking=True, group_expand='_expand_states')

    completed_document = fields.Binary(readonly=True, string="Completed Document", attachment=True)

    nb_wait = fields.Integer(string="Sent Requests", compute="_compute_count", store=True)
    nb_closed = fields.Integer(string="Completed Signatures", compute="_compute_count", store=True)
    nb_total = fields.Integer(string="Requested Signatures", compute="_compute_count", store=True)
    progress = fields.Char(string="Progress", compute="_compute_count", compute_sudo=True)
    start_sign = fields.Boolean(string="Signature Started", help="At least one signer has signed the document.", compute="_compute_count", compute_sudo=True)
    integrity = fields.Boolean(string="Integrity of the Sign request", compute='_compute_hashes', compute_sudo=True)

    active = fields.Boolean(default=True, string="Active")
    favorited_ids = fields.Many2many('res.users', string="Favorite of")

    color = fields.Integer()
    request_item_infos = fields.Binary(compute="_compute_request_item_infos")
    last_action_date = fields.Datetime(related="message_ids.create_date", readonly=True, string="Last Action Date")
    completion_date = fields.Date(string="Completion Date", compute="_compute_count", compute_sudo=True)

    sign_log_ids = fields.One2many('sign.log', 'sign_request_id', string="Logs", help="Activity logs linked to this request")

    @api.depends('request_item_ids.state')
    def _compute_count(self):
        for rec in self:
            wait, closed = 0, 0
            for s in rec.request_item_ids:
                if s.state == "sent":
                    wait += 1
                if s.state == "completed":
                    closed += 1
            rec.nb_wait = wait
            rec.nb_closed = closed
            rec.nb_total = wait + closed
            rec.start_sign = bool(closed)
            rec.progress = "{} / {}".format(closed, wait + closed)
            if closed:
                rec.start_sign = True
            signed_requests = rec.request_item_ids.filtered('signing_date')
            if wait == 0 and closed and signed_requests:
                last_completed_request = signed_requests.sorted(key=lambda i: i.signing_date, reverse=True)[0]
                rec.completion_date = last_completed_request.signing_date
            else:
                rec.completion_date = None

    @api.depends('request_item_ids.state', 'request_item_ids.partner_id.name')
    def _compute_request_item_infos(self):
        for rec in self:
            infos = []
            for item in rec.request_item_ids:
                infos.append({
                    'partner_name': item.partner_id.sudo().name if item.partner_id else 'Public User',
                    'state': item.state,
                })
            rec.request_item_infos = infos

    def _check_after_compute(self):
        for rec in self:
            if rec.state == 'sent' and rec.nb_closed == len(rec.request_item_ids) and len(rec.request_item_ids) > 0: # All signed
                rec.action_signed()

    def _get_final_recipients(self):
        self.ensure_one()
        all_recipients = set(self.request_item_ids.mapped('signer_email'))
        all_recipients |= set(self.mapped('message_follower_ids.partner_id.email'))
        # Remove False from all_recipients to avoid crashing later
        all_recipients.discard(False)
        return all_recipients

    def button_send(self):
        self.action_sent()

    def go_to_document(self):
        self.ensure_one()
        request_item = self.request_item_ids.filtered(lambda r: r.partner_id and r.partner_id.id == self.env.user.partner_id.id)[:1]
        return {
            'name': "Document \"%(name)s\"" % {'name': self.reference},
            'type': 'ir.actions.client',
            'tag': 'sign.Document',
            'context': {
                'id': self.id,
                'token': self.access_token,
                'sign_token': request_item.access_token if request_item and request_item.state == "sent" else None,
                'create_uid': self.create_uid.id,
                'state': self.state,
            },
        }

    def open_request(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sign.request",
            "views": [[False, "form"]],
            "res_id": self.id,
        }

    def get_completed_document(self):
        self.ensure_one()
        if not self.completed_document:
            self.generate_completed_document()

        return {
            'name': 'Signed Document',
            'type': 'ir.actions.act_url',
            'url': '/sign/download/%(request_id)s/%(access_token)s/completed' % {'request_id': self.id, 'access_token': self.access_token},
        }

    def open_logs(self):
        self.ensure_one()
        return {
            "name": _("Access History"),
            "type": "ir.actions.act_window",
            "res_model": "sign.log",
            'view_mode': 'tree,form',
            'domain': [('sign_request_id', '=', self.id)],
        }

    @api.onchange("progress", "start_sign")
    def _compute_hashes(self):
        for document in self:
            try:
                document.integrity = self.sign_log_ids._check_document_integrity()
            except Exception:
                document.integrity = False

    def toggle_favorited(self):
        self.ensure_one()
        self.write({'favorited_ids': [(3 if self.env.user in self[0].favorited_ids else 4, self.env.user.id)]})

    def action_resend(self):
        self.action_draft()
        subject = _("Signature Request - %s") % (self.template_id.attachment_id.name)
        self.action_sent(subject=subject)

    def action_draft(self):
        self.write({'completed_document': None, 'access_token': self._default_access_token()})

    def action_sent_without_mail(self):
        self.write({'state': 'sent'})
        for sign_request in self:
            for sign_request_item in sign_request.request_item_ids:
                sign_request_item.write({'state':'sent'})
                Log = http.request.env['sign.log'].sudo()
                vals = Log._prepare_vals_from_request(sign_request)
                vals['action'] = 'create'
                vals = Log._update_vals_with_http_request(vals)
                Log.create(vals)

    def action_sent(self, subject=None, message=None):
        # Send accesses by email
        self.write({'state': 'sent'})
        for sign_request in self:
            ignored_partners = []
            for request_item in sign_request.request_item_ids:
                if request_item.state != 'draft':
                    ignored_partners.append(request_item.partner_id.id)
            included_request_items = sign_request.request_item_ids.filtered(lambda r: not r.partner_id or r.partner_id.id not in ignored_partners)

            if sign_request.send_signature_accesses(subject, message, ignored_partners=ignored_partners):
                Log = http.request.env['sign.log'].sudo()
                vals = Log._prepare_vals_from_request(sign_request)
                vals['action'] = 'create'
                vals = Log._update_vals_with_http_request(vals)
                Log.create(vals)
                followers = sign_request.message_follower_ids.mapped('partner_id')
                followers -= sign_request.create_uid.partner_id
                followers -= sign_request.request_item_ids.mapped('partner_id')
                if followers:
                    sign_request.send_follower_accesses(followers, subject, message)
                included_request_items.action_sent()
            else:
                sign_request.action_draft()

    def action_signed(self):
        self.write({'state': 'signed'})
        self.env.cr.commit()
        if not self.check_is_encrypted():
            # if the file is encrypted, we must wait that the document is decrypted
            self.send_completed_document()

    def check_is_encrypted(self):
        self.ensure_one()
        if not self.template_id.sign_item_ids:
            return False

        old_pdf = PdfFileReader(io.BytesIO(base64.b64decode(self.template_id.attachment_id.datas)), strict=False, overwriteWarnings=False)
        return old_pdf.isEncrypted

    def action_canceled(self):
        self.write({'completed_document': None, 'access_token': self._default_access_token(), 'state': 'canceled'})
        for request_item in self.mapped('request_item_ids'):
            request_item.action_draft()

    def set_signers(self, signers):
        SignRequestItem = self.env['sign.request.item']

        for rec in self:
            rec.request_item_ids.filtered(lambda r: not r.partner_id or not r.role_id).unlink()
            ids_to_remove = []
            for request_item in rec.request_item_ids:
                for i in range(0, len(signers)):
                    if signers[i]['partner_id'] == request_item.partner_id.id and signers[i]['role'] == request_item.role_id.id:
                        signers.pop(i)
                        break
                else:
                    ids_to_remove.append(request_item.id)

            SignRequestItem.browse(ids_to_remove).unlink()
            for signer in signers:
                SignRequestItem.create({
                    'partner_id': signer['partner_id'],
                    'sign_request_id': rec.id,
                    'role_id': signer['role'],
                })

    def send_signature_accesses(self, subject=None, message=None, ignored_partners=[]):
        self.ensure_one()
        if len(self.request_item_ids) <= 0 or (set(self.request_item_ids.mapped('role_id')) != set(self.template_id.sign_item_ids.mapped('responsible_id'))):
            return False

        self.request_item_ids.filtered(lambda r: not r.partner_id or r.partner_id.id not in ignored_partners).send_signature_accesses(subject, message)
        return True

    def send_follower_accesses(self, followers, subject=None, message=None):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        tpl = self.env.ref('sign.sign_template_mail_follower')
        for follower in followers:
            if not follower.email:
                continue
            if not self.create_uid.email:
                raise UserError(_("Please configure the sender's email address"))
            tpl_follower = tpl.with_context(lang=get_lang(self.env, lang_code=follower.lang).code)
            body = tpl_follower.render({
                'record': self,
                'link': url_join(base_url, 'sign/document/%s/%s' % (self.id, self.access_token)),
                'subject': subject,
                'body': message,
            }, engine='ir.qweb', minimal_qcontext=True)
            self.env['sign.request']._message_send_mail(
                body, 'mail.mail_notification_light',
                {'record_name': self.reference},
                {'model_description': 'signature', 'company': self.create_uid.company_id},
                {'email_from': formataddr((self.create_uid.name, self.create_uid.email)),
                 'author_id': self.create_uid.partner_id.id,
                 'email_to': formataddr((follower.name, follower.email)),
                 'subject': subject or _('%s : Signature request') % self.reference},
                lang=follower.lang,
            )
            self.message_subscribe(partner_ids=follower.ids)

    def send_completed_document(self):
        self.ensure_one()
        if len(self.request_item_ids) <= 0 or self.state != 'signed':
            return False

        if not self.completed_document:
            self.generate_completed_document()

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        attachment = self.env['ir.attachment'].create({
            'name': "%s.pdf" % self.reference,
            'datas': self.completed_document,
            'type': 'binary',
            'res_model': self._name,
            'res_id': self.id,
        })
        report_action = self.env.ref('sign.action_sign_request_print_logs')
        # print the report with the public user in a sudoed env
        # public user because we don't want groups to pollute the result
        # (e.g. if the current user has the group Sign Manager,
        # some private information will be sent to *all* signers)
        # sudoed env because we have checked access higher up the stack
        public_user = self.env.ref('base.public_user', raise_if_not_found=False)
        if not public_user:
            # public user was deleted, fallback to avoid crash (info may leak)
            public_user = self.env.user
        pdf_content, __ = report_action.with_user(public_user).sudo().render_qweb_pdf(self.id)
        attachment_log = self.env['ir.attachment'].create({
            'name': "Activity Logs - %s.pdf" % time.strftime('%Y-%m-%d - %H:%M:%S'),
            'datas': base64.b64encode(pdf_content),
            'type': 'binary',
            'res_model': self._name,
            'res_id': self.id,
        })
        tpl = self.env.ref('sign.sign_template_mail_completed')
        for signer in self.request_item_ids:
            if not signer.signer_email:
                continue
            signer_lang = get_lang(self.env, lang_code=signer.partner_id.lang).code
            tpl = tpl.with_context(lang=signer_lang)
            body = tpl.render({
                'record': self,
                'link': url_join(base_url, 'sign/document/%s/%s' % (self.id, signer.access_token)),
                'subject': '%s signed' % self.reference,
                'body': False,
            }, engine='ir.qweb', minimal_qcontext=True)

            if not self.create_uid.email:
                raise UserError(_("Please configure the sender's email address"))
            if not signer.signer_email:
                raise UserError(_("Please configure the signer's email address"))

            self.env['sign.request']._message_send_mail(
                body, 'mail.mail_notification_light',
                {'record_name': self.reference},
                {'model_description': 'signature', 'company': self.create_uid.company_id},
                {'email_from': formataddr((self.create_uid.name, self.create_uid.email)),
                 'author_id': self.create_uid.partner_id.id,
                 'email_to': formataddr((signer.partner_id.name, signer.signer_email)),
                 'subject': _('%s has been signed') % self.reference,
                 'attachment_ids': [(4, attachment.id), (4, attachment_log.id)]},
                force_send=True,
                lang=signer_lang,
            )

        tpl = self.env.ref('sign.sign_template_mail_completed')
        for follower in self.mapped('message_follower_ids.partner_id') - self.request_item_ids.mapped('partner_id'):
            if not follower.email:
                continue
            if not self.create_uid.email:
                raise UserError(_("Please configure the sender's email address"))

            tpl_follower = tpl.with_context(lang=get_lang(self.env, lang_code=follower.lang).code)
            body = tpl.render({
                'record': self,
                'link': url_join(base_url, 'sign/document/%s/%s' % (self.id, self.access_token)),
                'subject': '%s signed' % self.reference,
                'body': '',
            }, engine='ir.qweb', minimal_qcontext=True)
            self.env['sign.request']._message_send_mail(
                body, 'mail.mail_notification_light',
                {'record_name': self.reference},
                {'model_description': 'signature', 'company': self.create_uid.company_id},
                {'email_from': formataddr((self.create_uid.name, self.create_uid.email)),
                 'author_id': self.create_uid.partner_id.id,
                 'email_to': formataddr((follower.name, follower.email)),
                 'subject': _('%s has been signed') % self.reference},
                lang=follower.lang,
            )

        return True

    def _get_font(self):
        custom_font = self.env["ir.config_parameter"].sudo().get_param("sign.use_custom_font")
        # The font must be a TTF font. The tool 'otf2ttf' may be useful for conversion.
        if custom_font:
            pdfmetrics.registerFont(TTFont(custom_font, custom_font + ".ttf"))
            return custom_font
        return "Helvetica"

    def _get_normal_font_size(self):
        return 0.015

    def generate_completed_document(self, password=""):
        self.ensure_one()
        if not self.template_id.sign_item_ids:
            self.completed_document = self.template_id.attachment_id.datas
            return

        old_pdf = PdfFileReader(io.BytesIO(base64.b64decode(self.template_id.attachment_id.datas)), strict=False, overwriteWarnings=False)

        isEncrypted = old_pdf.isEncrypted
        if isEncrypted and not old_pdf.decrypt(password):
            # password is not correct
            return

        font = self._get_font()
        normalFontSize = self._get_normal_font_size()

        packet = io.BytesIO()
        can = canvas.Canvas(packet)
        itemsByPage = self.template_id.sign_item_ids.getByPage()
        SignItemValue = self.env['sign.request.item.value']
        for p in range(0, old_pdf.getNumPages()):
            page = old_pdf.getPage(p)
            # Absolute values are taken as it depends on the MediaBox template PDF metadata, they may be negative
            width = float(abs(page.mediaBox.getWidth()))
            height = float(abs(page.mediaBox.getHeight()))

            # Set page orientation (either 0, 90, 180 or 270)
            rotation = page.get('/Rotate')
            if rotation:
                can.rotate(rotation)
                # Translate system so that elements are placed correctly
                # despite of the orientation
                if rotation == 90:
                    width, height = height, width
                    can.translate(0, -height)
                elif rotation == 180:
                    can.translate(-width, -height)
                elif rotation == 270:
                    width, height = height, width
                    can.translate(-width, 0)

            items = itemsByPage[p + 1] if p + 1 in itemsByPage else []
            for item in items:
                value = SignItemValue.search([('sign_item_id', '=', item.id), ('sign_request_id', '=', self.id)], limit=1)
                if not value or not value.value:
                    continue

                value = value.value

                if item.type_id.item_type == "text":
                    can.setFont(font, height*item.height*0.8)
                    can.drawString(width*item.posX, height*(1-item.posY-item.height*0.9), value)

                elif item.type_id.item_type == "selection":
                    content = []
                    for option in item.option_ids:
                        if option.id != int(value):
                            content.append("<strike>%s</strike>" % (option.value))
                        else:
                            content.append(option.value)
                    font_size = height * normalFontSize * 0.8
                    can.setFont(font, font_size)
                    text = " / ".join(content)
                    string_width = stringWidth(text.replace("<strike>", "").replace("</strike>", ""), font, font_size)
                    p = Paragraph(text, getSampleStyleSheet()["Normal"])
                    w, h = p.wrap(width, height)
                    posX = width * (item.posX + item.width * 0.5) - string_width // 2
                    posY = height * (1 - item.posY - item.height * 0.5) - h // 2
                    p.drawOn(can, posX, posY)

                elif item.type_id.item_type == "textarea":
                    can.setFont(font, height*normalFontSize*0.8)
                    lines = value.split('\n')
                    y = (1-item.posY)
                    for line in lines:
                        y -= normalFontSize*0.9
                        can.drawString(width*item.posX, height*y, line)
                        y -= normalFontSize*0.1

                elif item.type_id.item_type == "checkbox":
                    can.setFont(font, height*item.height*0.8)
                    value = 'X' if value == 'on' else ''
                    can.drawString(width*item.posX, height*(1-item.posY-item.height*0.9), value)

                elif item.type_id.item_type == "signature" or item.type_id.item_type == "initial":
                    image_reader = ImageReader(io.BytesIO(base64.b64decode(value[value.find(',')+1:])))
                    _fix_image_transparency(image_reader._image)
                    can.drawImage(image_reader, width*item.posX, height*(1-item.posY-item.height), width*item.width, height*item.height, 'auto', True)

            can.showPage()

        can.save()

        item_pdf = PdfFileReader(packet, overwriteWarnings=False)
        new_pdf = PdfFileWriter()

        for p in range(0, old_pdf.getNumPages()):
            page = old_pdf.getPage(p)
            page.mergePage(item_pdf.getPage(p))
            new_pdf.addPage(page)

        if isEncrypted:
            new_pdf.encrypt(password)

        output = io.BytesIO()
        new_pdf.write(output)
        self.completed_document = base64.b64encode(output.getvalue())
        output.close()

    @api.model
    def _message_send_mail(self, body, notif_template_xmlid, message_values, notif_values, mail_values, force_send=False, **kwargs):
        """ Shortcut to send an email. """
        default_lang = get_lang(self.env, lang_code=kwargs.get('lang')).code
        lang = kwargs.get('lang', default_lang)
        sign_request = self.with_context(lang=lang)

        # the notif layout wrapping expects a mail.message record, but we don't want
        # to actually create the record
        # See @tde-banana-odoo for details
        msg = sign_request.env['mail.message'].sudo().new(dict(body=body, **message_values))
        notif_layout = sign_request.env.ref(notif_template_xmlid)
        body_html = notif_layout.render(dict(message=msg, **notif_values), engine='ir.qweb', minimal_qcontext=True)
        body_html = sign_request.env['mail.thread']._replace_local_links(body_html)

        mail = sign_request.env['mail.mail'].create(dict(body_html=body_html, state='outgoing', **mail_values))
        if force_send:
            mail.send()
        return mail

    @api.model
    def initialize_new(self, id, signers, followers, reference, subject, message, send=True, without_mail=False):
        sign_users = self.env['res.users'].search([('partner_id', 'in', [signer['partner_id'] for signer in signers])]).filtered(lambda u: u.has_group('sign.group_sign_user'))
        sign_request = self.create({'template_id': id, 'reference': reference, 'favorited_ids': [(4, item) for item in (sign_users | self.env.user).ids]})
        sign_request.message_subscribe(partner_ids=followers)
        sign_request.activity_update(sign_users)
        sign_request.set_signers(signers)
        if send:
            sign_request.action_sent(subject, message)
        if without_mail:
            sign_request.action_sent_without_mail()
        return {
            'id': sign_request.id,
            'token': sign_request.access_token,
            'sign_token': sign_request.request_item_ids.filtered(lambda r: r.partner_id == self.env.user.partner_id)[:1].access_token,
        }

    @api.model
    def add_followers(self, id, followers):
        sign_request = self.browse(id)
        old_followers = set(sign_request.message_follower_ids.mapped('partner_id.id'))
        followers = list(set(followers) - old_followers)
        if followers:
            sign_request.message_subscribe(partner_ids=followers)
            sign_request.send_follower_accesses(self.env['res.partner'].browse(followers))
        return sign_request.id

    @api.model
    def activity_update(self, sign_users):
        for user in sign_users:
            self.with_context(mail_activity_quick_update=True).activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=user.id
            )


class SignRequestItem(models.Model):
    _name = "sign.request.item"
    _description = "Signature Request Item"
    _rec_name = 'partner_id'

    def _default_access_token(self):
        return str(uuid.uuid4())

    partner_id = fields.Many2one('res.partner', string="Contact", ondelete='cascade')
    sign_request_id = fields.Many2one('sign.request', string="Signature Request", ondelete='cascade', required=True)
    sign_item_value_ids = fields.One2many('sign.request.item.value', 'sign_request_item_id', string="Value")

    access_token = fields.Char('Security Token', required=True, default=_default_access_token, readonly=True)
    access_via_link = fields.Boolean('Accessed Through Token')
    role_id = fields.Many2one('sign.item.role', string="Role")
    sms_number = fields.Char(related='partner_id.mobile', readonly=False, depends=(['partner_id']), store=True)
    sms_token = fields.Char('SMS Token', readonly=True)

    signature = fields.Binary(attachment=True)
    signing_date = fields.Date('Signed on', readonly=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("sent", "Waiting for completion"),
        ("completed", "Completed")
    ], readonly=True, default="draft")

    signer_email = fields.Char(related='partner_id.email', readonly=False, depends=(['partner_id']), store=True)

    latitude = fields.Float(digits=(10, 7))
    longitude = fields.Float(digits=(10, 7))

    def action_draft(self):
        self.write({
            'signature': None,
            'signing_date': None,
            'access_token': self._default_access_token(),
            'state': 'draft',
        })
        for request_item in self:
            itemsToClean = request_item.sign_request_id.template_id.sign_item_ids.filtered(lambda r: r.responsible_id == request_item.role_id or not r.responsible_id)
            self.env['sign.request.item.value'].search([('sign_item_id', 'in', itemsToClean.mapped('id')), ('sign_request_id', '=', request_item.sign_request_id.id)]).unlink()
        self.mapped('sign_request_id')._check_after_compute()

    def action_sent(self):
        self.write({'state': 'sent'})
        self.mapped('sign_request_id')._check_after_compute()

    def action_completed(self):
        date = fields.Date.context_today(self).strftime(DEFAULT_SERVER_DATE_FORMAT)
        self.write({'signing_date': date, 'state': 'completed'})
        self.mapped('sign_request_id')._check_after_compute()

    def send_signature_accesses(self, subject=None, message=None):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        tpl = self.env.ref('sign.sign_template_mail_request')
        for signer in self:
            if not signer.partner_id or not signer.partner_id.email:
                continue
            if not signer.create_uid.email:
                continue
            signer_lang = get_lang(self.env, lang_code=signer.partner_id.lang).code
            tpl = tpl.with_context(lang=signer_lang)
            body = tpl.render({
                'record': signer,
                'link': url_join(base_url, "sign/document/mail/%(request_id)s/%(access_token)s" % {'request_id': signer.sign_request_id.id, 'access_token': signer.access_token}),
                'subject': subject,
                'body': message if message != '<p><br></p>' else False,
            }, engine='ir.qweb', minimal_qcontext=True)

            if not signer.signer_email:
                raise UserError(_("Please configure the signer's email address"))
            self.env['sign.request']._message_send_mail(
                body, 'mail.mail_notification_light',
                {'record_name': signer.sign_request_id.reference},
                {'model_description': 'signature', 'company': signer.create_uid.company_id},
                {'email_from': formataddr((signer.create_uid.name, signer.create_uid.email)),
                 'author_id': signer.create_uid.partner_id.id,
                 'email_to': formataddr((signer.partner_id.name, signer.partner_id.email)),
                 'subject': subject},
                force_send=True,
                lang=signer_lang,
            )

    def sign(self, signature):
        self.ensure_one()
        if not isinstance(signature, dict):
            self.signature = signature
        else:
            SignItemValue = self.env['sign.request.item.value']
            request = self.sign_request_id

            signerItems = request.template_id.sign_item_ids.filtered(lambda r: not r.responsible_id or r.responsible_id.id == self.role_id.id)
            autorizedIDs = set(signerItems.mapped('id'))
            requiredIDs = set(signerItems.filtered('required').mapped('id'))

            itemIDs = {int(k) for k in signature}
            if not (itemIDs <= autorizedIDs and requiredIDs <= itemIDs): # Security check
                return False

            user = self.env['res.users'].search([('partner_id', '=', self.partner_id.id)], limit=1).sudo()
            for itemId in signature:
                item_value = SignItemValue.search([('sign_item_id', '=', int(itemId)), ('sign_request_id', '=', request.id)])
                if not item_value:
                    item_value = SignItemValue.create({'sign_item_id': int(itemId), 'sign_request_id': request.id,
                                                       'value': signature[itemId], 'sign_request_item_id': self.id})
                    if item_value.sign_item_id.type_id.item_type == 'signature':
                        self.signature = signature[itemId][signature[itemId].find(',')+1:]
                        if user:
                            user.sign_signature = self.signature
                    if item_value.sign_item_id.type_id.item_type == 'initial' and user:
                        user.sign_initials = signature[itemId][signature[itemId].find(',')+1:]

        return True

    @api.model
    def resend_access(self, id):
        sign_request_item = self.browse(id)
        subject = _("Signature Request - %s") % (sign_request_item.sign_request_id.template_id.attachment_id.name)
        self.browse(id).send_signature_accesses(subject=subject)

    def _reset_sms_token(self):
        for record in self:
            record.sms_token = randint(100000, 999999)

    def _send_sms(self):
        for rec in self:
            rec._reset_sms_token()
            self.env['sms.api']._send_sms([rec.sms_number], _('Your confirmation code is %s') % rec.sms_token)


class SignRequestItemValue(models.Model):
    _name = "sign.request.item.value"
    _description = "Signature Item Value"
    _rec_name = 'sign_request_id'

    sign_request_item_id = fields.Many2one('sign.request.item', string="Signature Request item", required=True,
                                           ondelete='cascade')
    sign_item_id = fields.Many2one('sign.item', string="Signature Item", required=True, ondelete='cascade')
    sign_request_id = fields.Many2one(string="Signature Request", required=True, ondelete='cascade', related='sign_request_item_id.sign_request_id')

    value = fields.Text()
