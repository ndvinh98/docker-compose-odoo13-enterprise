# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class AccountMove(models.Model):
    _inherit = "account.move"

    attachment_ids = fields.One2many('ir.attachment', 'res_id', domain=[('res_model', '=', 'account.move')], string='Attachments')


class AccountPayment(models.Model):
    _inherit = "account.payment"

    attachment_ids = fields.One2many('ir.attachment', 'res_id', domain=[('res_model', '=', 'account.payment')], string='Attachments')


class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement"

    attachment_ids = fields.One2many('ir.attachment', 'res_id', domain=[('res_model', '=', 'account.bank.statement')], string='Attachments')


class AccountMoveLine(models.Model):
    _name = "account.move.line"
    _inherit = "account.move.line"

    move_attachment_ids = fields.One2many('ir.attachment', compute='_compute_attachment')

    @api.depends('move_id', 'payment_id')
    def _compute_attachment(self):
        for record in self:
            record.move_attachment_ids = record.move_id.attachment_ids + record.statement_id.attachment_ids + record.payment_id.attachment_ids
