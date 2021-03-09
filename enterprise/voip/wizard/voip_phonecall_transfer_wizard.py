# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from odoo.tools.translate import _


class VoipPhonecallTransferWizard(models.TransientModel):
    _name = 'voip.phonecall.transfer.wizard'
    _description = 'VOIP Transfer Wizard of Phonecalls'

    transfer_number = fields.Char('transfer To')
    transfer_choice = fields.Selection(selection=[
        ('physical', 'transfer to your external phone'),
        ('extern', 'transfer to another External Phone')
    ], default='physical', required=True)

    def save(self):
        if self.transfer_choice == 'extern':
            action = {
                'type': 'ir.actions.client',
                'tag': 'transfer_call',
                'params': {'number': self.transfer_number},
            }
        elif self.env.user.sip_external_phone:
                action = {
                    'type': 'ir.actions.client',
                    'tag': 'transfer_call',
                    'params': {'number': self.env.user.sip_external_phone},
                }
        else:
            action = {
                'warning': {
                    'title': _("Warning"),
                    'message': _("Wrong configuration for the call. There is no external phone number configured"),
                },
            }
        return action
