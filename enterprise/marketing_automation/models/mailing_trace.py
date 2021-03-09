# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class MailingTrace(models.Model):
    _inherit = 'mailing.trace'

    marketing_trace_id = fields.Many2one(
        'marketing.trace', string='Marketing Trace',
        index=True, ondelete='cascade')

    def set_clicked(self, mail_mail_ids=None, mail_message_ids=None):
        traces = super(MailingTrace, self).set_clicked(mail_mail_ids=mail_mail_ids, mail_message_ids=mail_message_ids)
        for marketing_trace in traces.mapped('marketing_trace_id'):
            marketing_trace.process_event('mail_click')
        return traces

    def set_opened(self, mail_mail_ids=None, mail_message_ids=None):
        traces = super(MailingTrace, self).set_opened(mail_mail_ids=mail_mail_ids, mail_message_ids=mail_message_ids)
        for marketing_trace in traces.mapped('marketing_trace_id'):
            marketing_trace.process_event('mail_open')
        return traces

    def set_replied(self, mail_mail_ids=None, mail_message_ids=None):
        traces = super(MailingTrace, self).set_replied(mail_mail_ids=mail_mail_ids, mail_message_ids=mail_message_ids)
        for marketing_trace in traces.mapped('marketing_trace_id'):
            marketing_trace.process_event('mail_reply')
        return traces

    def set_bounced(self, mail_mail_ids=None, mail_message_ids=None):
        traces = super(MailingTrace, self).set_bounced(mail_mail_ids=mail_mail_ids, mail_message_ids=mail_message_ids)
        for marketing_trace in traces.mapped('marketing_trace_id'):
            marketing_trace.process_event('mail_bounce')
        return traces
