# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools.misc import format_date
from odoo.osv import expression
from datetime import date, datetime, timedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    payment_next_action_date = fields.Date('Next Action Date', copy=False, company_dependent=True,
                                           help="The date before which no action should be taken.")
    unreconciled_aml_ids = fields.One2many('account.move.line', 'partner_id',
                                           domain=[('reconciled', '=', False),
                                                   ('account_id.deprecated', '=', False),
                                                   ('account_id.internal_type', '=', 'receivable'),
                                                   ('move_id.state', '=', 'posted')])
    unpaid_invoices = fields.One2many('account.move', compute='_compute_unpaid_invoices')
    total_due = fields.Monetary(compute='_compute_for_followup')
    total_overdue = fields.Monetary(compute='_compute_for_followup')
    followup_status = fields.Selection(
        [('in_need_of_action', 'In need of action'), ('with_overdue_invoices', 'With overdue invoices'), ('no_action_needed', 'No action needed')],
        compute='_compute_for_followup',
        string='Follow-up Status',
        search='_search_status')
    followup_level = fields.Many2one('account_followup.followup.line', compute="_compute_for_followup", string="Follow-up Level")
    payment_responsible_id = fields.Many2one('res.users', ondelete='set null', string='Follow-up Responsible',
                                             help="Optionally you can assign a user to this field, which will make him responsible for the action.",
                                             tracking=True, copy=False, company_dependent=True)

    def _search_status(self, operator, value):
        """
        Compute the search on the field 'followup_status'
        """
        if isinstance(value, str):
            value = [value]
        value = [v for v in value if v in ['in_need_of_action', 'with_overdue_invoices', 'no_action_needed']]
        if operator not in ('in', '=') or not value:
            return []
        followup_data = self._query_followup_level(all_partners=True)
        return [('id', 'in', [d['partner_id'] for d in followup_data.values() if d['followup_status'] in value])]

    def _compute_for_followup(self):
        """
        Compute the fields 'total_due', 'total_overdue','followup_level' and 'followup_status'
        """
        first_followup_level = self.env['account_followup.followup.line'].search([('company_id', '=', self.env.company.id)], order="delay asc", limit=1)
        followup_data = self._query_followup_level()
        today = fields.Date.context_today(self)
        for record in self:
            total_due = 0
            total_overdue = 0
            followup_status = "no_action_needed"
            for aml in record.unreconciled_aml_ids:
                if aml.company_id == self.env.company:
                    amount = aml.amount_residual
                    total_due += amount
                    is_overdue = today > aml.date_maturity if aml.date_maturity else today > aml.date
                    if is_overdue and not aml.blocked:
                        total_overdue += amount
            record.total_due = total_due
            record.total_overdue = total_overdue
            if record.id in followup_data:
                record.followup_status = followup_data[record.id]['followup_status']
                record.followup_level = self.env['account_followup.followup.line'].browse(followup_data[record.id]['followup_level']) or first_followup_level
            else:
                record.followup_status = 'no_action_needed'
                record.followup_level = first_followup_level

    def _compute_unpaid_invoices(self):
        for record in self:
            record.unpaid_invoices = self.env['account.move'].search([
                ('company_id', '=', self.env.company.id),
                ('commercial_partner_id', '=', record.id),
                ('state', '=', 'posted'),
                ('invoice_payment_state', '!=', 'paid'),
                ('type', 'in', self.env['account.move'].get_sale_types())
            ])

    def get_next_action(self, followup_line):
        """
        Compute the next action status of the customer.
        """
        self.ensure_one()
        date_auto = followup_line._get_next_date()
        return {
            'date': self.payment_next_action_date or date_auto,
        }

    def update_next_action(self, options=False):
        """Updates the next_action_date of the right account move lines"""
        next_action_date = options.get('next_action_date') and options['next_action_date'][0:10] or False
        next_action_date_done = False
        today = date.today()
        fups = self._compute_followup_lines()
        for partner in self:
            if options['action'] == 'done':
                next_action_date_done = datetime.strftime(partner.followup_level._get_next_date(), DEFAULT_SERVER_DATE_FORMAT)
            partner.payment_next_action_date = (not next_action_date or options['action'] == 'done') and next_action_date_done or next_action_date
            if options['action'] in ('done', 'later'):
                msg = _('Next Reminder Date set to %s') % format_date(self.env, partner.payment_next_action_date)
                partner.message_post(body=msg)
            if options['action'] == 'done':
                for aml in partner.unreconciled_aml_ids:
                    index = aml.followup_line_id.id or None
                    followup_date = fups[index][0]
                    next_level = fups[index][1]
                    if (aml.date_maturity and aml.date_maturity <= followup_date
                            or (aml.date and aml.date <= followup_date)):
                        aml.write({'followup_line_id': next_level, 'followup_date': today})

    def open_action_followup(self):
        self.ensure_one()
        return {
            'name': _("Overdue Payments for %s") % self.display_name,
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'views': [[self.env.ref('account_followup.customer_statements_form_view').id, 'form']],
            'res_model': 'res.partner',
            'res_id': self.id,
        }

    def send_followup_email(self):
        """
        Send a follow-up report by email to customers in self
        """
        for record in self:
            options = {
                'partner_id': record.id,
            }
            self.env['account.followup.report'].send_email(options)

    def get_followup_html(self):
        """
        Return the content of the follow-up report in HTML
        """
        options = {
            'partner_id': self.id,
            'followup_level': (self.followup_level.id, self.followup_level.delay),
            'keep_summary': True
        }
        return self.env['account.followup.report'].with_context(print_mode=True, lang=self.lang or self.env.user.lang).get_html(options)

    def _compute_followup_lines(self):
        """ returns the followup plan of the current user's company (of given in context directly)
        in the form of a dictionary with
         * keys being the different possible levels of followup for account.move.line's (None or IDs of account_followup.followup.line)
         * values being a tuple of 3 elements corresponding respectively to
           - the oldest date that any line in that followup level should be compared to in order to know if it is ready for the next level
           - the followup ID of the next level
           - the delays in days of the next level
        """
        followup_line_ids = self.env['account_followup.followup.line'].search([('company_id', '=', self.env.company.id)], order="delay asc")

        current_date = fields.Date.today()

        previous_level = None
        fups = {}
        for line in followup_line_ids:
            delay = timedelta(days=line.delay)
            delay_in_days = line.delay
            fups[previous_level] = (current_date - delay, line.id, delay_in_days)
            previous_level = line.id
        if previous_level:
            fups[previous_level] = (current_date - delay, previous_level, delay_in_days)
        return fups

    def _query_followup_level(self, all_partners=False):
        sql = """
            WITH unreconciled_aml AS (
                SELECT aml.id, aml.partner_id, aml.followup_line_id, aml.date, aml.date_maturity, aml.balance FROM account_move_line aml
                JOIN account_account account ON account.id = aml.account_id
                                            AND account.deprecated IS NOT TRUE
                                            AND account.internal_type = 'receivable'
                JOIN account_move move ON move.id = aml.move_id
                                       AND move.state = 'posted'
                WHERE aml.reconciled IS NOT TRUE
                AND aml.company_id = %(company_id)s
                {where}
            )
            SELECT partner.id as partner_id,
                   current_followup_level.id as followup_level,
                   CASE WHEN (SELECT SUM(balance) FROM unreconciled_aml ua WHERE ua.partner_id = partner.id GROUP BY partner.id) <= 0 THEN 'no_action_needed'
                        WHEN in_need_of_action_aml.id IS NOT NULL AND (prop_date.value_datetime IS NULL OR prop_date.value_datetime::date <= CURRENT_DATE) THEN 'in_need_of_action'
                        WHEN exceeded_unreconciled_aml.id IS NOT NULL THEN 'with_overdue_invoices'
                        ELSE 'no_action_needed' END as followup_status
            FROM res_partner partner
            -- Get the followup level
            LEFT OUTER JOIN account_followup_followup_line current_followup_level ON current_followup_level.id = (
                SELECT COALESCE(next_ful.id, ful.id) FROM unreconciled_aml aml
                LEFT OUTER JOIN account_followup_followup_line ful ON ful.id = aml.followup_line_id
                LEFT OUTER JOIN account_followup_followup_line next_ful ON next_ful.id = (
                    SELECT next_ful.id FROM account_followup_followup_line next_ful
                    WHERE next_ful.delay > COALESCE(ful.delay, 0)
                      AND COALESCE(aml.date_maturity, aml.date) + next_ful.delay <= CURRENT_DATE
                      AND next_ful.company_id = %(company_id)s
                    ORDER BY next_ful.delay ASC
                    LIMIT 1
                )
                WHERE aml.partner_id = partner.id
                  AND aml.balance > 0
                ORDER BY COALESCE(next_ful.delay, ful.delay, 0) DESC
                LIMIT 1
            )
            -- Get the followup status data
            LEFT OUTER JOIN account_move_line in_need_of_action_aml ON in_need_of_action_aml.id = (
                SELECT aml.id FROM unreconciled_aml aml
                LEFT OUTER JOIN account_followup_followup_line ful ON ful.id = aml.followup_line_id
                WHERE aml.partner_id = partner.id
                  AND aml.balance > 0
                  AND COALESCE(ful.delay, 0) < current_followup_level.delay
                  AND COALESCE(aml.date_maturity, aml.date) + COALESCE(ful.delay, 0) <= CURRENT_DATE
                LIMIT 1
            )
            LEFT OUTER JOIN account_move_line exceeded_unreconciled_aml ON exceeded_unreconciled_aml.id = (
                SELECT aml.id FROM unreconciled_aml aml
                WHERE aml.partner_id = partner.id
                  AND aml.balance > 0
                  AND COALESCE(aml.date_maturity, aml.date) <= CURRENT_DATE
                LIMIT 1
            )
            LEFT OUTER JOIN ir_property prop_date ON prop_date.res_id = CONCAT('res.partner,', partner.id) AND prop_date.name = 'payment_next_action_date'
            WHERE partner.id in (SELECT DISTINCT partner_id FROM unreconciled_aml)
        """.format(
            where="" if all_partners else "AND aml.partner_id in %(partner_ids)s",
        )
        params = {
            'company_id': self.env.company.id,
            'partner_ids': tuple(self.ids),
        }
        self.env['account.move.line'].flush()
        self.env['res.partner'].flush()
        self.env['account_followup.followup.line'].flush()
        self.env.cr.execute(sql, params)
        result = self.env.cr.dictfetchall()
        result = {r['partner_id']: r for r in result}
        return result

    def _execute_followup_partner(self):
        self.ensure_one()
        if self.followup_status == 'in_need_of_action':
            followup_line = self.followup_level
            if followup_line.send_email:
                self.send_followup_email()
            if followup_line.manual_action:
                # log a next activity for today
                activity_data = {
                    'res_id': self.id,
                    'res_model_id': self.env['ir.model']._get(self._name).id,
                    'activity_type_id': followup_line.manual_action_type_id.id or self.env.ref('mail.mail_activity_data_todo').id,
                    'summary': followup_line.manual_action_note,
                    'user_id': followup_line.manual_action_responsible_id.id or self.env.user.id,
                }
                self.env['mail.activity'].create(activity_data)
            if followup_line:
                next_date = followup_line._get_next_date()
                self.update_next_action(options={'next_action_date': datetime.strftime(next_date, DEFAULT_SERVER_DATE_FORMAT), 'action': 'done'})
            if followup_line.print_letter:
                return self
        return None

    def execute_followup(self):
        """
        Execute the actions to do with followups.
        """
        to_print = self.env['res.partner']
        for partner in self:
            partner_tmp = partner._execute_followup_partner()
            if partner_tmp:
                to_print += partner_tmp
        if not to_print:
            return
        return self.env['account.followup.report'].print_followups(to_print)

    def _cron_execute_followup(self):
        followup_data = self._query_followup_level(all_partners=True)
        in_need_of_action = self.env['res.partner'].browse([d['partner_id'] for d in followup_data.values() if d['followup_status'] == 'in_need_of_action'])
        in_need_of_action_auto = in_need_of_action.filtered(lambda p: p.followup_level.auto_execute)
        in_need_of_action_auto.execute_followup()
