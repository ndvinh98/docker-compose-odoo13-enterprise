# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FollowupSend(models.TransientModel):
    _name = 'followup.send'
    _description = 'Send Follow-ups'

    snailmail_cost = fields.Float(string='Stamp(s)', compute='_compute_snailmail_cost', readonly=True)
    letters_qty = fields.Integer(compute='_compute_letters_qty', string='Number of letters')
    partner_ids = fields.Many2many('res.partner', string='Recipients')
    invalid_addresses = fields.Integer('Invalid Addresses Count', compute='_compute_invalid_addresses')
    invalid_partner_ids = fields.Many2many('res.partner', string='Invalid Addresses', compute='_compute_invalid_addresses')

    @api.model
    def default_get(self, fields):
        res = super(FollowupSend, self).default_get(fields)
        res.update({'partner_ids': self._context.get('active_ids')})
        return res

    @api.depends('partner_ids')
    def _compute_invalid_addresses(self):
        for wizard in self:
            invalid_partner_addresses = wizard.partner_ids.filtered(lambda p: not self.env['snailmail.letter']._is_valid_address(p))
            wizard.invalid_partner_ids = invalid_partner_addresses
            wizard.invalid_addresses = len(invalid_partner_addresses)

    @api.depends('partner_ids')
    def _compute_letters_qty(self):
        for wizard in self:
            wizard.letters_qty = len(wizard.partner_ids)

    @api.depends('partner_ids')
    def _compute_snailmail_cost(self):
        for wizard in self:
            wizard.snailmail_cost = len(wizard.partner_ids.ids)

    def snailmail_send_action(self):
        for wizard in self:
            if wizard.invalid_addresses and len(wizard.partner_ids) > 1:
                wizard.notify_invalid_addresses()
            letters = self.env['snailmail.letter']
            for partner in self.partner_ids:
                letter = self.env['snailmail.letter'].create({
                    'partner_id': partner.id,
                    'model': 'res.partner',
                    'res_id': partner.id,
                    'user_id': self.env.user.id,
                    'report_template': self.env.ref('account_followup.action_report_followup').id,
                    # we will only process partners that are linked to the user current company
                    # TO BE CHECKED
                    'company_id': self.env.company.id,
                })
                letters |= letter

            if len(self.partner_ids) == 1:
                letters._snailmail_print()
            else:
                letters._snailmail_print(immediate=False)
        return {'type': 'ir.actions.act_window_close'}

    def notify_invalid_addresses(self):
        self.ensure_one()
        self.env['bus.bus'].sendone(
            (self._cr.dbname, 'res.partner', self.env.user.partner_id.id),
            {'type': 'snailmail_invalid_address', 'title': _("Invalid Addresses"),
                'message': _("%s of the selected partner(s) had an invalid address. The corresponding followups were not sent") % self.invalid_addresses}
        )

    def invalid_addresses_action(self):
        return {
            'name': _('Invalid Addresses'),
            'type': 'ir.actions.act_window',
            'view_mode': 'kanban,tree,form',
            'res_model': 'res.partner',
            'domain': [('id', 'in', self.mapped('invalid_partner_ids').ids)],
        }
