# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ApprovalRequest(models.Model):
    _name = 'approval.request'
    _description = 'Approval Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    @api.model
    def _read_group_request_status(self, stages, domain, order):
        request_status_list = dict(self._fields['request_status'].selection).keys()
        return request_status_list

    name = fields.Char(string="Approval Subject", tracking=True)
    category_id = fields.Many2one('approval.category', string="Category", required=True)
    approver_ids = fields.One2many('approval.approver', 'request_id', string="Approvers")
    date = fields.Datetime(string="Date")
    date_start = fields.Datetime(string="Date start")
    date_end = fields.Datetime(string="Date end")
    items = fields.Char(string="Items")
    quantity = fields.Float(string="Quantity")
    location = fields.Char(string="Location")
    date_confirmed = fields.Datetime(string="Date Confirmed")
    partner_id = fields.Many2one('res.partner', string="Contact")
    reference = fields.Char(string="Reference")
    amount = fields.Float(string="Amount")
    reason = fields.Text(string="Description")
    request_status = fields.Selection([
        ('new', 'To Submit'),
        ('pending', 'Submitted'),
        ('approved', 'Approved'),
        ('refused', 'Refused'),
        ('cancel', 'Cancel')], default="new", compute="_compute_request_status", store=True, compute_sudo=True, group_expand='_read_group_request_status')
    request_owner_id = fields.Many2one('res.users', string="Request Owner")
    user_status = fields.Selection([
        ('new', 'New'),
        ('pending', 'To Approve'),
        ('approved', 'Approved'),
        ('refused', 'Refused'),
        ('cancel', 'Cancel')], compute="_compute_user_status")
    has_access_to_request = fields.Boolean(string="Has Access To Request", compute="_compute_has_access_to_request")
    attachment_number = fields.Integer('Number of Attachments', compute='_compute_attachment_number')

    has_date = fields.Selection(related="category_id.has_date")
    has_period = fields.Selection(related="category_id.has_period")
    has_item = fields.Selection(related="category_id.has_item")
    has_quantity = fields.Selection(related="category_id.has_quantity")
    has_amount = fields.Selection(related="category_id.has_amount")
    has_reference = fields.Selection(related="category_id.has_reference")
    has_partner = fields.Selection(related="category_id.has_partner")
    has_payment_method = fields.Selection(related="category_id.has_payment_method")
    has_location = fields.Selection(related="category_id.has_location")
    requirer_document = fields.Selection(related="category_id.requirer_document")
    approval_minimum = fields.Integer(related="category_id.approval_minimum")
    is_manager_approver = fields.Boolean(related="category_id.is_manager_approver")

    def _compute_has_access_to_request(self):
        is_approval_user = self.env.user.has_group('approvals.group_approval_user')
        for request in self:
            request.has_access_to_request = request.request_owner_id == self.env.user and is_approval_user

    def _compute_attachment_number(self):
        domain = [('res_model', '=', 'approval.request'), ('res_id', 'in', self.ids)]
        attachment_data = self.env['ir.attachment'].read_group(domain, ['res_id'], ['res_id'])
        attachment = dict((data['res_id'], data['res_id_count']) for data in attachment_data)
        for request in self:
            request.attachment_number = attachment.get(request.id, 0)

    def action_get_attachment_view(self):
        self.ensure_one()
        res = self.env['ir.actions.act_window'].for_xml_id('base', 'action_attachment')
        res['domain'] = [('res_model', '=', 'approval.request'), ('res_id', 'in', self.ids)]
        res['context'] = {'default_res_model': 'approval.request', 'default_res_id': self.id}
        return res

    def action_confirm(self):
        if len(self.approver_ids) < self.approval_minimum:
            raise UserError(_("You have to add at least %s approvers to confirm your request.") % self.approval_minimum)
        if self.requirer_document == 'required' and not self.attachment_number:
            raise UserError(_("You have to attach at lease one document."))
        approvers = self.mapped('approver_ids').filtered(lambda approver: approver.status == 'new')
        approvers._create_activity()
        approvers.write({'status': 'pending'})
        self.write({'date_confirmed': fields.Datetime.now()})

    def _get_user_approval_activities(self, user):
        domain = [
            ('res_model', '=', 'approval.request'),
            ('res_id', 'in', self.ids),
            ('activity_type_id', '=', self.env.ref('approvals.mail_activity_data_approval').id),
            ('user_id', '=', user.id)
        ]
        activities = self.env['mail.activity'].search(domain)
        return activities

    def action_approve(self, approver=None):
        if not isinstance(approver, models.BaseModel):
            approver = self.mapped('approver_ids').filtered(
                lambda approver: approver.user_id == self.env.user
            )
        approver.write({'status': 'approved'})
        self.sudo()._get_user_approval_activities(user=self.env.user).action_feedback()

    def action_refuse(self, approver=None):
        if not isinstance(approver, models.BaseModel):
            approver = self.mapped('approver_ids').filtered(
                lambda approver: approver.user_id == self.env.user
            )
        approver.write({'status': 'refused'})
        self.sudo()._get_user_approval_activities(user=self.env.user).action_feedback()

    def action_withdraw(self, approver=None):
        if not isinstance(approver, models.BaseModel):
            approver = self.mapped('approver_ids').filtered(
                lambda approver: approver.user_id == self.env.user
            )
        approver.write({'status': 'pending'})

    def action_draft(self):
        self.mapped('approver_ids').write({'status': 'new'})

    def action_cancel(self):
        self.sudo()._get_user_approval_activities(user=self.env.user).unlink()
        self.mapped('approver_ids').write({'status': 'cancel'})

    @api.depends('approver_ids.status')
    def _compute_user_status(self):
        for approval in self:
            approval.user_status = approval.approver_ids.filtered(lambda approver: approver.user_id == self.env.user).status

    @api.depends('approver_ids.status')
    def _compute_request_status(self):
        for request in self:
            status_lst = request.mapped('approver_ids.status')
            minimal_approver = request.approval_minimum if len(status_lst) >= request.approval_minimum else len(status_lst)
            if status_lst:
                if status_lst.count('cancel'):
                    status = 'cancel'
                elif status_lst.count('refused'):
                    status = 'refused'
                elif status_lst.count('new'):
                    status = 'new'
                elif status_lst.count('approved') >= minimal_approver:
                    status = 'approved'
                else:
                    status = 'pending'
            else:
                status = 'new'
            request.request_status = status

    @api.onchange('category_id', 'request_owner_id')
    def _onchange_category_id(self):
        current_users = self.approver_ids.mapped('user_id')
        new_users = self.category_id.user_ids
        if self.category_id.is_manager_approver:
            employee = self.env['hr.employee'].search([('user_id', '=', self.request_owner_id.id)], limit=1)
            if employee.parent_id.user_id:
                new_users |= employee.parent_id.user_id
        for user in new_users - current_users:
            self.approver_ids += self.env['approval.approver'].new({
                'user_id': user.id,
                'request_id': self.id,
                'status': 'new'})

    def _write(self, values):
        # The attribute 'tracking' doesn't work for the
        # field request_status, as it is updated from the client side
        # We have to track the values modification by hand.
        if values.get('request_status'):
            # The compute method is already called and the new value is in cache.
            # We have to retrieve the correct old value from the database, as it is
            # stored computed field.
            self.env.cr.execute("""SELECT id, request_status FROM approval_request WHERE id IN %s""", (tuple(self.ids),))
            mapped_data = {data.get('id'): data.get('request_status') for data in self.env.cr.dictfetchall()}
            for request in self:
                old_value = mapped_data.get(request.id)
                if old_value != values['request_status']:
                    selection_description_values = {elem[0]: elem[1] for elem in self._fields['request_status']._description_selection(self.env)}
                    request._message_log(body=_('State change.'), tracking_value_ids=[(0, 0, {
                        'field': 'request_status',
                        'field_desc': 'Request Status',
                        'field_type': 'selection',
                        'old_value_char': selection_description_values.get(old_value),
                        'new_value_char': selection_description_values.get(values['request_status']),
                    })])
                    if request.request_owner_id:
                        request.message_notify(
                            partner_ids=request.request_owner_id.partner_id.ids,
                            body=_("Your request %s is now in the state %s") % (request.name, selection_description_values.get(values['request_status'])),
                            subject=request.name)
        return super(ApprovalRequest, self)._write(values)

class ApprovalApprover(models.Model):
    _name = 'approval.approver'
    _description = 'Approver'

    user_id = fields.Many2one('res.users', string="User", required=True)
    status = fields.Selection([
        ('new', 'New'),
        ('pending', 'To Approve'),
        ('approved', 'Approved'),
        ('refused', 'Refused'),
        ('cancel', 'Cancel')], string="Status", default="new", readonly=True)
    request_id = fields.Many2one('approval.request', string="Request", ondelete='cascade')

    def action_approve(self):
        self.request_id.action_approve(self)

    def action_refuse(self):
        self.request_id.action_refuse(self)

    def _create_activity(self):
        for approver in self:
            approver.request_id.activity_schedule(
                'approvals.mail_activity_data_approval',
                user_id=approver.user_id.id)

    @api.onchange('user_id')
    def _onchange_approver_ids(self):
        return {'domain': {'user_id': [('id', 'not in', self.request_id.approver_ids.mapped('user_id').ids + self.request_id.request_owner_id.ids)]}}
