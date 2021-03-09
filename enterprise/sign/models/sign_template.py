# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
import base64
import io

from PyPDF2 import PdfFileReader

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SignTemplate(models.Model):
    _name = "sign.template"
    _description = "Signature Template"
    _rec_name = "attachment_id"

    def _default_favorited_ids(self):
        return [(4, self.env.user.id)]

    attachment_id = fields.Many2one('ir.attachment', string="Attachment", required=True, ondelete='cascade')
    name = fields.Char(related='attachment_id.name', readonly=False)
    datas = fields.Binary(related='attachment_id.datas', readonly=False)
    sign_item_ids = fields.One2many('sign.item', 'template_id', string="Signature Items", copy=True)
    responsible_count = fields.Integer(compute='_compute_responsible_count', string="Responsible Count")

    active = fields.Boolean(default=True, string="Active")
    privacy = fields.Selection([('employee', 'All Users'), ('invite', 'On Invitation')],
                               string="Privacy", default="invite",
                               help="Set who can use this template:\n"
                                    "- All Users: all users of the Sign application can view and use the template\n"
                                    "- On Invitation: only invited users can view and use the template\n"
                                    "Invited users can always edit the document template.\n"
                                    "Existing requests based on this template will not be affected by changes.")
    favorited_ids = fields.Many2many('res.users', string="Invited Users", default=lambda s: s._default_favorited_ids())

    share_link = fields.Char(string="Share Link", copy=False)

    sign_request_ids = fields.One2many('sign.request', 'template_id', string="Signature Requests")

    tag_ids = fields.Many2many('sign.template.tag', string='Tags')
    color = fields.Integer()
    redirect_url = fields.Char(string="Redirect Link", default="",
        help="Optional link for redirection after signature")
    redirect_url_text = fields.Char(string="Link Label", default="Open Link",
        help="Optional text to display on the button link")

    @api.depends('sign_item_ids.responsible_id')
    def _compute_responsible_count(self):
        for template in self:
            template.responsible_count = len(template.sign_item_ids.mapped('responsible_id'))

    def go_to_custom_template(self, sign_directly_without_mail=False):
        self.ensure_one()
        return {
            'name': "Template \"%(name)s\"" % {'name': self.attachment_id.name},
            'type': 'ir.actions.client',
            'tag': 'sign.Template',
            'context': {
                'id': self.id,
                'sign_directly_without_mail': sign_directly_without_mail,
            },
        }

    def toggle_favorited(self):
        self.ensure_one()
        self.write({'favorited_ids': [(3 if self.env.user in self[0].favorited_ids else 4, self.env.user.id)]})

    def unlink(self):
        if self.filtered(lambda template: template.sign_request_ids):
            raise UserError(_("You can't delete a template for which signature requests exist but you can archive it instead."))
        return super(SignTemplate, self).unlink()

    @api.model
    def upload_template(self, name=None, dataURL=None, active=True):
        mimetype = dataURL[dataURL.find(':')+1:dataURL.find(',')]
        datas = dataURL[dataURL.find(',')+1:]
        # TODO: for now, PDF files without extension are recognized as application/octet-stream;base64
        try:
            file_pdf = PdfFileReader(io.BytesIO(base64.b64decode(datas)), strict=False, overwriteWarnings=False)
        except Exception as e:
            raise UserError(_("This file cannot be read. Is it a valid PDF?"))
        file_type = mimetype.replace('application/', '').replace(';base64', '')
        extension = re.compile(re.escape(file_type), re.IGNORECASE)
        name = extension.sub(file_type, name)
        attachment = self.env['ir.attachment'].create({'name': name, 'datas': datas, 'mimetype': mimetype})
        template = self.create({'attachment_id': attachment.id, 'favorited_ids': [(4, self.env.user.id)], 'active': active})

        return {'template': template.id, 'attachment': attachment.id}

    @api.model
    def update_from_pdfviewer(self, template_id=None, duplicate=None, sign_items=None, name=None):
        template = self.browse(template_id)
        if not duplicate and len(template.sign_request_ids) > 0:
            return False

        if duplicate:
            new_attachment = template.attachment_id.copy()
            r = re.compile(' \(v(\d+)\)$')
            m = r.search(name)
            v = str(int(m.group(1))+1) if m else "2"
            index = m.start() if m else len(name)
            new_attachment.name = name[:index] + " (v" + v + ")"
            template = template.copy({
                'attachment_id': new_attachment.id,
                'favorited_ids': [(4, self.env.user.id)]
            })

        elif name:
            template.attachment_id.name = name

        item_ids = {
            it
            for it in map(int, sign_items)
            if it > 0
        }
        template.sign_item_ids.filtered(lambda r: r.id not in item_ids).unlink()
        for item in template.sign_item_ids:
            values = sign_items.pop(str(item.id))
            values['option_ids'] = [(6, False, [int(op) for op in values.get('option_ids', [])])]
            item.write(values)
        for item in sign_items.values():
            item['template_id'] = template.id
            item['option_ids'] = [(6, False, [int(op) for op in item.get('option_ids', [])])]
            self.env['sign.item'].create(item)

        if len(template.sign_item_ids.mapped('responsible_id')) > 1:
            template.share_link = None

        return template.id

    @api.model
    def add_option(self, value):
        option = self.env['sign.item.option'].search([('value', '=', value)])
        option_id = option if option else self.env['sign.item.option'].create({'value': value})
        return option_id.id

    def open_requests(self,):
        return {
            "type": "ir.actions.act_window",
            "name": _("Sign requests"),
            "res_model": "sign.request",
            "domain": [["template_id.id", "in", self.ids]],
            "views": [[False, 'kanban'],[False, "form"]],
            "res_id": self.id,
        }

class SignTemplateTag(models.Model):

    _name = "sign.template.tag"
    _description = "Sign Template Tag"

    name = fields.Char('Tag Name', required=True, translate=True)
    color = fields.Integer('Color Index')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Tag name already exists !"),
    ]


class SignItemSelectionOption(models.Model):
    _name = "sign.item.option"
    _description = "Option of a selection Field"

    value = fields.Text(string="Option")


class SignItem(models.Model):
    _name = "sign.item"
    _description = "Fields to be sign on Document"
    _rec_name = 'template_id'

    template_id = fields.Many2one('sign.template', string="Document Template", required=True, ondelete='cascade')

    type_id = fields.Many2one('sign.item.type', string="Type", required=True, ondelete='cascade')

    required = fields.Boolean(default=True)
    responsible_id = fields.Many2one("sign.item.role", string="Responsible")

    option_ids = fields.Many2many("sign.item.option", string="Selection options")

    name = fields.Char(string="Field Name")
    page = fields.Integer(string="Document Page", required=True, default=1)
    posX = fields.Float(digits=(4, 3), string="Position X", required=True)
    posY = fields.Float(digits=(4, 3), string="Position Y", required=True)
    width = fields.Float(digits=(4, 3), required=True)
    height = fields.Float(digits=(4, 3), required=True)

    def getByPage(self):
        items = {}
        for item in self:
            if item.page not in items:
                items[item.page] = []
            items[item.page].append(item)
        return items


class SignItemType(models.Model):
    _name = "sign.item.type"
    _description = "Signature Item Type"

    name = fields.Char(string="Field Name", required=True, translate=True)
    item_type = fields.Selection([
        ('signature', "Signature"),
        ('initial', "Initial"),
        ('text', "Text"),
        ('textarea', "Multiline Text"),
        ('checkbox', "Checkbox"),
        ('selection', "Selection"),
    ], required=True, string='Type', default='text')

    tip = fields.Char(required=True, default="fill in", translate=True)
    placeholder = fields.Char(translate=True)

    default_width = fields.Float(string="Default Width", digits=(4, 3), required=True, default=0.150)
    default_height = fields.Float(string="Default Height", digits=(4, 3), required=True, default=0.015)
    auto_field = fields.Char(string="Automatic Partner Field", help="Partner field to use to auto-complete the fields of this type")


class SignItemParty(models.Model):
    _name = "sign.item.role"
    _description = "Signature Item Party"

    name = fields.Char(required=True, translate=True)

    sms_authentification = fields.Boolean('SMS Authentication', default=False,)

    @api.model
    def add(self, name):
        party = self.search([('name', '=', name)])
        return party.id if party else self.create({'name': name}).id

    def buy_credits(self):
        service_name = 'sms'
        url = self.env['iap.account'].get_credits_url(service_name)
        return {
            'name': 'Buy SMS credits',
            'res_model': 'ir.actions.act_url',
            'type': 'ir.actions.act_url',
            'target': 'current',
            'url': url
        }
