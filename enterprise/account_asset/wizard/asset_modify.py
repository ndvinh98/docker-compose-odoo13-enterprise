# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AssetModify(models.TransientModel):
    _name = 'asset.modify'
    _description = 'Modify Asset'

    name = fields.Text(string='Reason')
    asset_id = fields.Many2one(string="Asset", comodel_name='account.asset', required=True, help="The asset to be modified by this wizard", ondelete="cascade")
    method_number = fields.Integer(string='Number of Depreciations', required=True)
    method_period = fields.Selection([('1', 'Months'), ('12', 'Years')], string='Number of Months in a Period', help="The amount of time between two depreciations")
    value_residual = fields.Monetary(string="Depreciable Amount", help="New residual amount for the asset")
    salvage_value = fields.Monetary(string="Not Depreciable Amount", help="New salvage amount for the asset")
    currency_id = fields.Many2one(related='asset_id.currency_id')
    date = fields.Date(default=fields.Date.today(), string='Date')
    need_date = fields.Boolean(compute="_compute_need_date")
    gain_value = fields.Boolean(compute="_compute_gain_value", help="Technical field to know if we should display the fields for the creation of gross increase asset")
    account_asset_id = fields.Many2one('account.account', string="Asset Gross Increase Account")
    account_asset_counterpart_id = fields.Many2one('account.account')
    account_depreciation_id = fields.Many2one('account.account')
    account_depreciation_expense_id = fields.Many2one('account.account')

    @api.model
    def create(self, vals):
        if 'asset_id' in vals:
            asset = self.env['account.asset'].browse(vals['asset_id'])
            if asset.depreciation_move_ids.filtered(lambda m: m.state == 'posted' and not m.reversal_move_id and m.date > fields.Date.today()):
                raise UserError(_('Reverse the depreciation entries posted in the future in order to modify the depreciation'))
            if 'method_number' not in vals:
                vals.update({'method_number': len(asset.depreciation_move_ids.filtered(lambda move: move.state != 'posted')) or 1})
            if 'method_period' not in vals:
                vals.update({'method_period': asset.method_period})
            if 'salvage_value' not in vals:
                vals.update({'salvage_value': asset.salvage_value})
            if 'value_residual' not in vals:
                vals.update({'value_residual': asset.value_residual})
            if 'account_asset_id' not in vals:
                vals.update({'account_asset_id': asset.account_asset_id.id})
            if 'account_depreciation_id' not in vals:
                vals.update({'account_depreciation_id': asset.account_depreciation_id.id})
            if 'account_depreciation_expense_id' not in vals:
                vals.update({'account_depreciation_expense_id': asset.account_depreciation_expense_id.id})
        return super(AssetModify, self).create(vals)

    def modify(self):
        """ Modifies the duration of asset for calculating depreciation
        and maintains the history of old values, in the chatter.
        """
        old_values = {
            'method_number': self.asset_id.method_number,
            'method_period': self.asset_id.method_period,
            'value_residual': self.asset_id.value_residual,
            'salvage_value': self.asset_id.salvage_value,
        }

        asset_vals = {
            'method_number': self.method_number,
            'method_period': self.method_period,
            'value_residual': self.value_residual,
            'salvage_value': self.salvage_value,
        }
        if self.need_date:
            asset_vals.update({
                'first_depreciation_date': self.asset_id._get_first_depreciation_date(),
                'prorata_date': self.date,
            })
        if self.env.context.get('resume_after_pause'):
            asset_vals.update({'state': 'open'})
            self.asset_id.message_post(body=_("Asset unpaused"))
        else:
            self = self.with_context(ignore_prorata=True)

        current_asset_book = self.asset_id.value_residual + self.asset_id.salvage_value
        after_asset_book = self.value_residual + self.salvage_value
        increase = after_asset_book - current_asset_book

        new_residual = min(current_asset_book - min(self.salvage_value, self.asset_id.salvage_value), self.value_residual)
        new_salvage = min(current_asset_book - new_residual, self.salvage_value)
        residual_increase = max(0, self.value_residual - new_residual)
        salvage_increase = max(0, self.salvage_value - new_salvage)

        if residual_increase or salvage_increase:
            move = self.env['account.move'].create({
                'journal_id': self.asset_id.journal_id.id,
                'date': fields.Date.today(),
                'line_ids': [
                    (0, 0, {
                        'account_id': self.account_asset_id.id,
                        'debit': residual_increase + salvage_increase,
                        'credit': 0,
                        'name': _('Value increase for: ') + self.asset_id.name,
                    }),
                    (0, 0, {
                        'account_id': self.account_asset_counterpart_id.id,
                        'debit': 0,
                        'credit': residual_increase + salvage_increase,
                        'name': _('Value increase for: ') + self.asset_id.name,
                    }),
                ],
            })
            move.post()
            asset_increase = self.env['account.asset'].create({
                'name': self.asset_id.name + ': ' + self.name,
                'currency_id': self.asset_id.currency_id.id,
                'company_id': self.asset_id.company_id.id,
                'asset_type': self.asset_id.asset_type,
                'method': self.asset_id.method,
                'method_number': self.method_number,
                'method_period': self.method_period,
                'acquisition_date': self.date,
                'value_residual': residual_increase,
                'salvage_value': salvage_increase,
                'original_value': residual_increase + salvage_increase,
                'account_asset_id': self.account_asset_id.id,
                'account_depreciation_id': self.account_depreciation_id.id,
                'account_depreciation_expense_id': self.account_depreciation_expense_id.id,
                'journal_id': self.asset_id.journal_id.id,
                'parent_id': self.asset_id.id,
                'original_move_line_ids': [(6, 0, move.line_ids.filtered(lambda r: r.account_id == self.account_asset_id).ids)],
            })
            asset_increase.validate()

            subject = _('A gross increase has been created') + ': <a href=# data-oe-model=account.asset data-oe-id=%d>%s</a>' % (asset_increase.id, asset_increase.name)
            self.asset_id.message_post(body=subject)
        if increase < 0:
            if self.env['account.move'].search([('asset_id', '=', self.asset_id.id), ('state', '=', 'draft'), ('date', '<=', self.date)]):
                raise UserError('There are unposted depreciations prior to the selected operation date, please deal with them first.')
            move = self.env['account.move'].create(self.env['account.move']._prepare_move_for_asset_depreciation({
                'amount': -increase,
                'asset_id': self.asset_id,
                'move_ref': _('Value decrease for: ') + self.asset_id.name,
                'date': self.date,
                'asset_remaining_value': 0,
                'asset_depreciated_value': 0,
                'asset_value_change': True,
            })).post()

        asset_vals.update({
            'value_residual': new_residual,
            'salvage_value': new_salvage,
        })
        self.asset_id.write(asset_vals)
        self.asset_id.compute_depreciation_board()
        self.asset_id.children_ids.write({
            'method_number': asset_vals['method_number'],
            'method_period': asset_vals['method_period'],
        })
        for child in self.asset_id.children_ids:
            child.compute_depreciation_board()
        tracked_fields = self.env['account.asset'].fields_get(old_values.keys())
        changes, tracking_value_ids = self.asset_id._message_track(tracked_fields, old_values)
        if changes:
            self.asset_id.message_post(body=_('Depreciation board modified') + '<br>' + self.name, tracking_value_ids=tracking_value_ids)
        return {'type': 'ir.actions.act_window_close'}

    @api.depends('asset_id', 'value_residual', 'salvage_value')
    def _compute_need_date(self):
        for record in self:
            value_changed = self.value_residual + self.salvage_value != self.asset_id.value_residual + self.asset_id.salvage_value
            record.need_date = (self.env.context.get('resume_after_pause') and record.asset_id.prorata) or value_changed

    @api.depends('asset_id', 'value_residual', 'salvage_value')
    def _compute_gain_value(self):
        for record in self:
            record.gain_value = self.value_residual + self.salvage_value > self.asset_id.value_residual + self.asset_id.salvage_value
