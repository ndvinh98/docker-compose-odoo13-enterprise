# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions, _


class WorkflowActionRuleSign(models.Model):
    _inherit = ['documents.workflow.rule']

    has_business_option = fields.Boolean(default=True, compute='_get_business')
    create_model = fields.Selection(selection_add=[('sign.template.new', "Create signature request"),
                                                   ('sign.template.direct', "Sign directly")])

    def _compute_limited_to_single_record(self):
        super(WorkflowActionRuleSign, self)._compute_limited_to_single_record()
        for record in self:
            if record.create_model == 'sign.template.direct':
                record.limited_to_single_record = True

    def create_record(self, documents=None):
        rv = super(WorkflowActionRuleSign, self).create_record(documents=documents)
        if self.create_model.startswith('sign.template'):
            new_obj = None
            template_ids = []
            for document in documents:
                create_values = {
                    'name': document.name.rsplit('.', 1)[0],
                    'attachment_id': document.attachment_id.id,
                    'favorited_ids': [(4, self.env.user.id)],
                }
                if self.folder_id:
                    create_values['folder_id'] = self.folder_id.id
                elif self.domain_folder_id:
                    create_values['folder_id'] = self.domain_folder_id.id
                if document.tag_ids:
                    create_values['documents_tag_ids'] = [(6, 0, document.tag_ids.ids)]

                new_obj = self.env['sign.template'].create(create_values)

                this_document = document
                if (document.res_model or document.res_id) and document.res_model != 'documents.document':
                    this_document = document.copy()
                    attachment_id_copy = document.attachment_id.with_context(no_document=True).copy()
                    this_document.write({'attachment_id': attachment_id_copy.id})

                this_document.attachment_id.with_context(no_document=True).write({
                    'res_model': 'sign.template',
                    'res_id': new_obj.id
                })

                template_ids.append(new_obj.id)

            action = {
                'type': 'ir.actions.act_window',
                'res_model': 'sign.template',
                'name': _("New templates"),
                'view_id': False,
                'view_mode': 'kanban',
                'views': [(False, "kanban"), (False, "form")],
                'domain': [('id', 'in', template_ids)],
                'context': self._context,
            }

            if len(template_ids) == 1:
                return new_obj.go_to_custom_template(sign_directly_without_mail=self.create_model == 'sign.template.direct')
            return action
        return rv
