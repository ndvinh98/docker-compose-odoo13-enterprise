# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrReferralAlert(models.Model):
    _name = 'hr.referral.alert'
    _description = 'Alert in Referral App'

    name = fields.Char(string='Alert', required=True)
    onclick = fields.Selection([
        ('no', 'Not Clickable'),
        ('all_jobs', 'Go to All Jobs'),
        ('url', 'Specify URL')
    ], string="On Click", default='no', required=True)
    url = fields.Char(string="URL",
        help="External links must start with 'http://www.'. For an internal url, you don't need to put domain name, you can just insert the path.")
    date_from = fields.Date()
    date_to = fields.Date()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
