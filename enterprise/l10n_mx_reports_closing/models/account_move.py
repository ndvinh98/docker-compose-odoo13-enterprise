# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_mx_closing_move = fields.Boolean(
        string='Closing move',
        help='Journal Entry closing the fiscal year.', readonly=True, default=False)

    def _get_closing_move(self, search_date):
        company_id = self.env.context.get('company_id') or self.env.company
        company_fiscalyear_dates = company_id.compute_fiscalyear_dates(
            search_date)
        return self.env['account.move'].search(
            [('company_id', '=', company_id.id),
             ('l10n_mx_closing_move', '=', 'True'),
             ('date', '>=', company_fiscalyear_dates['date_from']),
             ('date', '<=', company_fiscalyear_dates['date_to']),
             ('state', '=', 'posted')])

    def action_mark_as_closing_move(self):
        """ Mark the current entry, as the closing entry for the fiscal year.
        Remove any previous mark from another entry for the same fiscal year. """

        self.ensure_one()
        existing_closing_move = self._get_closing_move(self.date)
        existing_closing_move.write({'l10n_mx_closing_move': False})
        self.l10n_mx_closing_move = True


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.model
    def _query_get(self, domain=None):
        """Avoid that the model l10n_mx.trial.report consider the closing moves
        """
        if self._context.get('model') not in ('l10n_mx.trial.report', 'account.financial.html.report'):
            return super(AccountMoveLine, self)._query_get(domain=domain)
        closing_moves = self.env['account.move']._get_closing_move(fields.Date.from_string(self._context.get('date_to')))
        if domain is None:
            domain = []
        domain.append(('move_id', 'not in', closing_moves.ids))
        return super(AccountMoveLine, self)._query_get(domain=domain)
