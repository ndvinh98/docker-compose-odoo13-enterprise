# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class VoipQueueMixin(models.AbstractModel):
    _name = 'voip.queue.mixin'
    _description = 'Add voip queue support to a model'
    has_call_in_queue = fields.Boolean("Is in the Call Queue", compute='_compute_has_call_in_queue')

    def _compute_has_call_in_queue(self):
        domain = self._linked_phone_call_domain()
        call_per_id = {call.activity_id.res_id: True for call in self.env['voip.phonecall'].search(domain)}
        for rec in self:
            rec.has_call_in_queue = call_per_id.get(rec.id, False)

    def _linked_phone_call_domain(self):
        return [
            ('activity_id.res_id', 'in', self.ids),
            ('activity_id.res_model_id', '=', self.env['ir.model']._get(self._name).id),
            ('date_deadline', '<=', fields.Date.today(self)),  # TODO check if correct
            ('in_queue', '=', True),
            ('state', '!=', 'done'),
            ('user_id', '=', self.env.user.id)
        ]

    def create_call_in_queue(self):
        # creating an activity of type phonecall will automaticaly create a voip.phonecall
        # will only work if _compute_phonenumbers gives a resul
        phonecall_activity_type = self.env.ref('mail.mail_activity_data_call')
        if phonecall_activity_type.category != 'phonecall':
            raise UserError(_('Call activity type is not of category "phonecall"'))

        values_list = [{
            'res_id': record.id,
            'res_model_id': self.env['ir.model']._get(record._name).id,
            'activity_type_id': phonecall_activity_type.id,
            'user_id': self.env.user.id,
            'date_deadline': fields.Date.today(self),
        } for record in self]
        activities = self.env['mail.activity'].create(values_list)
        for activity in activities:
            if not activity.voip_phonecall_id:
                record = self.env[activity.res_model_id.model].browse(activity.res_id)
                raise UserError(_('Phone call cannot be created. Is it any phone number linked to record %s?' % record.name))

    def delete_call_in_queue(self):
        domain = self._linked_phone_call_domain()
        phonecalls = self.env['voip.phonecall'].search(domain)
        for phonecall in phonecalls:
            phonecall.remove_from_queue()
        self.env['bus.bus'].sendone(
            (self._cr.dbname, 'res.partner', self.env.user.id),
            {'type': 'refresh_voip'}
        )
