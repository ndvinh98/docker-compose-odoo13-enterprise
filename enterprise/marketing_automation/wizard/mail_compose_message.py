# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    marketing_activity_id = fields.Many2one('marketing.activity', string='Marketing Activity')

    def get_mail_values(self, res_ids):
        """ Override method to link mail automation activity with mail statistics"""
        res = super(MailComposeMessage, self).get_mail_values(res_ids)

        if self.composition_mode == 'mass_mail' and (self.mass_mailing_name or self.mass_mailing_id) and self.marketing_activity_id:
            # retrieve trace linked to recipient
            traces = self.env['marketing.trace'].search([('activity_id', '=', self.marketing_activity_id.id), ('res_id', 'in', res_ids)])
            traces_mapping = dict((trace.res_id, trace.id) for trace in traces)

            # update statistics creation done in mass_mailing to include link between stat and trace
            for res_id in res_ids:
                mail_values = res[res_id]
                traces_command = mail_values.get('mailing_trace_ids')  # [(0, 0, stat_vals)]
                if traces_command and len(traces_command[0]) == 3:
                    statistics_dict = traces_command[0][2]
                    if traces_mapping.get(res_id):
                        statistics_dict['marketing_trace_id'] = traces_mapping[res_id]

        return res
