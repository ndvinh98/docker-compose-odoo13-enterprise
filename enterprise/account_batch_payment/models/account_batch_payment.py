# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountBatchPayment(models.Model):
    _name = "account.batch.payment"
    _description = "Batch Payment"
    _order = "date desc, id desc"

    name = fields.Char(required=True, copy=False, string='Reference', readonly=True, states={'draft': [('readonly', False)]})
    date = fields.Date(required=True, copy=False, default=fields.Date.context_today, readonly=True, states={'draft': [('readonly', False)]})
    state = fields.Selection([('draft', 'New'), ('sent', 'Sent'), ('reconciled', 'Reconciled')], readonly=True, default='draft', copy=False)
    journal_id = fields.Many2one('account.journal', string='Bank', domain=[('type', '=', 'bank')], required=True, readonly=True, states={'draft': [('readonly', False)]})
    payment_ids = fields.One2many('account.payment', 'batch_payment_id', string="Payments", required=True, readonly=True, states={'draft': [('readonly', False)]})
    amount = fields.Monetary(compute='_compute_amount', store=True, readonly=True)
    currency_id = fields.Many2one('res.currency', compute='_compute_currency', store=True, readonly=True)
    batch_type = fields.Selection(selection=[('inbound', 'Inbound'), ('outbound', 'Outbound')], required=True, readonly=True, states={'draft': [('readonly', False)]}, default='inbound')
    payment_method_id = fields.Many2one(comodel_name='account.payment.method', string='Payment Method', required=True, readonly=True, states={'draft': [('readonly', False)]}, help="The payment method used by the payments in this batch.")
    payment_method_code = fields.Char(related='payment_method_id.code', readonly=False)
    export_file_create_date = fields.Date(string='Generation Date', default=fields.Date.today, readonly=True, help="Creation date of the related export file.", copy=False)
    export_file = fields.Binary(string='File', readonly=True, help="Export file related to this batch", copy=False)
    export_filename = fields.Char(string='File Name', help="Name of the export file generated for this batch", store=True, copy=False)

    available_payment_method_ids = fields.One2many(comodel_name='account.payment', compute='_compute_available_payment_method_ids')
    file_generation_enabled = fields.Boolean(help="Whether or not this batch payment should display the 'Generate File' button instead of 'Print' in form view.", compute='_compute_file_generation_enabled')

    @api.depends('payment_method_id')
    def _compute_file_generation_enabled(self):
        for record in self:
            record.file_generation_enabled = record.payment_method_id.code in record._get_methods_generating_files()

    def _get_methods_generating_files(self):
        """ Hook for extension. Any payment method whose code stands in the list
        returned by this function will see the "print" button disappear on batch
        payments form when it gets selected and an 'Export file' appear instead.
        """
        return []

    @api.depends('journal_id', 'batch_type')
    def _compute_available_payment_method_ids(self):
        for record in self:
            record.available_payment_method_ids = record.batch_type == 'inbound' and record.journal_id.inbound_payment_method_ids.ids or record.journal_id.outbound_payment_method_ids.ids

    @api.depends('journal_id')
    def _compute_currency(self):
        for batch in self:
            if batch.journal_id:
                batch.currency_id = batch.journal_id.currency_id or batch.journal_id.company_id.currency_id
            else:
                batch.currency_id = False

    @api.depends('payment_ids', 'payment_ids.amount', 'journal_id')
    def _compute_amount(self):
        for batch in self:
            company_currency = batch.journal_id.company_id.currency_id or self.env.company.currency_id
            journal_currency = batch.journal_id.currency_id or company_currency
            amount = 0
            for payment in batch.payment_ids:
                payment_currency = payment.currency_id or company_currency
                if payment_currency == journal_currency:
                    amount += payment.amount
                else:
                    # note: this makes rec.date the value date, which IRL probably is the
                    # date of the reception by the bank
                    amount += payment_currency._convert(
                        payment.amount, journal_currency, batch.journal_id.company_id,
                        batch.date or fields.Date.today())
            batch.amount = amount

    @api.constrains('batch_type', 'journal_id', 'payment_ids')
    def _check_payments_constrains(self):
        for record in self:
            all_companies = set(record.payment_ids.mapped('company_id'))
            if len(all_companies) > 1:
                raise ValidationError(_("All payments in the batch must belong to the same company."))
            all_journals = set(record.payment_ids.mapped('journal_id'))
            if len(all_journals) > 1 or (record.payment_ids and record.payment_ids[:1].journal_id != record.journal_id):
                raise ValidationError(_("The journal of the batch payment and of the payments it contains must be the same."))
            all_types = set(record.payment_ids.mapped('payment_type'))
            if all_types and record.batch_type not in all_types:
                raise ValidationError(_("The batch must have the same type as the payments it contains."))
            all_payment_methods = set(record.payment_ids.mapped('payment_method_id'))
            if len(all_payment_methods) > 1:
                raise ValidationError(_("All payments in the batch must share the same payment method."))
            if all_payment_methods and record.payment_method_id not in all_payment_methods:
                raise ValidationError(_("The batch must have the same payment method as the payments it contains."))
            payment_null = record.payment_ids.filtered(lambda p: p.amount == 0)
            if payment_null:
                names = '\n'.join([p.name or _('Id: %s') % p.id for p in payment_null])
                msg = _('You cannot add payments with zero amount in a Batch Payment.\nPayments:\n%s') % names
                raise ValidationError(msg)

    @api.model
    def create(self, vals):
        vals['name'] = self._get_batch_name(vals.get('batch_type'), vals.get('date', fields.Date.context_today(self)), vals)
        rec = super(AccountBatchPayment, self).create(vals)
        rec.normalize_payments()
        return rec

    def write(self, vals):
        if 'batch_type' in vals:
            vals['name'] = self.with_context(default_journal_id=self.journal_id.id)._get_batch_name(vals['batch_type'], self.date, vals)

        rslt = super(AccountBatchPayment, self).write(vals)

        if 'payment_ids' in vals:
            self.normalize_payments()

        return rslt

    def normalize_payments(self):
        for batch in self:
            # Since a batch payment has no confirmation step (it can be used to select payments in a bank reconciliation
            # as long as state != reconciled), its payments need to be posted
            batch.payment_ids.filtered(lambda r: r.state == 'draft').post()

    @api.model
    def _get_batch_name(self, batch_type, sequence_date, vals):
        if not vals.get('name'):
            sequence_code = 'account.inbound.batch.payment'
            if batch_type == 'outbound':
                sequence_code = 'account.outbound.batch.payment'
            return self.env['ir.sequence'].with_context(sequence_date=sequence_date).next_by_code(sequence_code)
        return vals['name']

    def validate_batch(self):
        records = self.filtered(lambda x: x.state == 'draft')
        for record in records:
            record.payment_ids.write({'state':'sent', 'payment_reference': record.name})
        records.write({'state': 'sent'})

        return self.filtered('file_generation_enabled').export_batch_payment()

    def export_batch_payment(self):
        export_file_data = {}
        #export and save the file for each batch payment
        self.check_access_rights('write')
        self.check_access_rule('write')
        for record in self.with_context(force_company=self.env.user.company_id.id).sudo():
            export_file_data = record._generate_export_file()
            record.export_file = export_file_data['file']
            record.export_filename = export_file_data['filename']
            record.export_file_create_date = fields.Date.today()

        #if the validation was asked for a single batch payment, open the wizard to download the newly generated file
        if len(self) == 1:
            download_wizard = self.env['account.batch.download.wizard'].create({
                    'batch_payment_id': self.id,
                    'warning_message': export_file_data.get('warning'),
            })
            return {
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'account.batch.download.wizard',
                'target': 'new',
                'res_id': download_wizard.id,
            }

    def print_batch_payment(self):
        return self.env.ref('account_batch_payment.action_print_batch_payment').report_action(self, config=False)

    def _generate_export_file(self):
        """ To be overridden by modules adding support for different export format.
            This function returns False if no export file could be generated
            for this batch. Otherwise, it returns a dictionary containing the following keys:
            - file: the content of the generated export file, in base 64.
            - filename: the name of the generated file
            - warning: (optional) the warning message to display

        """
        self.ensure_one()
        return False
