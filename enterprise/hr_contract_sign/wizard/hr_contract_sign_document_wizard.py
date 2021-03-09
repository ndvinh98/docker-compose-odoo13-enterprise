# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrContractSignDocumentWizard(models.TransientModel):
    _name = 'hr.contract.sign.document.wizard'
    _description = 'Sign document in contract'

    def _group_hr_contract_domain(self):
        group = self.env.ref('hr_contract.group_hr_contract_manager', raise_if_not_found=False)
        return [('groups_id', 'in', group.ids)] if group else []

    def _sign_template_domain(self):
        list_template = []
        for template in self.env['sign.template'].search([]):
            if len(template.sign_item_ids.mapped('responsible_id')) == 2:
                list_template.append(template.id)
        return [('id', 'in', list_template)]

    def _default_responsible_id(self):
        return self.env['hr.contract'].browse(self.env.context.get('active_id')).hr_responsible_id

    contract_id = fields.Many2one('hr.contract', string='Contract',
        default=lambda self: self.env.context.get('active_id'))
    employee_id = fields.Many2one('hr.employee', string='Employee', compute='_compute_employee')
    responsible_id = fields.Many2one('res.users', string='Responsible', required=True,
        default=_default_responsible_id, domain=_group_hr_contract_domain)
    employee_role_id = fields.Many2one("sign.item.role", string="Employee Role", required=True)

    sign_template_id = fields.Many2one('sign.template', string="Document to Sign", required=True,
        domain=_sign_template_domain, help="Document that the employee will have to sign.")

    subject = fields.Char(string="Subject", required=True, default='Signature Request')
    message = fields.Html("Message")
    follower_ids = fields.Many2many('res.partner', string="Copy to")

    @api.onchange('sign_template_id')
    def _onchange_sign_template_id(self):
        return {'domain': {'employee_role_id': [('id', 'in', self.sign_template_id.mapped('sign_item_ids.responsible_id').ids)]}}

    @api.depends('contract_id')
    def _compute_employee(self):
        for contract in self:
            contract.employee_id = contract.contract_id.employee_id

    def validate_signature(self):
        if not self.employee_id.user_id and not self.employee_id.user_id.partner_id:
            raise ValidationError(_('Employee must be linked to a user and a partner.'))

        sign_request = self.env['sign.request']
        if not self.check_access_rights('create', raise_exception=False):
            sign_request = sign_request.sudo()

        second_role = set(self.sign_template_id.mapped('sign_item_ids.responsible_id').ids)
        second_role.remove(self.employee_role_id.id)

        res = sign_request.initialize_new(
            self.sign_template_id.id,
            [
                {'role': self.employee_role_id.id,
                 'partner_id': self.employee_id.user_id.partner_id.id},
                {'role': second_role.pop(),
                 'partner_id': self.responsible_id.partner_id.id}
            ],
            self.follower_ids.ids.append(self.responsible_id.partner_id.id),
            'Signature Request - ' + self.contract_id.name,
            self.subject,
            self.message
        )

        sign_request = self.env['sign.request'].browse(res['id'])
        if not self.check_access_rights('write', raise_exception=False):
            sign_request = sign_request.sudo()

        sign_request.toggle_favorited()
        sign_request.action_sent()
        sign_request.write({'state': 'sent'})
        sign_request.request_item_ids.write({'state': 'sent'})

        self.contract_id.sign_request_ids += sign_request

        self.contract_id.message_post(body=_('%s requested a new signature on document: %s.<br/>%s and %s are the signatories.') %
            (self.env.user.display_name, self.sign_template_id.name, self.employee_id.display_name, self.responsible_id.display_name))

        if self.env.user.id == self.responsible_id.id:
            return sign_request.go_to_document()
