# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class MailActivityType(models.Model):
    _inherit = 'mail.activity.type'

    category = fields.Selection(selection_add=[('phonecall', 'Phonecall')])


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    phone = fields.Char('Phone')
    mobile = fields.Char('Mobile')
    voip_phonecall_id = fields.Many2one('voip.phonecall', 'Linked Voip Phonecall')

    @api.model_create_multi
    def create(self, values_list):
        activities = super(MailActivity, self).create(values_list)
        user_to_notify = set()
        for activity in activities:
            if activity.activity_type_id.category == 'phonecall':
                numbers = activity._compute_phonenumbers()
                if numbers['phone'] or numbers['mobile']:
                    user_to_notify.add(activity.user_id)
                    activity.phone = numbers['phone']
                    activity.mobile = numbers['mobile']
                    phonecall = self.env['voip.phonecall'].create_from_activity(activity)
                    activity.voip_phonecall_id = phonecall.id
        for user in user_to_notify:
            self.env['bus.bus'].sendone(
                (self._cr.dbname, 'res.partner', user.partner_id.id),
                {'type': 'refresh_voip'}
            )
        return activities

    def write(self, values):
        if 'date_deadline' in values:
            self.mapped('voip_phonecall_id').write({'date_deadline': values['date_deadline']})
            for user in self.mapped('user_id'):
                self.env['bus.bus'].sendone(
                    (self._cr.dbname, 'res.partner', user.partner_id.id),
                    {'type': 'refresh_voip'}
                )
        return super(MailActivity, self).write(values)

    def _compute_phonenumbers(self):
        self.ensure_one()
        model = self.env[self.res_model]
        record = model.browse(self.res_id)
        numbers = {
            'phone': False,
            'mobile': False,
        }
        if 'phone' in record:
            numbers['phone'] = record.phone
        if 'mobile' in record:
            numbers['mobile'] = record.mobile
        if not numbers['phone'] and not numbers['mobile']:
            fields = model._fields.items()
            partner_field_name = [k for k, v in fields if v.type == 'many2one' and v.comodel_name == 'res.partner']
            if partner_field_name:
                numbers['phone'] = record[partner_field_name[0]].phone
                numbers['mobile'] = record[partner_field_name[0]].mobile
        return numbers

    def _action_done(self, feedback=False, attachment_ids=None):
        # extract potential required data to update phonecalls
        phonecall_values_to_keep = {}  # mapping index of self and acitivty value to keep {index: {key1: value1, key2: value2}}
        for index, activity in enumerate(self):
            if activity.voip_phonecall_id:
                phonecall_values_to_keep[index] = {
                    'note': activity.note,
                    'voip_phonecall_id': activity.voip_phonecall_id,
                    'call_date': activity.voip_phonecall_id.call_date,
                    'partner_id': activity.user_id.partner_id.id
                }

        # call super, and unlink `self`
        messages, activities = super(MailActivity, self)._action_done(feedback=feedback, attachment_ids=attachment_ids)

        # update phonecalls and broadcast refresh notifications on bus
        if phonecall_values_to_keep:
            bus_notifications = []
            for index, message in enumerate(messages):
                if index in phonecall_values_to_keep:
                    values_to_keep = phonecall_values_to_keep[index]
                    phonecall = values_to_keep['voip_phonecall_id']
                    values_to_write = {
                        'state': 'done',
                        'mail_message_id': message.id,
                        'note': feedback if feedback else values_to_keep['note'],
                    }
                    if not values_to_keep['call_date']:
                        values_to_write['call_date'] = fields.Datetime.now()
                    phonecall.write(values_to_write)

                    bus_notifications.append([(self._cr.dbname, 'res.partner', values_to_keep['partner_id']), {'type': 'refresh_voip'}])

            self.env['bus.bus'].sendmany(bus_notifications)

        return messages, activities
