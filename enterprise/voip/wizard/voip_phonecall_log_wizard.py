# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta

from odoo import models, fields, api


class VoipPhonecallLogWizard(models.TransientModel):
    _name = 'voip.phonecall.log.wizard'
    _description = 'VOIP Phonecall log Wizard'

    phonecall_id = fields.Many2one('voip.phonecall', 'Logged Phonecall', readonly=True)
    activity_id = fields.Many2one('mail.activity', 'Linked Activity', readonly=True)
    summary = fields.Char('Summary')
    note = fields.Html('Note')
    reschedule_option = fields.Selection([
        ('no_reschedule', "Don't Reschedule"),
        ('1d', 'Tomorrow'),
        ('7d', 'In 1 Week'),
        ('15d', 'In 15 Day'),
        ('2m', 'In 2 Months'),
        ('custom', 'Specific Date')
    ], 'Schedule A New Activity', required=True, default="no_reschedule")
    reschedule_date = fields.Datetime(
        string='Specific Date',
        default=lambda *a: datetime.now() + timedelta(hours=2))

    def _schedule_new_activity(self):
        self.ensure_one()
        new_activity = self.activity_id.copy()
        if self.reschedule_option == "7d":
            new_activity.date_deadline = datetime.now() + timedelta(weeks=1)
        elif self.reschedule_option == "1d":
            new_activity.date_deadline = datetime.now() + timedelta(days=1)
        elif self.reschedule_option == "15d":
            new_activity.date_deadline = datetime.now() + timedelta(days=15)
        elif self.reschedule_option == "2m":
            new_activity.date_deadline = datetime.now() + timedelta(weeks=8)
        elif self.reschedule_option == "custom":
            new_activity.date_deadline = self.reschedule_date
        new_activity.voip_phonecall_id.date_deadline = new_activity.date_deadline

    def action_done(self):
        self.ensure_one()
        self.activity_id.write({
            'summary': self.summary,
            'note': self.note,
        })
        if (self.reschedule_option != "no_reschedule"):
            self._schedule_new_activity()
        phonecall = self.activity_id.voip_phonecall_id
        self.activity_id.action_done()
        phonecall.in_queue = True
        phonecall.trigger_voip_refresh()
        return
