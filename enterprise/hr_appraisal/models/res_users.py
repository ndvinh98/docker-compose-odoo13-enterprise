# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class User(models.Model):
    _inherit = ['res.users']

    appraisal_by_manager = fields.Boolean(compute='_compute_appraisal_by_manager')
    appraisal_manager_ids = fields.Many2many('hr.employee', compute='_compute_appraisal_manager_ids')
    appraisal_self = fields.Boolean(compute='_compute_appraisal_self', string="Employee Himself")
    appraisal_by_collaborators = fields.Boolean(compute='_compute_appraisal_by_collaborators')
    appraisal_collaborators_ids = fields.Many2many('hr.employee', compute='_compute_appraisal_collaborators_ids')
    appraisal_by_colleagues = fields.Boolean(compute='_compute_appraisal_by_colleagues')
    appraisal_colleagues_ids = fields.Many2many('hr.employee', compute='_compute_appraisal_colleagues_ids')
    appraisal_date = fields.Date(compute='_compute_appraisal_date')

    @api.depends('employee_ids.appraisal_by_manager')
    def _compute_appraisal_by_manager(self):
        for user in self:
            user.appraisal_by_manager = user.employee_id.appraisal_by_manager

    @api.depends('employee_ids.appraisal_manager_ids')
    def _compute_appraisal_manager_ids(self):
        for user in self:
            user.appraisal_manager_ids = user.employee_id.appraisal_manager_ids

    @api.depends('employee_ids.appraisal_self')
    def _compute_appraisal_self(self):
        for user in self:
            user.appraisal_self = user.employee_id.appraisal_self

    @api.depends('employee_ids.appraisal_by_collaborators')
    def _compute_appraisal_by_collaborators(self):
        for user in self:
            user.appraisal_by_collaborators = user.employee_id.appraisal_by_collaborators

    @api.depends('employee_ids.appraisal_collaborators_ids')
    def _compute_appraisal_collaborators_ids(self):
        for user in self:
            user.appraisal_collaborators_ids = user.employee_id.appraisal_collaborators_ids

    @api.depends('employee_ids.appraisal_by_colleagues')
    def _compute_appraisal_by_colleagues(self):
        for user in self:
            user.appraisal_by_colleagues = user.employee_id.appraisal_by_colleagues

    @api.depends('employee_ids.appraisal_colleagues_ids')
    def _compute_appraisal_colleagues_ids(self):
        for user in self:
            user.appraisal_colleagues_ids = user.employee_id.appraisal_colleagues_ids

    @api.depends('employee_ids.appraisal_date')
    def _compute_appraisal_date(self):
        for user in self:
            user.appraisal_date = user.employee_id.appraisal_date

    def __init__(self, pool, cr):
        """ Override of __init__ to add access rights.
            Access rights are disabled by default, but allowed
            on some specific fields defined in self.SELF_{READ/WRITE}ABLE_FIELDS.
        """
        appraisal_readable_fields = [
            'appraisal_by_manager',
            'appraisal_manager_ids',
            'appraisal_self',
            'appraisal_by_collaborators',
            'appraisal_collaborators_ids',
            'appraisal_by_colleagues',
            'appraisal_colleagues_ids',
            'appraisal_date',
        ]
        init_res = super(User, self).__init__(pool, cr)
        # duplicate list to avoid modifying the original reference
        type(self).SELF_READABLE_FIELDS = appraisal_readable_fields + type(self).SELF_READABLE_FIELDS
        return init_res

    def action_send_appraisal_request(self):
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'request.appraisal',
            'target': 'new',
            'name': 'Appraisal Request',
            'context': self.env.context,
        }
