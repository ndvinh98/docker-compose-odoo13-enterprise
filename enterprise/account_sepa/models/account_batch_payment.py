# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round, float_repr, DEFAULT_SERVER_DATE_FORMAT
from odoo.tools.misc import remove_accents

import base64
import re

def check_valid_SEPA_str(string):
    if re.search('[^-A-Za-z0-9/?:().,\'+ ]', string) is not None:
        raise ValidationError(_("The text used in SEPA files can only contain the following characters :\n\n"
            "a b c d e f g h i j k l m n o p q r s t u v w x y z\n"
            "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z\n"
            "0 1 2 3 4 5 6 7 8 9\n"
            "/ - ? : ( ) . , ' + (space)"))


class AccountBatchPayment(models.Model):
    _inherit = 'account.batch.payment'

    sct_generic = fields.Boolean(compute='_compute_sct_generic',
        help=u"Technical feature used during the file creation. A SEPA message is said to be 'generic' if it cannot be considered as "
             u"a standard european credit transfer. That is if the bank journal is not in €, a transaction is not in € or a payee is "
             u"not identified by an IBAN account number and a bank BIC.")

    sct_warning = fields.Text(compute='_compute_sct_generic')

    @api.depends('payment_ids', 'journal_id')
    def _compute_sct_generic(self):
        for record in self:
            warnings = record._get_genericity_info()
            record.sct_generic = bool(warnings)
            text_warning = None
            if record.journal_id.company_id.country_id.code != 'CH': #We need it as generic, but we should not give warnings
                if warnings and len(warnings) == 1:
                    text_warning = _('Please note that the following warning has been raised:')
                    text_warning += '\n%s\n\n' % warnings
                    text_warning += _('In result, the file might not be accepted by all bank as a valid SEPA Credit Transfer file')
                elif warnings:
                    text_warning = _('Please note that the following warnings have been raised:')
                    text_warning += '<ul>'
                    for warning in warnings:
                        text_warning += '<li>%s</li>' % warning
                    text_warning += '</ul>\n\n'
                    text_warning += _('In result, the file might not be accepted by all bank as a valid SEPA Credit Transfer file')
            record.sct_warning = text_warning

    def _get_genericity_info(self):
        """ Find out if generating a credit transfer initiation message for payments requires to use the generic rules, as opposed to the standard ones.
            The generic rules are used for payments which are not considered to be standard european credit transfers.
        """
        self.ensure_one()
        if self.payment_method_code != 'sepa_ct':
            return []
        error_list = []
        debtor_currency = self.journal_id.currency_id and self.journal_id.currency_id.name or self.journal_id.company_id.currency_id.name
        if debtor_currency != 'EUR':
            error_list.append(_('Your bank account is not labelled in EUR'))
        for payment in self.payment_ids:
            bank_account = payment.partner_bank_account_id
            if payment.currency_id.name != 'EUR' and (self.journal_id.currency_id or self.journal_id.company_id.currency_id).name == 'EUR':
                error_list.append(_('The transaction %s is instructed in another currency than EUR') % payment.name)
            if not bank_account.bank_bic:
                error_list.append(_('The creditor bank account %s used in payment %s is not identified by a BIC') % (payment.partner_bank_account_id.acc_number, payment.name))
            if not bank_account.acc_type == 'iban':
                error_list.append(_('The creditor bank account %s used in payment %s is not identified by an IBAN') % (payment.partner_bank_account_id.acc_number, payment.name))
        return error_list

    def _get_methods_generating_files(self):
        rslt = super(AccountBatchPayment, self)._get_methods_generating_files()
        rslt.append('sepa_ct')
        return rslt

    def validate_batch(self):
        if self.payment_method_code == 'sepa_ct':
            if self.journal_id.bank_account_id.acc_type != 'iban':
                    raise UserError(_("The account %s, of journal '%s', is not of type IBAN.\nA valid IBAN account is required to use SEPA features.") % (self.journal_id.bank_account_id.acc_number, self.journal_id.name))

            no_bank_acc_payments = self.env['account.payment']
            wrong_comm_payments = self.env['account.payment']
            for payment in self.payment_ids:
                if not payment.partner_bank_account_id:
                    no_bank_acc_payments += payment

            no_bank_acc_error_format = _("The following payments have no recipient bank account set: %s. \n\n")
            error_message = ''
            error_message += no_bank_acc_payments and no_bank_acc_error_format % ', '.join(no_bank_acc_payments.mapped('name')) or ''

            if error_message:
                raise UserError(error_message)

        return super(AccountBatchPayment, self).validate_batch()

    def _generate_export_file(self):
        if self.payment_method_code == 'sepa_ct':
            payments = self.payment_ids.sorted(key=lambda r: r.id)
            payment_dicts = self._generate_payment_template(payments)
            batch_booked = bool(self.env['ir.config_parameter'].sudo().get_param('account_sepa.batch_payment_batch_booking'))
            xml_doc = self.journal_id.create_iso20022_credit_transfer(payment_dicts, batch_booked, self.sct_generic)
            return {
                'file': base64.encodebytes(xml_doc),
                'filename': "SCT-" + self.journal_id.code + "-" + str(fields.Date.today()) + ".xml",
                'warning': self.sct_warning,
            }

        return super(AccountBatchPayment, self)._generate_export_file()

    def _generate_payment_template(self, payments):
        payment_dicts = []
        for payment in payments:
            if not payment.partner_bank_account_id:
                raise UserError(_('A bank account is not defined.'))

            payment_dict = {
                'id' : payment.id,
                'name': payment.communication or 'SCT-' + self.journal_id.code + '-' + str(fields.Date.today()),
                'payment_date' : payment.payment_date,
                'amount' : payment.amount,
                'journal_id' : self.journal_id.id,
                'currency_id' : payment.currency_id.id,
                'payment_type' : payment.payment_type,
                'communication' : payment.communication,
                'partner_id' : payment.partner_id.id,
                'partner_bank_id': payment.partner_bank_account_id.id,
            }

            payment_dicts.append(payment_dict)

        return payment_dicts
