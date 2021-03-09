# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from odoo import fields, models, tools
from odoo.modules.module import get_module_resource


CATEGORY_SELECTION = [
    ('required', 'Required'),
    ('optional', 'Optional'),
    ('no', 'None')]


class ApprovalCategory(models.Model):
    _name = 'approval.category'
    _description = 'Approval Category'
    _order = 'sequence'

    def _get_default_image(self):
        default_image_path = get_module_resource('approvals', 'static/src/img', 'clipboard-check-solid.svg')
        return base64.b64encode(open(default_image_path, 'rb').read())

    name = fields.Char(string="Name", translate=True, required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(string="Sequence")
    description = fields.Char(string="Description", translate=True)
    image = fields.Binary(string='Image', default=_get_default_image)
    has_date = fields.Selection(CATEGORY_SELECTION, string="Has Date", default="no", required=True)
    has_period = fields.Selection(CATEGORY_SELECTION, string="Has Period", default="no", required=True)
    has_item = fields.Selection(
        CATEGORY_SELECTION, string="Has Item", default="no", required=True,
        help="Additional items that should be specified on the request.")
    has_quantity = fields.Selection(CATEGORY_SELECTION, string="Has Quantity", default="no", required=True)
    has_amount = fields.Selection(CATEGORY_SELECTION, string="Has Amount", default="no", required=True)
    has_reference = fields.Selection(
        CATEGORY_SELECTION, string="Has Reference", default="no", required=True,
        help="An additional reference that should be specified on the request.")
    has_partner = fields.Selection(CATEGORY_SELECTION, string="Has Contact", default="no", required=True)
    has_payment_method = fields.Selection(CATEGORY_SELECTION, string="Has Payment", default="no", required=True)
    has_location = fields.Selection(CATEGORY_SELECTION, string="Has Location", default="no", required=True)
    requirer_document = fields.Selection([('required', 'Required'), ('optional', 'Optional')], string="Documents", default="optional", required=True)
    approval_minimum = fields.Integer(string="Minimum Approval", default="1", required=True)
    is_manager_approver = fields.Boolean(
        string="Employee's Manager",
        help="Automatically add the manager as approver on the request.")
    user_ids = fields.Many2many('res.users', string="Approvers")
    request_to_validate_count = fields.Integer("Number of requests to validate", compute="_compute_request_to_validate_count")

    def _compute_request_to_validate_count(self):
        domain = [('request_status', '=', 'pending'), ('approver_ids.user_id', '=', self.env.user.id)]
        requests_data = self.env['approval.request'].read_group(domain, ['category_id'], ['category_id'])
        requests_mapped_data = dict((data['category_id'][0], data['category_id_count']) for data in requests_data)
        for category in self:
            category.request_to_validate_count = requests_mapped_data.get(category.id, 0)

    def create_request(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "approval.request",
            "views": [[False, "form"]],
            "context": {
                'form_view_initial_mode': 'edit',
                'default_name': self.name,
                'default_category_id': self.id,
                'default_request_owner_id': self.env.user.id,
                'default_request_status': 'new'
            },
        }
