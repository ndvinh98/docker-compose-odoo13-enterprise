# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import formataddr

_logger = logging.getLogger(__name__)


class RequestAppraisal(models.TransientModel):
    _name = 'request.appraisal'
    _description = "Request an Appraisal"

    @api.model
    def default_get(self, fields):
        if not self.env.user.email:
            raise UserError(_("Unable to post message, please configure the sender's email address."))
        result = super(RequestAppraisal, self).default_get(fields)
        result.update({
            'email_from': formataddr((self.env.user.name, self.env.user.email)),
            'author_id': self.env.user.partner_id.id,
        })
        if self.env.context.get('active_model') == 'hr.employee':
            employee = self.env['hr.employee'].browse(self.env.context['active_id'])
            template = self.env.ref('hr_appraisal.mail_template_appraisal_request', raise_if_not_found=False)
            result.update({
                'template_id': template and template.id or False,
                'recipient_id': employee.user_id.partner_id.id or employee.address_home_id.id,
                'employee_id': employee.id,
            })
        if self.env.context.get('active_model') == 'res.users':
            user = self.env['res.users'].browse(self.env.context['active_id'])
            template = self.env.ref('hr_appraisal.mail_template_appraisal_request_from_employee', raise_if_not_found=False)
            result.update({
                'template_id': template and template.id or False,
                'recipient_id': user.employee_id.parent_id.user_id.partner_id.id,
                'employee_id': user.employee_id.id,
            })
        return result

    subject = fields.Char('Subject')
    body = fields.Html('Contents', default='', sanitize_style=True)
    attachment_ids = fields.Many2many(
        'ir.attachment', 'hr_appraisal_mail_compose_message_ir_attachments_rel',
        'wizard_id', 'attachment_id', string='Attachments')
    template_id = fields.Many2one(
        'mail.template', 'Use template', index=True,
        domain="[('model', '=', 'hr.appraisal')]")
    email_from = fields.Char('From', help="Email address of the sender", required=True)
    author_id = fields.Many2one('res.partner', 'Author', help="Author of the message.", required=True)
    employee_id = fields.Many2one('hr.employee', 'Appraisal Employee')
    recipient_id = fields.Many2one('res.partner', 'Recipient')
    deadline = fields.Date(string="Desired Deadline", required=True)

    @api.onchange('template_id', 'recipient_id')
    def _onchange_template_id(self):
        if self.template_id:
            ctx = {
                'partner_to_name': self.recipient_id.name,
                'author_name': self.author_id.name,
                'url': "${ctx['url']}",
            }
            self.subject = self.env['mail.template'].with_context(ctx)._render_template(self.template_id.subject, 'res.users', self.env.user.id, post_process=True)
            self.body = self.env['mail.template'].with_context(ctx)._render_template(self.template_id.body_html, 'res.users', self.env.user.id, post_process=False)

    def action_invite(self):
        """ Process the wizard content and proceed with sending the related
            email(s), rendering any template patterns on the fly if needed """
        self.ensure_one()
        if not self.recipient_id:
            raise UserError(_("The recipient is required!"))
        appraisal = self.env['hr.appraisal'].create({
            'employee_id': self.employee_id.id,
            'date_close': self.deadline,
        })
        appraisal.message_subscribe(partner_ids=self.recipient_id.ids)
        appraisal.sudo()._onchange_employee_id()
        appraisal._onchange_company_id()

        ctx = {'url': '/mail/view?model=%s&res_id=%s' % ('hr.appraisal', appraisal.id)}
        body = self.env['mail.template'].with_context(ctx)._render_template(self.body, 'hr.appraisal', appraisal.id, post_process=True)
        mail_values = {
            'email_from': self.email_from,
            'author_id': self.author_id.id,
            'model': None,
            'res_id': None,
            'subject': self.subject,
            'body_html': body,
            'attachment_ids': [(4, att.id) for att in self.attachment_ids],
            'auto_delete': True,
            'recipient_ids': [(4, self.recipient_id.id)]
        }

        template = self.env.ref('mail.mail_notification_light', raise_if_not_found=False)
        template_ctx = {
            'message': self.env['mail.message'].sudo().new(dict(body=mail_values['body_html'], record_name=appraisal.display_name)),
            'model_description': 'Employee Appraisal',
            'company': self.env.company,
        }
        body = template.render(template_ctx, engine='ir.qweb', minimal_qcontext=True)
        mail_values['body_html'] = self.env['mail.thread']._replace_local_links(body)

        self.env['mail.mail'].sudo().create(mail_values)

        return {
            'name': _('Appraisal Request'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'hr.appraisal',
            'res_id': appraisal.id,
        }
