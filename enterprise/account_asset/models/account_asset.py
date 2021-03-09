# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import calendar
from dateutil.relativedelta import relativedelta
from math import copysign

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero, float_round


class AccountAsset(models.Model):
    _name = 'account.asset'
    _description = 'Asset/Revenue Recognition'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    depreciation_entries_count = fields.Integer(compute='_entry_count', string='# Posted Depreciation Entries')
    gross_increase_count = fields.Integer(compute='_entry_count', string='# Gross Increases', help="Number of assets made to increase the value of the asset")
    total_depreciation_entries_count = fields.Integer(compute='_entry_count', string='# Depreciation Entries', help="Number of depreciation entries (posted or not)")

    name = fields.Char(string='Asset Name', required=True, readonly=True, states={'draft': [('readonly', False)], 'model': [('readonly', False)]})
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, readonly=True, states={'draft': [('readonly', False)]},
                                  default=lambda self: self.env.company.currency_id.id)
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True, states={'draft': [('readonly', False)]},
                                 default=lambda self: self.env.company)
    state = fields.Selection([('model', 'Model'), ('draft', 'Draft'), ('open', 'Running'), ('paused', 'On Hold'), ('close', 'Closed')], 'Status', copy=False, default='draft',
        help="When an asset is created, the status is 'Draft'.\n"
            "If the asset is confirmed, the status goes in 'Running' and the depreciation lines can be posted in the accounting.\n"
            "The 'On Hold' status can be set manually when you want to pause the depreciation of an asset for some time.\n"
            "You can manually close an asset when the depreciation is over. If the last line of depreciation is posted, the asset automatically goes in that status.")
    active = fields.Boolean(default=True)
    asset_type = fields.Selection([('sale', 'Sale: Revenue Recognition'), ('purchase', 'Purchase: Asset'), ('expense', 'Deferred Expense')], index=True, readonly=False, states={'draft': [('readonly', False)]})

    # Depreciation params
    method = fields.Selection([('linear', 'Linear'), ('degressive', 'Degressive'), ('degressive_then_linear', 'Accelerated Degressive')], string='Method', readonly=True, states={'draft': [('readonly', False)], 'model': [('readonly', False)]}, default='linear',
        help="Choose the method to use to compute the amount of depreciation lines.\n"
            "  * Linear: Calculated on basis of: Gross Value / Number of Depreciations\n"
            "  * Degressive: Calculated on basis of: Residual Value * Degressive Factor\n"
            "  * Accelerated Degressive: Like Degressive but with a minimum depreciation value equal to the linear value.")
    method_number = fields.Integer(string='Number of Depreciations', readonly=True, states={'draft': [('readonly', False)], 'model': [('readonly', False)]}, default=5, help="The number of depreciations needed to depreciate your asset")
    method_period = fields.Selection([('1', 'Months'), ('12', 'Years')], string='Number of Months in a Period', readonly=True, default='12', states={'draft': [('readonly', False)], 'model': [('readonly', False)]},
        help="The amount of time between two depreciations")
    method_progress_factor = fields.Float(string='Degressive Factor', readonly=True, default=0.3, states={'draft': [('readonly', False)], 'model': [('readonly', False)]})
    prorata = fields.Boolean(string='Prorata Temporis', readonly=True, states={'draft': [('readonly', False)], 'model': [('readonly', False)]},
        help='Indicates that the first depreciation entry for this asset have to be done from the asset date (purchase date) instead of the first January / Start date of fiscal year')
    prorata_date = fields.Date(
        string='Prorata Date',
        readonly=True, states={'draft': [('readonly', False)]})
    account_asset_id = fields.Many2one('account.account', string='Fixed Asset Account', compute='_compute_value', help="Account used to record the purchase of the asset at its original price.", store=True, states={'draft': [('readonly', False)], 'model': [('readonly', False)]}, domain="[('company_id', '=', company_id)]")
    account_depreciation_id = fields.Many2one('account.account', string='Depreciation Account', readonly=True, states={'draft': [('readonly', False)], 'model': [('readonly', False)]}, domain="[('internal_type', '=', 'other'), ('deprecated', '=', False), ('company_id', '=', company_id)]", help="Account used in the depreciation entries, to decrease the asset value.")
    account_depreciation_expense_id = fields.Many2one('account.account', string='Expense Account', readonly=True, states={'draft': [('readonly', False)], 'model': [('readonly', False)]}, domain="[('internal_type', '=', 'other'), ('deprecated', '=', False), ('company_id', '=', company_id)]", help="Account used in the periodical entries, to record a part of the asset as expense.")

    journal_id = fields.Many2one('account.journal', string='Journal', readonly=True, states={'draft': [('readonly', False)], 'model': [('readonly', False)]}, domain="[('type', '=', 'general'), ('company_id', '=', company_id)]")

    # Values
    original_value = fields.Monetary(string="Original Value", compute='_compute_value', inverse='_set_value', store=True, readonly=True, states={'draft': [('readonly', False)]})
    book_value = fields.Monetary(string='Book Value', readonly=True, compute='_compute_book_value', store=True, help="Sum of the depreciable value, the salvage value and the book value of all value increase items")
    value_residual = fields.Monetary(string='Depreciable Value', digits=0, readonly="1")
    salvage_value = fields.Monetary(string='Not Depreciable Value', digits=0, readonly=True, states={'draft': [('readonly', False)]},
                                    help="It is the amount you plan to have that you cannot depreciate.")
    gross_increase_value = fields.Monetary(string="Gross Increase Value", compute="_compute_book_value", compute_sudo=True)

    # Links with entries
    depreciation_move_ids = fields.One2many('account.move', 'asset_id', string='Depreciation Lines', readonly=True, states={'draft': [('readonly', False)], 'open': [('readonly', False)], 'paused': [('readonly', False)]})
    original_move_line_ids = fields.One2many('account.move.line', 'asset_id', string='Journal Items', readonly=True, states={'draft': [('readonly', False)]}, copy=False)

    # Analytic
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account', domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tag', domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    # Dates
    first_depreciation_date = fields.Date(
        string='First Depreciation Date',
        readonly=True, states={'draft': [('readonly', False)]}, required=True,
        help='Note that this date does not alter the computation of the first journal entry in case of prorata temporis assets. It simply changes its accounting date',
    )
    acquisition_date = fields.Date(readonly=True, states={'draft': [('readonly', False)]},)
    disposal_date = fields.Date(readonly=True, states={'draft': [('readonly', False)]}, compute="_compute_disposal_date", store=True)

    # model-related fields
    model_id = fields.Many2one('account.asset', string='Model', change_default=True, readonly=True, states={'draft': [('readonly', False)]}, domain="[('company_id', '=', company_id)]")
    user_type_id = fields.Many2one('account.account.type', related="account_asset_id.user_type_id", string="Type of the account")
    display_model_choice = fields.Boolean(compute="_compute_value", compute_sudo=True)
    display_account_asset_id = fields.Boolean(compute="_compute_value", compute_sudo=True)

    # Capital gain
    parent_id = fields.Many2one('account.asset', help="An asset has a parent when it is the result of gaining value")
    children_ids = fields.One2many('account.asset', 'parent_id', help="The children are the gains in value of this asset")

    @api.depends('depreciation_move_ids.date', 'state')
    def _compute_disposal_date(self):
        for asset in self:
            if asset.state == 'close':
                dates = asset.depreciation_move_ids.filtered(lambda m: m.date).mapped('date')
                asset.disposal_date = dates and max(dates)
            else:
                asset.disposal_date = False

    @api.depends('original_move_line_ids', 'original_move_line_ids.account_id', 'asset_type')
    def _compute_value(self):
        for record in self:
            misc_journal_id = self.env['account.journal'].search([('type', '=', 'general'), ('company_id', '=', record.company_id.id)], limit=1)
            if not record.original_move_line_ids:
                record.account_asset_id = record.account_asset_id or False
                record.original_value = record.original_value or False
                record.display_model_choice = record.state == 'draft' and self.env['account.asset'].search([('state', '=', 'model'), ('asset_type', '=', record.asset_type)])
                record.display_account_asset_id = True
                continue
            if any(line.move_id.state == 'draft' for line in record.original_move_line_ids):
                raise UserError(_("All the lines should be posted"))
            if any(account != record.original_move_line_ids[0].account_id for account in record.original_move_line_ids.mapped('account_id')):
                raise UserError(_("All the lines should be from the same account"))
            if any(type != record.original_move_line_ids[0].move_id.type for type in record.original_move_line_ids.mapped('move_id.type')):
                raise UserError(_("All the lines should be from the same move type"))
            record.account_asset_id = record.original_move_line_ids[0].account_id
            record.display_model_choice = record.state == 'draft' and len(self.env['account.asset'].search([('state', '=', 'model'), ('account_asset_id.user_type_id', '=', record.user_type_id.id)]))
            record.display_account_asset_id = False
            if not record.journal_id:
                record.journal_id = misc_journal_id
            total_credit = sum(line.credit for line in record.original_move_line_ids)
            total_debit = sum(line.debit for line in record.original_move_line_ids)
            record.original_value = total_credit + total_debit
            if (total_credit and total_debit) or record.original_value == 0:
                raise UserError(_("You cannot create an asset from lines containing credit and debit on the account or with a null amount"))

    def _set_value(self):
        for record in self:
            record.acquisition_date = min(record.original_move_line_ids.mapped('date') + [record.prorata_date or record.first_depreciation_date or fields.Date.today()] + [record.acquisition_date or fields.Date.today()])
            record.first_depreciation_date = record._get_first_depreciation_date()
            record.value_residual = record.original_value - record.salvage_value
            record.name = record.name or (record.original_move_line_ids and record.original_move_line_ids[0].name or '')
            if not record.asset_type and 'asset_type' in self.env.context:
                record.asset_type = self.env.context['asset_type']
            if not record.asset_type and record.original_move_line_ids:
                account = record.original_move_line_ids.account_id
                record.asset_type = account.asset_type
            record._onchange_depreciation_account()

    @api.depends('value_residual', 'salvage_value', 'children_ids.book_value')
    def _compute_book_value(self):
        for record in self:
            record.book_value = record.value_residual + record.salvage_value + sum(record.children_ids.mapped('book_value'))
            record.gross_increase_value = sum(record.children_ids.mapped('original_value'))

    @api.onchange('salvage_value')
    def _onchange_salvage_value(self):
        # When we are configuring the asset we dont want the book value to change
        # when we change the salvage value because of _compute_book_value
        # we need to reduce value_residual to do that
        self.value_residual = self.original_value - self.salvage_value

    @api.onchange('original_value')
    def _onchange_value(self):
        self._set_value()

    @api.onchange('method_period')
    def _onchange_method_period(self):
        self.first_depreciation_date = self._get_first_depreciation_date()

    @api.onchange('prorata')
    def _onchange_prorata(self):
        if self.prorata:
            self.prorata_date = fields.Date.today()

    @api.onchange('depreciation_move_ids')
    def _onchange_depreciation_move_ids(self):
        seq = 0
        asset_remaining_value = self.value_residual
        cumulated_depreciation = 0
        for m in self.depreciation_move_ids.sorted(lambda x: x.date):
            seq += 1
            if not m.reversal_move_id:
                asset_remaining_value -= m.amount_total
                cumulated_depreciation += m.amount_total
            if not m.asset_manually_modified:
                continue
            m.asset_manually_modified = False
            m.asset_remaining_value = asset_remaining_value
            m.asset_depreciated_value = cumulated_depreciation
            for older_move in self.depreciation_move_ids.sorted(lambda x: x.date)[seq:]:
                if not older_move.reversal_move_id:
                    asset_remaining_value -= older_move.amount_total
                    cumulated_depreciation += older_move.amount_total
                older_move.asset_remaining_value = asset_remaining_value
                older_move.asset_depreciated_value = cumulated_depreciation

    @api.onchange('account_depreciation_id')
    def _onchange_account_depreciation_id(self):
        """
        The field account_asset_id is required but invisible in the Deferred Revenue Model form.
        Therefore, set it when account_depreciation_id changes.
        """
        if self.asset_type in ('sale', 'expense') and self.state == 'model':
            self.account_asset_id = self.account_depreciation_id

    @api.onchange('account_asset_id')
    def _onchange_account_asset_id(self):
        self.display_model_choice = self.state == 'draft' and len(self.env['account.asset'].search([('state', '=', 'model'), ('user_type_id', '=', self.user_type_id.id)]))
        if self.asset_type in ('purchase', 'expense'):
            self.account_depreciation_id = self.account_depreciation_id or self.account_asset_id
        else:
            self.account_depreciation_expense_id = self.account_depreciation_expense_id or self.account_asset_id

    @api.onchange('account_depreciation_id', 'account_depreciation_expense_id')
    def _onchange_depreciation_account(self):
        if not self.original_move_line_ids and (self.state == 'model' or not self.account_asset_id or self.asset_type != 'purchase'):
            self.account_asset_id = self.account_depreciation_id if self.asset_type in ('purchase', 'expense') else self.account_depreciation_expense_id

    @api.onchange('model_id')
    def _onchange_model_id(self):
        model = self.model_id
        if model:
            self.method = model.method
            self.method_number = model.method_number
            self.method_period = model.method_period
            self.method_progress_factor = model.method_progress_factor
            self.prorata = model.prorata
            self.prorata_date = fields.Date.today()
            self.account_analytic_id = model.account_analytic_id.id
            self.analytic_tag_ids = [(6, 0, model.analytic_tag_ids.ids)]
            self.account_depreciation_id = model.account_depreciation_id
            self.account_depreciation_expense_id = model.account_depreciation_expense_id
            self.journal_id = model.journal_id

    @api.onchange('asset_type')
    def _onchange_type(self):
        if self.state != 'model':
            if self.asset_type == 'sale':
                self.prorata = True
                self.method_period = '1'
            else:
                self.method_period = '12'

    def _get_first_depreciation_date(self, vals={}):
        pre_depreciation_date = fields.Date.to_date(vals.get('acquisition_date') or vals.get('date') or min(self.original_move_line_ids.mapped('date'), default=self.acquisition_date or fields.Date.today()))
        depreciation_date = pre_depreciation_date + relativedelta(day=31)
        # ... or fiscalyear depending the number of period
        if '12' in (self.method_period, vals.get('method_period')):
            depreciation_date = depreciation_date + relativedelta(month=int(self.company_id.fiscalyear_last_month))
            depreciation_date = depreciation_date + relativedelta(day=self.company_id.fiscalyear_last_day)
            if depreciation_date < pre_depreciation_date:
                depreciation_date = depreciation_date + relativedelta(years=1)
        return depreciation_date

    def unlink(self):
        for asset in self:
            if asset.state in ['open', 'paused', 'close']:
                raise UserError(_('You cannot delete a document that is in %s state.') % dict(self._fields['state']._description_selection(self.env)).get(asset.state))
            for line in asset.original_move_line_ids:
                body = _('A document linked to %s has been deleted: ') % (line.name or _('this move'))
                body += '<a href=# data-oe-model=account.asset data-oe-id=%d>%s</a>' % (asset.id, asset.name)
                line.move_id.message_post(body=body)
        return super(AccountAsset, self).unlink()

    def _compute_board_amount(self, computation_sequence, residual_amount, total_amount_to_depr, max_depreciation_nb, starting_sequence, depreciation_date):
        amount = 0
        if computation_sequence == max_depreciation_nb:
            # last depreciation always takes the asset residual amount
            amount = residual_amount
        else:
            if self.method in ('degressive', 'degressive_then_linear'):
                amount = residual_amount * self.method_progress_factor
            if self.method in ('linear', 'degressive_then_linear'):
                nb_depreciation = max_depreciation_nb - starting_sequence
                if self.prorata:
                    nb_depreciation -= 1
                linear_amount = min(total_amount_to_depr / nb_depreciation, residual_amount)
                if self.method == 'degressive_then_linear':
                    amount = max(linear_amount, amount)
                else:
                    amount = linear_amount
        return amount

    def compute_depreciation_board(self):
        self.ensure_one()
        amount_change_ids = self.depreciation_move_ids.filtered(lambda x: x.asset_value_change and not x.reversal_move_id).sorted(key=lambda l: l.date)
        posted_depreciation_move_ids = self.depreciation_move_ids.filtered(lambda x: x.state == 'posted' and not x.asset_value_change and not x.reversal_move_id).sorted(key=lambda l: l.date)
        already_depreciated_amount = sum([m.amount_total for m in posted_depreciation_move_ids])
        depreciation_number = self.method_number
        if self.prorata:
            depreciation_number += 1
        starting_sequence = 0
        amount_to_depreciate = self.value_residual + sum([m.amount_total for m in amount_change_ids])
        depreciation_date = self.first_depreciation_date
        # if we already have some previous validated entries, starting date is last entry + method period
        if posted_depreciation_move_ids and posted_depreciation_move_ids[-1].date:
            last_depreciation_date = fields.Date.from_string(posted_depreciation_move_ids[-1].date)
            if last_depreciation_date > depreciation_date:  # in case we unpause the asset
                depreciation_date = last_depreciation_date + relativedelta(months=+int(self.method_period))
        commands = [(2, line_id.id, False) for line_id in self.depreciation_move_ids.filtered(lambda x: x.state == 'draft')]
        newlines = self._recompute_board(depreciation_number, starting_sequence, amount_to_depreciate, depreciation_date, already_depreciated_amount, amount_change_ids)
        newline_vals_list = []
        for newline_vals in newlines:
            # no need of amount field, as it is computed and we don't want to trigger its inverse function
            del(newline_vals['amount_total'])
            newline_vals_list.append(newline_vals)
        new_moves = self.env['account.move'].create(newline_vals_list)
        for move in new_moves:
            commands.append((4, move.id))
        return self.write({'depreciation_move_ids': commands})

    def _recompute_board(self, depreciation_number, starting_sequence, amount_to_depreciate, depreciation_date, already_depreciated_amount, amount_change_ids):
        self.ensure_one()
        residual_amount = amount_to_depreciate
        # Remove old unposted depreciation lines. We cannot use unlink() with One2many field
        move_vals = []
        prorata = self.prorata and not self.env.context.get("ignore_prorata")
        if amount_to_depreciate != 0.0:
            for asset_sequence in range(starting_sequence + 1, depreciation_number + 1):
                while amount_change_ids and amount_change_ids[0].date <= depreciation_date:
                    if not amount_change_ids[0].reversal_move_id:
                        residual_amount -= amount_change_ids[0].amount_total
                        amount_to_depreciate -= amount_change_ids[0].amount_total
                        already_depreciated_amount += amount_change_ids[0].amount_total
                    amount_change_ids[0].write({
                        'asset_remaining_value': float_round(residual_amount, precision_rounding=self.currency_id.rounding),
                        'asset_depreciated_value': amount_to_depreciate - residual_amount + already_depreciated_amount,
                    })
                    amount_change_ids -= amount_change_ids[0]
                amount = self._compute_board_amount(asset_sequence, residual_amount, amount_to_depreciate, depreciation_number, starting_sequence, depreciation_date)
                prorata_factor = 1
                move_ref = self.name + ' (%s/%s)' % (prorata and asset_sequence - 1 or asset_sequence, self.method_number)
                if prorata and asset_sequence == 1:
                    move_ref = self.name + ' ' + _('(prorata entry)')
                    first_date = self.prorata_date
                    if int(self.method_period) % 12 != 0:
                        month_days = calendar.monthrange(first_date.year, first_date.month)[1]
                        days = month_days - first_date.day + 1
                        prorata_factor = days / month_days
                    else:
                        total_days = (depreciation_date.year % 4) and 365 or 366
                        days = (self.company_id.compute_fiscalyear_dates(first_date)['date_to'] - first_date).days + 1
                        prorata_factor = days / total_days
                amount = self.currency_id.round(amount * prorata_factor)
                if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                    continue
                residual_amount -= amount

                move_vals.append(self.env['account.move']._prepare_move_for_asset_depreciation({
                    'amount': amount,
                    'asset_id': self,
                    'move_ref': move_ref,
                    'date': depreciation_date,
                    'asset_remaining_value': float_round(residual_amount, precision_rounding=self.currency_id.rounding),
                    'asset_depreciated_value': amount_to_depreciate - residual_amount + already_depreciated_amount,
                }))

                depreciation_date = depreciation_date + relativedelta(months=+int(self.method_period))
                # datetime doesn't take into account that the number of days is not the same for each month
                if (not self.prorata or self.env.context.get("ignore_prorata")) and int(self.method_period) % 12 != 0:
                    max_day_in_month = calendar.monthrange(depreciation_date.year, depreciation_date.month)[1]
                    depreciation_date = depreciation_date.replace(day=max_day_in_month)
        return move_vals

    @api.model
    def _get_views(self, type):
        form_view = self.env.ref('account_asset.view_account_asset_form')
        tree_view = self.env.ref('account_asset.view_account_asset_purchase_tree')
        if type == 'sale':
            form_view = self.env.ref('account_asset.view_account_asset_revenue_form')
            tree_view = self.env.ref('account_asset.view_account_asset_sale_tree')
        elif type == 'expense':
            form_view = self.env.ref('account_asset.view_account_asset_expense_form')
            tree_view = self.env.ref('account_asset.view_account_asset_expense_tree')
        return [[tree_view.id, "tree"], [form_view.id, "form"]]

    def action_asset_modify(self):
        """ Returns an action opening the asset modification wizard.
        """
        self.ensure_one()
        new_wizard = self.env['asset.modify'].create({
            'asset_id': self.id,
        })
        return {
            'name': _('Modify Asset'),
            'view_mode': 'form',
            'res_model': 'asset.modify',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_id': new_wizard.id,
            'context': self.env.context,
        }

    def action_asset_pause(self):
        """ Returns an action opening the asset pause wizard."""
        self.ensure_one()
        new_wizard = self.env['account.asset.pause'].create({
            'asset_id': self.id,
        })
        return {
            'name': _('Pause Asset'),
            'view_mode': 'form',
            'res_model': 'account.asset.pause',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_id': new_wizard.id,
        }

    def action_set_to_close(self):
        """ Returns an action opening the asset pause wizard."""
        self.ensure_one()
        new_wizard = self.env['account.asset.sell'].create({
            'asset_id': self.id,
        })
        return {
            'name': _('Sell Asset'),
            'view_mode': 'form',
            'res_model': 'account.asset.sell',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_id': new_wizard.id,
        }

    def action_save_model(self):
        form_ref = {
            'purchase': 'account_asset.view_account_asset_form',
            'sale': 'account_asset.view_account_asset_revenue_form',
            'expense': 'account_asset.view_account_asset_expense_form',
        }.get(self.asset_type)

        return {
            'name': _('Save model'),
            'views': [[self.env.ref(form_ref).id, "form"]],
            'res_model': 'account.asset',
            'type': 'ir.actions.act_window',
            'context': {
                'default_state': 'model',
                'default_account_asset_id': self.account_asset_id.id,
                'default_account_depreciation_id': self.account_depreciation_id.id,
                'default_account_depreciation_expense_id': self.account_depreciation_expense_id.id,
                'default_journal_id': self.journal_id.id,
                'default_method': self.method,
                'default_method_number': self.method_number,
                'default_method_period': self.method_period,
                'default_method_progress_factor': self.method_progress_factor,
                'default_prorata': self.prorata,
                'default_prorata_date': self.prorata_date,
                'default_analytic_tag_ids': [(6, 0, self.analytic_tag_ids.ids)],
                'original_asset': self.id,
            }
        }

    def open_entries(self):
        return {
            'name': _('Journal Entries'),
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'views': [(self.env.ref('account.view_move_tree').id, 'tree'), (False, 'form')],
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.depreciation_move_ids.ids)],
            'context': dict(self._context, create=False),
        }

    def open_related_entries(self):
        return {
            'name': _('Journal Items'),
            'view_mode': 'tree,form',
            'res_model': 'account.move.line',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.original_move_line_ids.ids)],
        }

    def open_increase(self):
        return {
            'name': _('Gross Increase'),
            'view_mode': 'tree,form',
            'res_model': 'account.asset',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.children_ids.ids)],
            'views': self.env['account.asset']._get_views(self.asset_type),
        }

    def validate(self):
        fields = [
            'method',
            'method_number',
            'method_period',
            'method_progress_factor',
            'salvage_value',
            'original_move_line_ids',
        ]
        ref_tracked_fields = self.env['account.asset'].fields_get(fields)
        self.write({'state': 'open'})
        for asset in self:
            tracked_fields = ref_tracked_fields.copy()
            if asset.method == 'linear':
                del(tracked_fields['method_progress_factor'])
            dummy, tracking_value_ids = asset._message_track(tracked_fields, dict.fromkeys(fields))
            asset_name = {
                'purchase': (_('Asset created'), _('An asset has been created for this move:')),
                'sale': (_('Deferred revenue created'), _('A deferred revenue has been created for this move:')),
                'expense': (_('Deferred expense created'), _('A deferred expense has been created for this move:')),
            }[asset.asset_type]
            msg = asset_name[1] + ' <a href=# data-oe-model=account.asset data-oe-id=%d>%s</a>' % (asset.id, asset.name)
            asset.message_post(body=asset_name[0], tracking_value_ids=tracking_value_ids)
            for move_id in asset.original_move_line_ids.mapped('move_id'):
                move_id.message_post(body=msg)
            if not asset.depreciation_move_ids:
                asset.compute_depreciation_board()
            asset._check_depreciations()
            asset.depreciation_move_ids.write({'auto_post': True})

    def _return_disposal_view(self, move_ids):
        name = _('Disposal Move')
        view_mode = 'form'
        if len(move_ids) > 1:
            name = _('Disposal Moves')
            view_mode = 'tree,form'
        return {
            'name': name,
            'view_mode': view_mode,
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_id': move_ids[0],
            'domain': [('id', 'in', move_ids)]
        }

    def _get_disposal_moves(self, invoice_line_ids, disposal_date):
        def get_line(asset, amount, account):
            return (0, 0, {
                'name': asset.name,
                'account_id': account.id,
                'debit': 0.0 if float_compare(amount, 0.0, precision_digits=prec) > 0 else -amount,
                'credit': amount if float_compare(amount, 0.0, precision_digits=prec) > 0 else 0.0,
                'analytic_account_id': account_analytic_id.id if asset.asset_type == 'sale' else False,
                'analytic_tag_ids': [(6, 0, analytic_tag_ids.ids)] if asset.asset_type == 'sale' else False,
                'currency_id': company_currency != current_currency and current_currency.id or False,
                'amount_currency': company_currency != current_currency and - 1.0 * asset.value_residual or 0.0,
            })

        move_ids = []
        assert len(self) == len(invoice_line_ids)
        for asset, invoice_line_id in zip(self, invoice_line_ids):
            if disposal_date < max(asset.depreciation_move_ids.filtered(lambda x: not x.reversal_move_id and x.state == 'posted').mapped('date') or [fields.Date.today()]):
                if invoice_line_id:
                    raise UserError('There are depreciation posted after the invoice date (%s).\nPlease revert them or change the date of the invoice.' % disposal_date)
                else:
                    raise UserError('There are depreciation posted in the future, please revert them.')
            account_analytic_id = asset.account_analytic_id
            analytic_tag_ids = asset.analytic_tag_ids
            company_currency = asset.company_id.currency_id
            current_currency = asset.currency_id
            prec = company_currency.decimal_places
            unposted_depreciation_move_ids = asset.depreciation_move_ids.filtered(lambda x: x.state == 'draft')
            if unposted_depreciation_move_ids:
                old_values = {
                    'method_number': asset.method_number,
                }

                # Remove all unposted depr. lines
                commands = [(2, line_id.id, False) for line_id in unposted_depreciation_move_ids]

                # Create a new depr. line with the residual amount and post it
                asset_sequence = len(asset.depreciation_move_ids) - len(unposted_depreciation_move_ids) + 1

                initial_amount = asset.original_value
                initial_account = asset.original_move_line_ids.account_id if len(asset.original_move_line_ids.account_id) == 1 else asset.account_asset_id
                depreciated_amount = copysign(sum(asset.depreciation_move_ids.filtered(lambda r: r.state == 'posted').mapped('amount_total')), -initial_amount)
                depreciation_account = asset.account_depreciation_id
                invoice_amount = copysign(invoice_line_id.price_subtotal, -initial_amount)
                invoice_account = invoice_line_id.account_id
                difference = -initial_amount - depreciated_amount - invoice_amount
                difference_account = asset.company_id.gain_account_id if difference > 0 else asset.company_id.loss_account_id
                line_datas = [(initial_amount, initial_account), (depreciated_amount, depreciation_account), (invoice_amount, invoice_account), (difference, difference_account)]
                if not invoice_line_id:
                    del line_datas[2]
                vals = {
                    'amount_total': current_currency._convert(asset.value_residual, company_currency, asset.company_id, disposal_date),
                    'asset_id': asset.id,
                    'ref': asset.name + ': ' + (_('Disposal') if not invoice_line_id else _('Sale')),
                    'asset_remaining_value': 0,
                    'asset_depreciated_value': max(asset.depreciation_move_ids.filtered(lambda x: x.state == 'posted'), key=lambda x: x.date, default=self.env['account.move']).asset_depreciated_value,
                    'date': disposal_date,
                    'journal_id': asset.journal_id.id,
                    'line_ids': [get_line(asset, amount, account) for amount, account in line_datas if account],
                }
                commands.append((0, 0, vals))
                asset.write({'depreciation_move_ids': commands, 'method_number': asset_sequence})
                tracked_fields = self.env['account.asset'].fields_get(['method_number'])
                changes, tracking_value_ids = asset._message_track(tracked_fields, old_values)
                if changes:
                    asset.message_post(body=_('Asset sold or disposed. Accounting entry awaiting for validation.'), tracking_value_ids=tracking_value_ids)
                move_ids += self.env['account.move'].search([('asset_id', '=', asset.id), ('state', '=', 'draft')]).ids

        return move_ids

    def set_to_close(self, invoice_line_id, date=None):
        self.ensure_one()
        disposal_date = date or fields.Date.today()
        if invoice_line_id and self.children_ids.filtered(lambda a: a.state in ('draft', 'open') or a.value_residual > 0):
            raise UserError(_("You cannot automate the journal entry for an asset that has a running gross increase. Please use 'Dispose' on the increase(s)."))
        full_asset = self + self.children_ids
        move_ids = full_asset._get_disposal_moves([invoice_line_id] * len(full_asset), disposal_date)
        full_asset.write({'state': 'close'})
        if move_ids:
            return self._return_disposal_view(move_ids)

    def set_to_draft(self):
        self.write({'state': 'draft'})

    def set_to_running(self):
        if self.depreciation_move_ids and not max(self.depreciation_move_ids, key=lambda m: m.date).asset_remaining_value == 0:
            self.env['asset.modify'].create({'asset_id': self.id, 'name': _('Reset to running')}).modify()
        self.write({'state': 'open'})

    def resume_after_pause(self):
        """ Sets an asset in 'paused' state back to 'open'.
        A Depreciation line is created automatically to remove  from the
        depreciation amount the proportion of time spent
        in pause in the current period.
        """
        self.ensure_one()
        return self.with_context(resume_after_pause=True).action_asset_modify()

    def pause(self, pause_date):
        """ Sets an 'open' asset in 'paused' state, generating first a depreciation
        line corresponding to the ratio of time spent within the current depreciation
        period before putting the asset in pause. This line and all the previous
        unposted ones are then posted.
        """
        self.ensure_one()

        all_lines_before_pause = self.depreciation_move_ids.filtered(lambda x: x.date <= pause_date)
        line_before_pause = all_lines_before_pause and max(all_lines_before_pause, key=lambda x: x.date)
        following_lines = self.depreciation_move_ids.filtered(lambda x: x.date > pause_date)
        if following_lines:
            if any(line.state == 'posted' for line in following_lines):
                raise UserError(_("You cannot pause an asset with posted depreciation lines in the future."))

            if self.prorata:
                first_following = min(following_lines, key=lambda x: x.date)
                depreciation_period_start = line_before_pause and line_before_pause.date or self.prorata_date or self.first_depreciation_date
                try:
                    time_ratio = ((pause_date - depreciation_period_start).days) / (first_following.date - depreciation_period_start).days
                    new_line = self._insert_depreciation_line(line_before_pause, first_following.amount_total * time_ratio, _("Asset paused"), pause_date)
                    if pause_date <= fields.Date.today():
                        new_line.post()
                except ZeroDivisionError:
                    pass

            self.write({'state': 'paused'})
            self.depreciation_move_ids.filtered(lambda x: x.state == 'draft').unlink()
            self.message_post(body=_("Asset paused"))
        else:
            raise UserError(_("Trying to pause an asset without any future depreciation line"))

    def _insert_depreciation_line(self, line_before, amount, label, depreciation_date):
        """ Inserts a new line in the depreciation board, shifting the sequence of
        all the following lines from one unit.
        :param line_before:     The depreciation line after which to insert the new line,
                                or none if the inserted line should take the first position.
        :param amount:          The depreciation amount of the new line.
        :param label:           The name to give to the new line.
        :param date:            The date to give to the new line.
        """
        self.ensure_one()
        moveObj = self.env['account.move']

        new_line = moveObj.create(moveObj._prepare_move_for_asset_depreciation({
            'amount': amount,
            'asset_id': self,
            'move_ref': self.name + ': ' + label,
            'date': depreciation_date,
            'asset_remaining_value': self.value_residual - amount,
            'asset_depreciated_value': line_before and (line_before.asset_depreciated_value + amount) or amount,
        }))
        return new_line

    @api.onchange('company_id')
    def _onchange_company_id(self):
        self.currency_id = self.company_id.currency_id.id

    @api.depends('depreciation_move_ids.state', 'parent_id')
    def _entry_count(self):
        for asset in self:
            res = self.env['account.move'].search_count([('asset_id', '=', asset.id), ('state', '=', 'posted'), ('reversal_move_id', '=', False)])
            asset.depreciation_entries_count = res or 0
            asset.total_depreciation_entries_count = len(asset.depreciation_move_ids)
            asset.gross_increase_count = len(asset.children_ids)

    def copy_data(self, default=None):
        if default is None:
            default = {}
        if self.state == 'model':
            default.update(state='model')
        default['name'] = self.name + _(' (copy)')
        default['account_asset_id'] = self.account_asset_id.id
        return super(AccountAsset, self).copy_data(default)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            original_move_line_ids = 'original_move_line_ids' in vals and self._check_original_move_line_ids(vals['original_move_line_ids'])
            if 'state' in vals and vals['state'] != 'draft' and not (set(vals) - set({'account_depreciation_id', 'account_depreciation_expense_id', 'journal_id'})):
                raise UserError(_("Some required values are missing"))
            if 'first_depreciation_date' not in vals:
                if 'acquisition_date' in vals:
                    vals['first_depreciation_date'] = self._get_first_depreciation_date(vals)
                elif original_move_line_ids and 'date' in original_move_line_ids[0]:
                    vals['first_depreciation_date'] = self._get_first_depreciation_date(original_move_line_ids[0])
                else:
                    vals['first_depreciation_date'] = self._get_first_depreciation_date()
            if self._context.get('import_file', False) and 'category_id' in vals:
                changed_vals = self.onchange_category_id_values(vals['category_id'])['value']
                # To avoid to overwrite vals explicitly set by the import
                [changed_vals.pop(key, None) for  key in vals.keys()]
                vals.update(changed_vals)
        with self.env.norecompute():
            new_recs = super(AccountAsset, self.with_context(mail_create_nolog=True)).create(vals_list)
            if self.env.context.get('original_asset'):
                # When original_asset is set, only one asset is created since its from the form view
                original_asset = self.env['account.asset'].browse(self.env.context.get('original_asset'))
                original_asset.model_id = new_recs
        if not self._context.get('import_file', False):
            new_recs.filtered(lambda r: r.state != 'model')._set_value()
        return new_recs

    def write(self, vals):
        'original_move_line_ids' in vals and self._check_original_move_line_ids(vals['original_move_line_ids'])
        res = super(AccountAsset, self).write(vals)
        return res

    @api.constrains('active', 'state')
    def _check_active(self):
        for record in self:
            if not record.active and record.state != 'close':
                raise UserError(_('You cannot archive a record that is not closed'))

    @api.constrains('depreciation_move_ids')
    def _check_depreciations(self):
        for record in self:
            if record.state == 'open' and record.depreciation_move_ids and not record.currency_id.is_zero(record.depreciation_move_ids.filtered(lambda x: not x.reversal_move_id).sorted(lambda x: (x.date, x.id))[-1].asset_remaining_value):
                raise UserError(_("The remaining value on the last depreciation line must be 0"))

    def _check_original_move_line_ids(self, original_move_line_ids):
        original_move_line_ids = self.resolve_2many_commands('original_move_line_ids', original_move_line_ids) or []
        if any(line.get('asset_id') for line in original_move_line_ids):
            raise UserError(_("One of the selected Journal Items already has a depreciation associated"))
        return original_move_line_ids
