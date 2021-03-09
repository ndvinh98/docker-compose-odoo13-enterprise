# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, tools


class VoipPhonecallReport(models.Model):
    _name = "voip.phonecall.report"
    _description = "VOIP Phonecalls by user report"
    _auto = False

    user_id = fields.Many2one('res.users', 'Responsible', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Contact', readonly=True)
    duration = fields.Float('Duration', digits=(16, 2), group_operator="avg", readonly=True)
    state = fields.Selection([
        ('pending', 'Not Held'),
        ('cancel', 'Cancelled'),
        ('open', 'To Do'),
        ('done', 'Held')
    ], 'Status', readonly=True)
    call_date = fields.Datetime('Date', readonly=True, index=True)
    nbr = fields.Integer('# of Cases', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self._cr, 'voip_phonecall_report')
        self._cr.execute("""
            create or replace view voip_phonecall_report as (
                select
                    id,
                    c.user_id,
                    c.duration,
                    1 as nbr,
                    c.call_date
                from
                    voip_phonecall c
                where
                    c.state = 'done'
            )""")
