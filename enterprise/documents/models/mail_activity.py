# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _


class MailActivityType(models.Model):
    _inherit = "mail.activity.type"

    tag_ids = fields.Many2many('documents.tag')
    folder_id = fields.Many2one('documents.folder',
                                help="By defining a folder, the upload activities will generate a document")
    default_user_id = fields.Many2one('res.users', string="Default User")


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    def _action_done(self, feedback=False, attachment_ids=None):
        if attachment_ids:
            for record in self:
                document = self.env['documents.document'].search([('request_activity_id', '=', record.id)], limit=1)
                if document and not document.attachment_id:
                    self.env['documents.document'].search([('attachment_id', '=', attachment_ids[0])]).unlink()
                    if not feedback:
                        feedback = _("Document Request: %s Uploaded by: %s") % (document.name, self.env.user.name)
                    document.write({'attachment_id': attachment_ids[0], 'request_activity_id': False})

        return super(MailActivity, self)._action_done(feedback=feedback, attachment_ids=attachment_ids)

    @api.model
    def create(self, values):
        activity = super(MailActivity, self).create(values)
        activity_type = activity.activity_type_id
        if activity_type.category == 'upload_file' and activity.res_model != 'documents.document':
            if activity_type.folder_id:
                self.env['documents.document'].create({
                    'res_model': activity.res_model,
                    'res_id': activity.res_id,
                    'owner_id': activity_type.default_user_id.id,
                    'folder_id': activity_type.folder_id.id,
                    'tag_ids': [(6, 0, activity_type.tag_ids.ids if activity_type.tag_ids else [])],
                    'name': activity.summary or activity.res_name or 'upload file request',
                    'request_activity_id': activity.id,
                })
        return activity
