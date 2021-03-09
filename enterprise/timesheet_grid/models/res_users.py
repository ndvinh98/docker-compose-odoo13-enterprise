# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class User(models.Model):
    _inherit = ['res.users']

    timesheet_manager_id = fields.Many2one(related='employee_id.timesheet_manager_id')

    def __init__(self, pool, cr):
        """ Override of __init__ to add access rights.
            Access rights are disabled by default, but allowed
            on some specific fields defined in self.SELF_{READ/WRITE}ABLE_FIELDS.
        """
        init_res = super(User, self).__init__(pool, cr)
        # duplicate list to avoid modifying the original reference
        type(self).SELF_READABLE_FIELDS = ['timesheet_manager_id'] + type(self).SELF_READABLE_FIELDS
        return init_res
