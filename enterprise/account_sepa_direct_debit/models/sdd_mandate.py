# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo import api, fields, models, _

from odoo.exceptions import UserError


class SDDMandate(models.Model):
    """ A class containing the data of a mandate sent by a customer to give its
    consent to a company to collect the payments associated to his invoices
    using SEPA Direct Debit.
    """
    _name = 'sdd.mandate'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'SDD Mandate'

    _sql_constraints = [('name_unique', 'unique(name)', "Mandate identifier must be unique ! Please choose another one.")]

    state = fields.Selection([('draft', 'Draft'),('active','Active'), ('revoked','Revoked'), ('closed','Closed')],
                            string="State",
                            readonly=True,
                            default='draft',
                            help="The state this mandate is in. \n"
                            "- 'draft' means that this mandate still needs to be confirmed before being usable. \n"
                            "- 'active' means that this mandate can be used to pay invoices. \n"
                            "- 'closed' designates a mandate that has been marked as not to use anymore without invalidating the previous transactions done with it."
                            "- 'revoked' means the mandate has been signaled as fraudulent by the customer. It cannot be used anymore, and should not ever have been. You will probably need to refund the related invoices, if any.\n")

    #one-off mandates are fully supported, but hidden to the user for now. Let's see if they need it.
    one_off = fields.Boolean(string='One-off Mandate',
                                    default=False,
                                    help="True if and only if this mandate can be used for only one transaction. It will automatically go from 'active' to 'closed' after its first use in payment if this option is set.\n")

    name = fields.Char(string='Identifier', required=True, readonly=True, states={'draft':[('readonly',False)]}, help="The unique identifier of this mandate.", default=lambda self: datetime.now().strftime('%f%S%M%H%d%m%Y'), copy=False)
    debtor_id_code = fields.Char(string='Debtor Identifier', readonly=True, states={'draft':[('readonly',False)]}, help="Free reference identifying the debtor in your company.")
    partner_id = fields.Many2one(comodel_name='res.partner', string='Customer', required=True, readonly=True, states={'draft':[('readonly',False)]}, domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]", help="Customer whose payments are to be managed by this mandate.")
    company_id = fields.Many2one(comodel_name='res.company', default=lambda self: self.env.company, help="Company for whose invoices the mandate can be used.")
    partner_bank_id = fields.Many2one(string='IBAN', readonly=True, states={'draft':[('readonly',False)]}, comodel_name='res.partner.bank', domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]", help="Account of the customer to collect payments from.")
    paid_invoice_ids = fields.One2many(string='Invoices Paid', comodel_name='account.move', readonly=True, inverse_name='sdd_paying_mandate_id', help="Invoices paid using this mandate.")
    start_date = fields.Date(string="Start Date", required=True, readonly=True, states={'draft':[('readonly',False)]}, help="Date from which the mandate can be used (inclusive).")
    end_date = fields.Date(string="End Date", states={'closed':[('readonly',True)]}, help="Date until which the mandate can be used. It will automatically be closed after this date.")
    original_doc = fields.Binary(string="Original Document", readonly=True, states={'draft':[('readonly',False)]}, help="Original document into which the customer authorises the use of Direct Debit for his invoices.", attachment=False) # TODO: check — should probably remain in DB for confidence purposes?
    original_doc_filename = fields.Char(string='Original Document File Name', help="File name of original_doc.")
    payment_journal_id = fields.Many2one(string='Journal', comodel_name='account.journal', required=True, domain="[('company_id', '=', company_id)]", help='Journal to use to receive SEPA Direct Debit payments from this mandate.')
    payment_ids = fields.One2many(string='Payments', comodel_name='account.payment', inverse_name='sdd_mandate_id', help="Payments generated thanks to this mandate.")
    payments_to_collect_nber = fields.Integer(string='Direct Debit Payments to Collect', compute='_compute_payments_to_collect_nber', help="Number of Direct Debit payments to be collected for this mandate, that is, the number of payments that have been generated and posted thanks to this mandate and still needs their XML file to be generated and sent to the bank to debit the customer's account.")
    paid_invoices_nber = fields.Integer(string='Paid Invoices Number', compute='_compute_paid_invoices_nber', help="Number of invoices paid with thid mandate.")

    def unlink(self):
        if self.filtered(lambda x: x.state != 'draft'):
            raise UserError(_("Only mandates in draft state can be deleted from database when cancelled."))
        return super(SDDMandate, self).unlink()

    @api.model
    def _sdd_get_usable_mandate(self, company_id, partner_id, date):
        """ returns the first mandate found that can be used, accordingly to given parameters
        or none if there is no such mandate.
        """
        return self.search([('state', 'not in', ['draft', 'revoked']),
                            ('start_date', '<=', date),
                            '|', ('end_date', '>=', date), ('end_date', '=', None),
                            ('company_id', '=', company_id),
                            ('partner_id', '=', partner_id),
                            '|', ('one_off', '=', False), ('payment_ids', '=', False)],
                          limit=1)

    @api.depends('paid_invoice_ids')
    def _compute_paid_invoices_nber(self):
        for record in self:
            record.paid_invoices_nber = len(record.paid_invoice_ids)

    @api.depends('payment_ids')
    def _compute_payments_to_collect_nber(self):
        for record in self:
            record.payments_to_collect_nber = self.env['account.payment'].search_count([('id','in',record.payment_ids.ids), ('state','=','posted'), ('payment_method_code','=','sdd')])

    def action_validate_mandate(self):
        """ Called by the 'validate' button of the form view.
        """
        for record in self:
            if record.state == 'draft':
                if any([not record.partner_bank_id for record in self]):
                    raise UserError(_("A debtor account is required to validate a SEPA Direct Debit mandate."))
                if any([record.partner_bank_id.acc_type != 'iban' for record in self]):
                    raise UserError(_("SEPA Direct Debit scheme only accepts IBAN account numbers. Please select an IBAN-compliant debtor account for this mandate."))

                record.state = 'active'

    def action_cancel_draft_mandate(self):
        """ Cancels (i.e. deletes) a mandate in draft state.
        """
        self.unlink()

    def action_revoke_mandate(self):
        """ Called by the 'revoke' button of the form view.
        """
        for record in self:
            record.state = 'revoked'

    def action_close_mandate(self):
        """ Called by the 'close' button of the form view.
        Also automatically triggered by one-off mandate when they are used.
        """
        for record in self:
            if record.state != 'revoked':
                record.end_date = fields.Date.today()
                record.state = 'closed'

    def action_view_paid_invoices(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Paid Invoices'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.mapped('paid_invoice_ids').ids)],
        }

    def action_view_payments_to_collect(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payments to Collect'),
            'res_model': 'account.payment',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.mapped('payment_ids').ids), ('state', '=', 'posted')],
        }

    @api.constrains('end_date', 'start_date')
    def validate_end_date(self):
        for record in self:
            if record.end_date and record.start_date and record.end_date < record.start_date:
                raise UserError(_("The end date of the mandate must be posterior or equal to its start date."))

    @api.constrains('payment_journal_id')
    def _validate_account_journal_id(self):
        for record in self:
            if record.payment_journal_id.bank_account_id.acc_type != 'iban':
                raise UserError(_("Only IBAN account numbers can receive SEPA Direct Debit payments. Please select a journal associated to one."))
            if not record.payment_journal_id.bank_id:
                raise UserError(_("The destination bank account must be related to a bank with a valid BIC."))
            if not record.payment_journal_id.bank_id.bic:
                raise UserError(_("The bank your payment account is related to must have a BIC number. Please define one."))

    @api.constrains('debtor_id_code')
    def _validate_debtor_id_code(self):
        for record in self:
            if record.debtor_id_code and len(record.debtor_id_code) > 35:  # Arbitrary limitation given by SEPA regulation for the <id> element used for this field when generating the XML
                raise UserError(_("The debtor identifier you specified exceeds the limitation of 35 characters imposed by SEPA regulation"))

    @api.model
    def cron_update_mandates_states(self):
        current_company = self.env.company
        today = fields.Date.today()
        for mandate in self.search([('company_id', '=', current_company.id), ('state', '=', 'active'), ('end_date', '!=', False)]):
            if mandate.end_date < today:
                mandate.state = 'closed'
