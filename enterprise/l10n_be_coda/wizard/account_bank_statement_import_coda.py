# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Copyright (c) 2012 Noviat nv/sa (www.noviat.be). All rights reserved.

import time
import re

from odoo import models, fields, tools, _
from odoo.exceptions import UserError


class safedict(dict):
    def __init__(self, *args, return_val=None, **kwargs):
        self.__return_val = return_val if return_val is not None else _('Wrong CODA code')
        super().__init__(*args, **kwargs)

    def __getitem__(self, k):
        return super().__getitem__(k) if k in self else self.__return_val


# Mappings for the structured communication formats
minimum = safedict({'1': _('minimum applicable'), '2': _('minimum not applicable')})
card_scheme = safedict({'1': _('Bancontact/Mister Cash'), '2': _('Maestro'), '3': _('Private'), '5': _('TINA'), '9': _('Other')})
transaction_type = safedict({'0': _('cumulative'), '1': _('withdrawal'), '2': _('cumulative on network'), '4': _('reversal of purchases'), '5': _('POS others'), '7': _('distribution sector'), '8': _('teledata'), '9': _('fuel')})
product_code = safedict({'00': _('unset'), '01': _('premium with lead substitute'), '02': _('europremium'), '03': _('diesel'), '04': _('LPG'), '06': _('premium plus 98 oct'), '07': _('regular unleaded'), '08': _('domestic fuel oil'), '09': _('lubricants'), '10': _('petrol'), '11': _('premium 99+'), '12': _('Avgas'), '16': _('other types')})
issuing_institution = safedict({'1': 'Mastercard', '2': 'Visa', '3': 'American Express', '4': 'Diners Club', '9': 'Other'})
type_direct_debit = safedict({'0': _('unspecified'), '1': _('recurrent'), '2': _('one-off'), '3': _('1-st (recurrent)'), '4': _('last (recurrent)')})
direct_debit_scheme = safedict({'0': _('unspecified'), '1': _('SEPA core'), '2': _('SEPA B2B')})
payment_reason = safedict({'0': _('paid'), '1': _('technical problem'), '2': _('reason not specified'), '3': _('debtor disagrees'), '4': _('debtor’s account problem')})
sepa_type = safedict({'0': _('paid'), '1': _('reject'), '2': _('return'), '3': _('refund'), '4': _('reversal'), '5': _('cancellation')})


sepa_transaction_type = safedict({
    0: _('Simple amount without detailed data'),
    1: _('Amount as totalised by the customer'),
    2: _('Amount as totalised by the bank'),
    3: _('Simple amount with detailed data'),
    5: _('Detail of Amount as totalised by the customer'),
    6: _('Detail of Amount as totalised by the bank'),
    7: _('Detail of Amount as totalised by the bank'),
    8: _('Detail of Simple amount with detailed data'),
    9: _('Detail of Amount as totalised by the bank'),
})

default_transaction_code = safedict({
    '40': _('Codes proper to each bank'), '41': _('Codes proper to each bank'), '42': _('Codes proper to each bank'), '43': _('Codes proper to each bank'), '44': _('Codes proper to each bank'), '45': _('Codes proper to each bank'), '46': _('Codes proper to each bank'), '47': _('Codes proper to each bank'), '48': _('Codes proper to each bank'),
    '49': _('Cancellation or correction'),
    '87': _('Reimbursement of costs'),
    '90': _('Codes proper to each bank'), '91': _('Codes proper to each bank'), '92': _('Codes proper to each bank'), '93': _('Codes proper to each bank'), '94': _('Codes proper to each bank'), '95': _('Codes proper to each bank'), '96': _('Codes proper to each bank'), '97': _('Codes proper to each bank'), '98': _('Codes proper to each bank'),
    '99': _('Cancellation or correction'),
})
transaction_code = safedict(**{
    'return_val': ('', {}),
    '01': (_('Domestic or local SEPA credit transfers'), {
        '01': _('Individual transfer order'),
        '02': _('Individual transfer order initiated by the bank'),
        '03': _('Standing order'),
        '05': _('Payment of wages, etc.'),
        '07': _('Collective transfer'),
        '13': _('Transfer from your account'),
        '17': _('Financial centralisation'),
        '37': _('Costs'),
        '39': _('Your issue circular cheque'),
        '50': _('Transfer in your favour'),
        '51': _('Transfer in your favour – initiated by the bank'),
        '52': _('Payment in your favour'),
        '54': _('Unexecutable transfer order'),
        '60': _('Non-presented circular cheque'),
        '62': _('Unpaid postal order'),
        '64': _('Transfer to your account'),
        '66': _('Financial centralization'),
    }),
    '02': (_('Instant SEPA credit transfer'), {
        '01': _('Individual transfer order'),
        '02': _('Individual transfer order initiated by the bank'),
        '03': _('Standing order'),
        '05': _('Payment of wages, etc.'),
        '07': _('Collective transfer'),
        '13': _('Transfer from your account'),
        '17': _('Financial centralisation'),
        '37': _('Costs'),
        '50': _('Transfer in your favour'),
        '51': _('Transfer in your favour – initiated by the bank'),
        '52': _('Payment in your favour'),
        '54': _('Unexecutable transfer order'),
        '64': _('Transfer to your account'),
        '66': _('Financial centralization'),
    }),
    '03': (_('Cheques'), {
        '01': _('Payment of your cheque'),
        '05': _('Payment of voucher'),
        '09': _('Unpaid voucher'),
        '11': _('Department store cheque'),
        '15': _('Your purchase bank cheque'),
        '17': _('Your certified cheque'),
        '37': _('Cheque-related costs'),
        '38': _('Provisionally unpaid'),
        '40': _('Codes proper to each bank'),
        '52': _('First credit of cheques, vouchers, luncheon vouchers, postal orders, credit under usual reserve'),
        '58': _('Remittance of cheques, vouchers, etc. credit after collection'),
        '60': _('Reversal of voucher'),
        '62': _('Reversal of cheque'),
        '63': _('Second credit of unpaid cheque'),
        '66': _('Remittance of cheque by your branch - credit under usual reserve'),
        '87': _('Reimbursement of cheque-related costs'),
    }),
    '04': (_('Cards'), {
        '01': _('Loading a GSM card'),
        '02': _('Payment by means of a payment card within the Eurozone'),
        '03': _('Settlement credit cards'),
        '04': _('Cash withdrawal from an ATM'),
        '05': _('Loading Proton'),
        '06': _('Payment with tank card'),
        '07': _('Payment by GSM'),
        '08': _('Payment by means of a payment card outside the Eurozone'),
        '09': _('Upload of prepaid card'),
        '10': _('Correction for prepaid card'),
        '37': _('Costs'),
        '50': _('Credit after a payment at a terminal'),
        '51': _('Unloading Proton'),
        '52': _('Loading GSM cards'),
        '53': _('Cash deposit at an ATM'),
        '54': _('Download of prepaid card'),
        '55': _('Income from payments by GSM'),
        '56': _('Correction for prepaid card'),
        '68': _('Credit after Proton payments'),
    }),
    '05': (_('Direct debit'), {
        '01': _('Payment'),
        '03': _('Unpaid debt'),
        '05': _('Reimbursement'),
        '37': _('Costs'),
        '50': _('Credit after collection'),
        '52': _('Credit under usual reserve'),
        '54': _('Reimbursement'),
        '56': _('Unexecutable reimbursement'),
        '58': _('Reversal'),
    }),
    '07': (_('Domestic commercial paper'), {
        '01': _('Payment commercial paper'),
        '05': _('Commercial paper claimed back'),
        '06': _('Extension of maturity date'),
        '07': _('Unpaid commercial paper'),
        '08': _('Payment in advance'),
        '09': _('Agio on supplier\'s bill'),
        '37': _('Costs related to commercial paper'),
        '39': _('Return of an irregular bill of exchange'),
        '50': _('Remittance of commercial paper - credit after collection'),
        '52': _('Remittance of commercial paper - credit under usual reserve'),
        '54': _('Remittance of commercial paper for discount'),
        '56': _('Remittance of supplier\'s bill with guarantee'),
        '58': _('Remittance of supplier\'s bill without guarantee'),
    }),
    '09': (_('Counter transactions'), {
        '01': _('Cash withdrawal'),
        '05': _('Purchase of foreign bank notes'),
        '07': _('Purchase of gold/pieces'),
        '09': _('Purchase of petrol coupons'),
        '13': _('Cash withdrawal by your branch or agents'),
        '17': _('Purchase of fiscal stamps'),
        '19': _('Difference in payment'),
        '25': _('Purchase of traveller’s cheque'),
        '37': _('Costs'),
        '50': _('Cash payment'),
        '52': _('Payment night safe'),
        '58': _('Payment by your branch/agents'),
        '60': _('Sale of foreign bank notes'),
        '62': _('Sale of gold/pieces under usual reserve'),
        '68': _('Difference in payment'),
        '70': _('Sale of traveller’s cheque'),
    }),
    '11': (_('Securities'), {
        '01': _('Purchase of securities'),
        '02': _('Tenders'),
        '03': _('Subscription to securities'),
        '04': _('Issues'),
        '05': _('Partial payment subscription'),
        '06': _('Share option plan – exercising an option'),
        '09': _('Settlement of securities'),
        '11': _('Payable coupons/repayable securities'),
        '13': _('Your repurchase of issue'),
        '15': _('Interim interest on subscription'),
        '17': _('Management fee'),
        '19': _('Regularisation costs'),
        '37': _('Costs'),
        '50': _('Sale of securities'),
        '51': _('Tender'),
        '52': _('Payment of coupons from a deposit or settlement of coupons delivered over the counter - credit under usual reserve'),
        '58': _('Repayable securities from a deposit or delivered at the counter - credit under usual reserve'),
        '62': _('Interim interest on subscription'),
        '64': _('Your issue'),
        '66': _('Retrocession of issue commission'),
        '68': _('Compensation for missing coupon'),
        '70': _('Settlement of securities'),
        '99': _('Cancellation or correction'),
    }),
    '13': (_('Credit'), {
        '01': _('Short-term loan'),
        '02': _('Long-term loan'),
        '05': _('Settlement of fixed advance'),
        '07': _('Your repayment instalment credits'),
        '11': _('Your repayment mortgage loan'),
        '13': _('Settlement of bank acceptances'),
        '15': _('Your repayment hire-purchase and similar claims'),
        '19': _('Documentary import credits'),
        '21': _('Other credit applications'),
        '37': _('Credit-related costs'),
        '50': _('Settlement of instalment credit'),
        '54': _('Fixed advance – capital and interest'),
        '55': _('Fixed advance – interest only'),
        '56': _('Subsidy'),
        '60': _('Settlement of mortgage loan'),
        '62': _('Term loan'),
        '68': _('Documentary export credits'),
        '70': _('Settlement of discount bank acceptance'),
    }),
    '30': (_('Various transactions'), {
        '01': _('Spot purchase of foreign exchange'),
        '03': _('Forward purchase of foreign exchange'),
        '05': _('Capital and/or interest term investment'),
        '33': _('Value (date) correction'),
        '37': _('Costs'),
        '39': _('Undefined transaction'),
        '50': _('Spot sale of foreign exchange'),
        '52': _('Forward sale of foreign exchange'),
        '54': _('Capital and/or interest term investment'),
        '55': _('Interest term investment'),
        '83': _('Value (date) correction'),
        '89': _('Undefined transaction'),
    }),
    '35': (_('Closing (periodical settlements for interest, costs,...)'), {
        '01': _('Closing'),
        '37': _('Costs'),
        '50': _('Closing'),
    }),
    '41': (_('International credit transfers - non-SEPA credit transfers'), {
        '01': _('Transfer'),
        '03': _('Standing order'),
        '05': _('Collective payments of wages'),
        '07': _('Collective transfers'),
        '13': _('Transfer from your account'),
        '17': _('Financial centralisation (debit)'),
        '37': _('Costs relating to outgoing foreign transfers and non-SEPA transfers'),
        '38': _('Costs relating to incoming foreign and non-SEPA transfers'),
        '50': _('Transfer'),
        '64': _('Transfer to your account'),
        '66': _('Financial centralisation (credit)'),
    }),
    '43': (_('Foreign cheques'), {
        '01': _('Payment of a foreign cheque'),
        '07': _('Unpaid foreign cheque'),
        '15': _('Purchase of an international bank cheque'),
        '37': _('Costs relating to payment of foreign cheques'),
        '52': _('Remittance of foreign cheque credit under usual reserve'),
        '58': _('Remittance of foreign cheque credit after collection'),
        '62': _('Reversal of cheques'),
    }),
    '47': (_('Foreign commercial paper'), {
        '01': _('Payment of foreign bill'),
        '05': _('Bill claimed back'),
        '06': _('Extension'),
        '07': _('Unpaid foreign bill'),
        '11': _('Payment documents abroad'),
        '13': _('Discount foreign supplier\'s bills'),
        '14': _('Warrant fallen due'),
        '37': _('Costs relating to the payment of a foreign bill'),
        '50': _('Remittance of foreign bill credit after collection'),
        '52': _('Remittance of foreign bill credit under usual reserve'),
        '54': _('Discount abroad'),
        '56': _('Remittance of guaranteed foreign supplier\'s bill'),
        '58': _('Idem without guarantee'),
        '60': _('Remittance of documents abroad - credit under usual reserve'),
        '62': _('Remittance of documents abroad - credit after collection'),
        '64': _('Warrant'),
    }),
    '80': (_('Separately charged costs and provisions'), {
        '02': _('Costs relating to electronic output'),
        '04': _('Costs for holding a documentary cash credit'),
        '06': _('Damage relating to bills and cheques'),
        '07': _('Insurance costs'),
        '08': _('Registering compensation for savings accounts'),
        '09': _('Postage'),
        '10': _('Purchase of Smartcard'),
        '11': _('Costs for the safe custody of correspondence'),
        '12': _('Costs for opening a bank guarantee'),
        '13': _('Renting of safes'),
        '14': _('Handling costs instalment credit'),
        '15': _('Night safe'),
        '16': _('Bank confirmation to revisor or accountant'),
        '17': _('Charge for safe custody'),
        '18': _('Trade information'),
        '19': _('Special charge for safe custody'),
        '20': _('Drawing up a certificate'),
        '21': _('Pay-packet charges'),
        '22': _('Management/custody'),
        '23': _('Research costs'),
        '24': _('Participation in and management of interest refund system'),
        '25': _('Renting of direct debit box'),
        '26': _('Travel insurance premium'),
        '27': _('Subscription fee'),
        '29': _('Information charges'),
        '31': _('Writ service fee'),
        '33': _('Miscellaneous fees and commissions'),
        '35': _('Costs'),
        '37': _('Access right to database'),
        '39': _('Surety fee'),
        '41': _('Research costs'),
        '43': _('Printing of forms'),
        '45': _('Documentary credit charges'),
        '47': _('Charging fees for transactions'),
    }),
})


class AccountBankStatementImport(models.TransientModel):
    _inherit = 'account.bank.statement.import'

    split_transactions = fields.Boolean()

    def _check_coda(self, data_file):
        # Matches the first 24 characters of a CODA file, as defined by the febelfin specifications
        return re.match(b'0{5}\d{9}05[ D] +', data_file) is not None

    def _parse_file(self, data_file):
        if not self._check_coda(data_file):
            return super(AccountBankStatementImport, self)._parse_file(data_file)

        def rmspaces(s):
            return " ".join(s.split())

        def parsedate(s):
            if s == '999999':
                return _('No date')
            return "{day}/{month}/{year}".format(day=s[:2], month=s[2:4], year=s[4:])

        def parsehour(s):
            return "{hour}:{minute}".format(hour=s[:2], minute=s[2:])

        def parsefloat(s, precision):
            return str(float(rmspaces(s)) / (10 ** precision))

        def parse_terminal(s):
            return _('Name: {name}, Town: {city}').format(name=rmspaces(s[:16]), city=rmspaces(s[16:]))

        def parse_operation(type, family, operation, category):
            return "{type}: {family} ({operation})".format(
                type=sepa_transaction_type[type],
                family=transaction_code[family][0],
                operation=transaction_code[family][1].get(operation, default_transaction_code.get(operation, _('undefined')))
            )

        def parse_structured_communication(type, communication):
            note = []
            p_idx = 0 ; o_idx = 0
            if type == '100':  # RF Creditor Reference
                structured_com = rmspaces(communication[:25])
            elif type in ('101', '102'):  # Credit transfer or cash payment with structured format communication or with reconstituted structured format communication
                structured_com = '+++' + communication[:3] + '/' + communication[3:7] + '/' + communication[7:12] + '+++'
            elif type == '103':  # number (e.g. of the cheque, of the card, etc.)
                structured_com = rmspaces(communication[:12])
            elif type == '105':  # Original amount of the transaction
                structured_com = _('Original amount of the transaction')
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('Gross amount in the currency of the account') + ': ' + parsefloat(communication[o_idx:p_idx], 3))
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('Gross amount in the original currency') + ': ' + parsefloat(communication[o_idx:p_idx], 3))
                o_idx = p_idx; p_idx += 12; note.append(_('Detail') + ': ' + _('Rate') + ': ' + parsefloat(communication[o_idx:p_idx], 8))
                o_idx = p_idx; p_idx +=  3; note.append(_('Detail') + ': ' + _('Currency') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 12; note.append(_('Detail') + ': ' + _('Structured format communication') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  2; note.append(_('Detail') + ': ' + _('Country code of the principal') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('Equivalent in EUR') + ': ' + parsefloat(communication[o_idx:p_idx], 3))
            elif type == '106':  # Method of calculation (VAT, withholding tax on income, commission, etc.)
                structured_com = _('Method of calculation (VAT, withholding tax on income, commission, etc.)')
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('equivalent in the currency of the account') + ': ' + parsefloat(communication[o_idx:p_idx], 3))
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('amount on which % is calculated') + ': ' + parsefloat(communication[o_idx:p_idx], 3))
                o_idx = p_idx; p_idx += 12; note.append(_('Detail') + ': ' + _('percent') + ': ' + parsefloat(communication[o_idx:p_idx], 8))
                o_idx = p_idx; p_idx +=  1; note.append(_('Detail') + ': ' + _('minimum') + ': ' + minimum[communication[o_idx:p_idx]])
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('equivalent in EUR') + ': ' + parsefloat(communication[o_idx:p_idx], 3))
            elif type == '108':  # Closing
                structured_com = _('Closing')
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('equivalent in the currency of the account') + ': ' + parsefloat(communication[o_idx:p_idx], 3))
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('interest rates, calculation basis') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 12; note.append(_('Detail') + ': ' + _('interest') + ': ' + parsefloat(communication[o_idx:p_idx], 8))
                o_idx = p_idx; p_idx += 12; note.append(_('Detail') + ': ' + _('period from {} to {}').format(parsedate(communication[o_idx:o_idx+6]), parsedate(communication[o_idx+6:o_idx+12])))
            elif type == '111':  # POS credit – Globalisation
                structured_com = _('POS credit – Globalisation')
                o_idx = p_idx; p_idx +=  1; note.append(_('Detail') + ': ' + _('card scheme') + ': ' + card_scheme[communication[o_idx:p_idx]])
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('POS number') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  3; note.append(_('Detail') + ': ' + _('period number') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('sequence number of first transaction') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('date of first transaction') + ': ' + parsedate(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('sequence number of last transaction') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('date of last transaction') + ': ' + parsedate(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  1; note.append(_('Detail') + ': ' + _('transaction type') + ': ' + transaction_type[communication[o_idx:p_idx]])
                o_idx = p_idx; p_idx += 26; note.append(_('Detail') + ': ' + _('identification of terminal') + ': ' + parse_terminal(communication[o_idx:p_idx]))
            elif type == '113':  # ATM/POS debit
                structured_com = _('ATM/POS debit')
                o_idx = p_idx; p_idx += 16; note.append(_('Detail') + ': ' + _('Masked PAN or card number') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  1; note.append(_('Detail') + ': ' + _('card scheme') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('terminal number') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('sequence number of transaction') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('date of transaction') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  4; note.append(_('Detail') + ': ' + _('hour of transaction') + ': ' + parsehour(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  1; note.append(_('Detail') + ': ' + _('transaction type') + ': ' + transaction_type[communication[o_idx:p_idx]])
                o_idx = p_idx; p_idx += 26; note.append(_('Detail') + ': ' + _('identification of terminal') + ': ' + parse_terminal(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('original amount') + ': ' + parsefloat(communication[o_idx:p_idx], 3))
                o_idx = p_idx; p_idx += 12; note.append(_('Detail') + ': ' + _('rate') + ': ' + parsefloat(communication[o_idx:p_idx], 8))
                o_idx = p_idx; p_idx +=  3; note.append(_('Detail') + ': ' + _('currency') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  5; note.append(_('Detail') + ': ' + _('volume') + ': ' + parsefloat(communication[o_idx:p_idx], 2))
                o_idx = p_idx; p_idx +=  2; note.append(_('Detail') + ': ' + _('product code') + ': ' + product_code[communication[o_idx:p_idx]])
                o_idx = p_idx; p_idx +=  5; note.append(_('Detail') + ': ' + _('unit price') + ': ' + parsefloat(communication[o_idx:p_idx], 3))
            elif type == '114':  # POS credit - individual transaction
                structured_com = _('POS credit - individual transaction')
                o_idx = p_idx; p_idx +=  1; note.append(_('Detail') + ': ' + _('card scheme') + ': ' + card_scheme[communication[o_idx:p_idx]])
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('POS number') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  3; note.append(_('Detail') + ': ' + _('period number') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('sequence number of transaction') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('date of transaction') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  4; note.append(_('Detail') + ': ' + _('hour of transaction') + ': ' + parsehour(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  1; note.append(_('Detail') + ': ' + _('transaction type') + ': ' + transaction_type[communication[o_idx:p_idx]])
                o_idx = p_idx; p_idx += 26; note.append(_('Detail') + ': ' + _('identification of terminal') + ': ' + parse_terminal(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 16; note.append(_('Detail') + ': ' + _('reference of transaction') + ': ' + rmspaces(communication[o_idx:p_idx]))
            elif type == '115':  # Terminal cash deposit
                structured_com = _('Terminal cash deposit')
                o_idx = p_idx; p_idx += 16; note.append(_('Detail') + ': ' + _('PAN or card number') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  1; note.append(_('Detail') + ': ' + _('card scheme') + ': ' + card_scheme[communication[o_idx:p_idx]])
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('terminal number') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('sequence number of transaction') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('payment day') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  4; note.append(_('Detail') + ': ' + _('hour of payment') + ': ' + parsehour(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('validation date') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('sequence number of validation') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('original amount (given by the customer)') + ': ' + parsefloat(communication[o_idx:p_idx], 3))
                o_idx = p_idx; p_idx +=  1; note.append(_('Detail') + ': ' + _('conformity code or blank') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 26; note.append(_('Detail') + ': ' + _('identification of terminal') + ': ' + parse_terminal(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 12; note.append(_('Detail') + ': ' + _('message (structured of free)') + ': ' + rmspaces(communication[o_idx:p_idx]))
            elif type == '121':  # Commercial bills
                structured_com = _('Commercial bills')
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('amount of the bill') + ': ' + parsefloat(communication[o_idx:p_idx], 3))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('maturity date of the bill') + ': ' + parsedate(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('conventional maturity date') + ': ' + parsedate(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('date of issue of the bill') + ': ' + parsedate(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 11; note.append(_('Detail') + ': ' + _('company number') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  3; note.append(_('Detail') + ': ' + _('currency') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  3;  # blanks
                o_idx = p_idx; p_idx += 13; note.append(_('Detail') + ': ' + _('number of the bill') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 12; note.append(_('Detail') + ': ' + _('exchange rate') + ': ' + parsefloat(communication[o_idx:p_idx], 8))
            elif type == '122':  # Bills - calculation of interest
                structured_com = _('Bills - calculation of interest')
                o_idx = p_idx; p_idx +=  4; note.append(_('Detail') + ': ' + _('number of days') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 12; note.append(_('Detail') + ': ' + _('interest rate') + ': ' + parsefloat(communication[o_idx:p_idx], 8))
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('basic amount of the calculation') + ': ' + parsefloat(communication[o_idx:p_idx], 3))
                o_idx = p_idx; p_idx +=  1; note.append(_('Detail') + ': ' + _('minimum rate') + ': ' + minimum[communication[o_idx:p_idx]])
                o_idx = p_idx; p_idx += 13; note.append(_('Detail') + ': ' + _('number of the bill') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('maturity date of the bill') + ': ' + parsedate(communication[o_idx:p_idx]))
            elif type == '123':  # Fees and commissions
                structured_com = _('Fees and commissions')
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('starting date') + ': ' + parsedate(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('maturity date') + ': ' + parsedate(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('basic amount') + ': ' + parsefloat(communication[o_idx:p_idx], 3))
                o_idx = p_idx; p_idx += 12; note.append(_('Detail') + ': ' + _('percentage') + ': ' + parsefloat(communication[o_idx:p_idx], 8))
                o_idx = p_idx; p_idx +=  4; note.append(_('Detail') + ': ' + _('term in days') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  1; note.append(_('Detail') + ': ' + _('minimum rate') + ': ' + minimum[communication[o_idx:p_idx]])
                o_idx = p_idx; p_idx += 13; note.append(_('Detail') + ': ' + _('guarantee number (no. allocated by the bank)') + ': ' + rmspaces(communication[o_idx:p_idx]))
            elif type == '124':  # Number of the credit card
                structured_com = _('Number of the credit card')
                o_idx = p_idx; p_idx += 20; note.append(_('Detail') + ': ' + _('Masked PAN or card number') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  1; note.append(_('Detail') + ': ' + _('issuing institution') + ': ' + issuing_institution[communication[o_idx:p_idx]])
                o_idx = p_idx; p_idx += 12; note.append(_('Detail') + ': ' + _('invoice number') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('identification number') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('date') + ': ' + parsedate(communication[o_idx:p_idx]))
            elif type == '125':  # Credit
                structured_com = _('Credit')
                o_idx = p_idx; p_idx += 12; note.append(_('Detail') + ': ' + _('account number of the credit') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('extension zone of account number of the credit') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('old balance of the credit') + ': ' + parsefloat(communication[o_idx:p_idx], 3))
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('new balance of the credit') + ': ' + parsefloat(communication[o_idx:p_idx], 3))
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('amount (equivalent in foreign currency)') + ': ' + parsefloat(communication[o_idx:p_idx], 3))
                o_idx = p_idx; p_idx +=  3; note.append(_('Detail') + ': ' + _('currency') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('starting date') + ': ' + parsedate(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('end date') + ': ' + parsedate(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 12; note.append(_('Detail') + ': ' + _('nominal interest rate or rate of charge') + ': ' + parsefloat(communication[o_idx:p_idx], 8))
                o_idx = p_idx; p_idx += 13; note.append(_('Detail') + ': ' + _('reference of transaction on credit account') + ': ' + rmspaces(communication[o_idx:p_idx]))
            elif type == '126':  # Term Investments
                structured_com = _('Term Investments')
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('deposit number') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('deposit amount') + ': ' + parsefloat(communication[o_idx:p_idx], 3))
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('equivalent in the currency of the account') + ': ' + parsefloat(communication[o_idx:p_idx], 3))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('starting date') + ': ' + parsedate(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('end date') + ': ' + parsedate(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 12; note.append(_('Detail') + ': ' + _('interest rate') + ': ' + parsefloat(communication[o_idx:p_idx], 8))
                o_idx = p_idx; p_idx += 15; note.append(_('Detail') + ': ' + _('amount of interest') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  3; note.append(_('Detail') + ': ' + _('currency') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 12; note.append(_('Detail') + ': ' + _('rate') + ': ' + parsefloat(communication[o_idx:p_idx], 8))
            elif type == '127':  # SEPA
                structured_com = _('SEPA Direct Debit')
                o_idx = p_idx; p_idx +=  6; note.append(_('Detail') + ': ' + _('Settlement Date') + ': ' + parsedate(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  1; note.append(_('Detail') + ': ' + _('Type Direct Debit') + ': ' + type_direct_debit[communication[o_idx:p_idx]])
                o_idx = p_idx; p_idx +=  1; note.append(_('Detail') + ': ' + _('Direct Debit scheme') + ': ' + direct_debit_scheme[communication[o_idx:p_idx]])
                o_idx = p_idx; p_idx +=  1; note.append(_('Detail') + ': ' + _('Paid or reason for refused payment') + ': ' + payment_reason[communication[o_idx:p_idx]])
                o_idx = p_idx; p_idx += 35; note.append(_('Detail') + ': ' + _('Creditor’s identification code') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 35; note.append(_('Detail') + ': ' + _('Mandate reference') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx += 62; note.append(_('Detail') + ': ' + _('Communicaton') + ': ' + rmspaces(communication[o_idx:p_idx]))
                o_idx = p_idx; p_idx +=  1; note.append(_('Detail') + ': ' + _('Type of R transaction') + ': ' + sepa_type[communication[o_idx:p_idx]])
                o_idx = p_idx; p_idx +=  4; note.append(_('Detail') + ': ' + _('Reason') + ': ' + rmspaces(communication[o_idx:p_idx]))
            else:
                structured_com = _('Type of structured communication not supported: ' + type)
                note.append(communication)
            return structured_com, note

        pattern = re.compile("[\u0020-\u1EFF\n\r]+")  # printable characters
        # Try different encodings for the file
        for encoding in ('cp850', 'cp858', 'cp1140', 'cp1252', 'iso8859_15', 'utf_32', 'utf_16', 'utf_8', 'windows-1252'):
            try:
                record_data = data_file.decode(encoding)
            except UnicodeDecodeError:
                continue
            if pattern.fullmatch(record_data, re.MULTILINE):
                break  # We only have printable characters, stick with this one

        recordlist = record_data.split(u'\n')
        statements = []
        globalisation_comm = {}
        for line in recordlist:
            if not line:
                pass
            elif line[0] == '0':
                #Begin of a new Bank statement
                statement = {}
                statements.append(statement)
                statement['version'] = line[127]
                if statement['version'] not in ['1', '2']:
                    raise UserError(_('Error') + ' R001: ' + _('CODA V%s statements are not supported, please contact your bank') % statement['version'])
                statement['globalisation_stack'] = []
                statement['lines'] = []
                statement['date'] = time.strftime(tools.DEFAULT_SERVER_DATE_FORMAT, time.strptime(rmspaces(line[5:11]), '%d%m%y'))
                statement['separateApplication'] = rmspaces(line[83:88])
            elif line[0] == '1':
                #Statement details
                if statement['version'] == '1':
                    statement['acc_number'] = rmspaces(line[5:17])
                    statement['currency'] = rmspaces(line[18:21])
                elif statement['version'] == '2':
                    if line[1] == '0':  # Belgian bank account BBAN structure
                        statement['acc_number'] = rmspaces(line[5:17])
                        # '11' and '14' stand respecively for characters 'B' and 'E', it's a constant for Belgium, that we need to append to the account number before computing the check digits
                        statement['acc_number'] = 'BE%02d' % (98 - int(statement['acc_number'] + '111400') % 97) + statement['acc_number']
                        statement['currency'] = rmspaces(line[18:21])
                    elif line[1] == '1':  # foreign bank account BBAN structure
                        raise UserError(_('Error') + ' R1001: ' + _('Foreign bank accounts with BBAN structure are not supported '))
                    elif line[1] == '2':    # Belgian bank account IBAN structure
                        statement['acc_number'] = rmspaces(line[5:21])
                        statement['currency'] = rmspaces(line[39:42])
                    elif line[1] == '3':    # foreign bank account IBAN structure
                        raise UserError(_('Error') + ' R1002: ' + _('Foreign bank accounts with IBAN structure are not supported '))
                    else:  # Something else, not supported
                        raise UserError(_('Error') + ' R1003: ' + _('Unsupported bank account structure '))
                statement['description'] = rmspaces(line[90:125])
                statement['balance_start'] = float(rmspaces(line[43:58])) / 1000
                if line[42] == '1':  # 1 = Debit, the starting balance is negative
                    statement['balance_start'] = - statement['balance_start']
                statement['balance_start_date'] = time.strftime(tools.DEFAULT_SERVER_DATE_FORMAT, time.strptime(rmspaces(line[58:64]), '%d%m%y')) if rmspaces(line[58:64]) != '000000' else statement['date']
                statement['accountHolder'] = rmspaces(line[64:90])
                statement['paperSeqNumber'] = rmspaces(line[2:5])
                statement['codaSeqNumber'] = rmspaces(line[125:128])
            elif line[0] == '2':
                if line[1] == '1':
                    #New statement line
                    statementLine = {}
                    statementLine['ref'] = rmspaces(line[2:10])
                    statementLine['ref_move'] = rmspaces(line[2:6])
                    statementLine['ref_move_detail'] = rmspaces(line[6:10])
                    statementLine['sequence'] = len(statement['lines']) + 1
                    statementLine['transactionRef'] = rmspaces(line[10:31])
                    statementLine['debit'] = line[31]  # 0 = Credit, 1 = Debit
                    statementLine['amount'] = float(rmspaces(line[32:47])) / 1000
                    if statementLine['debit'] == '1':
                        statementLine['amount'] = - statementLine['amount']
                    statementLine['transactionDate'] = time.strftime(tools.DEFAULT_SERVER_DATE_FORMAT, time.strptime(rmspaces(line[47:53]), '%d%m%y')) if rmspaces(line[47:53]) != '000000' else statement['date']
                    statementLine['transaction_type'] = int(rmspaces(line[53:54]))
                    statementLine['transaction_family'] = rmspaces(line[54:56])
                    statementLine['transaction_code'] = rmspaces(line[56:58])
                    statementLine['transaction_category'] = rmspaces(line[58:61])
                    if line[61] == '1':
                        #Structured communication
                        statementLine['communication_struct'] = True
                        statementLine['communication_type'] = line[62:65]
                        statementLine['communication'] = line[65:115]
                    else:
                        #Non-structured communication
                        statementLine['communication_struct'] = False
                        statementLine['communication'] = rmspaces(line[62:115])
                    statementLine['entryDate'] = time.strftime(tools.DEFAULT_SERVER_DATE_FORMAT, time.strptime(rmspaces(line[115:121]), '%d%m%y'))
                    statementLine['type'] = 'normal'
                    statementLine['globalisation'] = int(line[124])
                    if statementLine['globalisation'] > 0:
                        if statementLine['ref_move'] in statement['globalisation_stack']:
                            statement['globalisation_stack'].remove(statementLine['ref_move'])
                        else:
                            statementLine['type'] = 'globalisation'
                            statement['globalisation_stack'].append(statementLine['ref_move'])
                            globalisation_comm[statementLine['ref_move']] = statementLine['communication']
                    if not statementLine.get('communication'):
                        statementLine['communication'] = globalisation_comm.get(statementLine['ref_move'], '')
                    statement['lines'].append(statementLine)
                elif line[1] == '2':
                    if statement['lines'][-1]['ref'][0:4] != line[2:6]:
                        raise UserError(_('Error') + 'R2004: ' + _('CODA parsing error on movement data record 2.2, seq nr %s! Please report this issue via your Odoo support channel.') % line[2:10])
                    statement['lines'][-1]['communication'] += line[10:63]
                    statement['lines'][-1]['payment_reference'] = rmspaces(line[63:98])
                    statement['lines'][-1]['counterparty_bic'] = rmspaces(line[98:109])
                    # TODO 113, 114-117, 118-121, 122-125
                elif line[1] == '3':
                    if statement['lines'][-1]['ref'][0:4] != line[2:6]:
                        raise UserError(_('Error') + 'R2005: ' + _('CODA parsing error on movement data record 2.3, seq nr %s! Please report this issue via your Odoo support channel.') % line[2:10])
                    if statement['version'] == '1':
                        statement['lines'][-1]['counterpartyNumber'] = rmspaces(line[10:22])
                        statement['lines'][-1]['counterpartyName'] = rmspaces(line[47:73])
                        statement['lines'][-1]['counterpartyAddress'] = rmspaces(line[73:125])
                        statement['lines'][-1]['counterpartyCurrency'] = ''
                    else:
                        if line[22] == ' ':
                            statement['lines'][-1]['counterpartyNumber'] = rmspaces(line[10:22])
                            statement['lines'][-1]['counterpartyCurrency'] = rmspaces(line[23:26])
                        else:
                            statement['lines'][-1]['counterpartyNumber'] = rmspaces(line[10:44])
                            statement['lines'][-1]['counterpartyCurrency'] = rmspaces(line[44:47])
                        statement['lines'][-1]['counterpartyName'] = rmspaces(line[47:82])
                        statement['lines'][-1]['communication'] += line[82:125]
                else:
                    # movement data record 2.x (x != 1,2,3)
                    raise UserError(_('Error') + 'R2006: ' + _('\nMovement data records of type 2.%s are not supported ') % line[1])
            elif line[0] == '3':
                if line[1] == '1':
                    infoLine = {}
                    infoLine['entryDate'] = statement['lines'][-1]['entryDate']
                    infoLine['type'] = 'information'
                    infoLine['sequence'] = len(statement['lines']) + 1
                    infoLine['ref'] = rmspaces(line[2:10])
                    infoLine['ref_move'] = rmspaces(line[2:6])
                    infoLine['ref_move_detail'] = rmspaces(line[6:10])
                    infoLine['transactionRef'] = rmspaces(line[10:31])
                    infoLine['transaction_family'] = rmspaces(line[32:34])
                    infoLine['transaction_code'] = rmspaces(line[34:36])
                    infoLine['transaction_category'] = rmspaces(line[36:39])
                    if line[39] == '1':
                        #Structured communication
                        infoLine['communication_struct'] = True
                        infoLine['communication_type'] = line[40:43]
                        infoLine['communication'] = line[43:113]
                    else:
                        #Non-structured communication
                        infoLine['communication_struct'] = False
                        infoLine['communication'] = line[40:113]
                    statement['lines'].append(infoLine)
                elif line[1] == '2':
                    if infoLine['ref'] != rmspaces(line[2:10]):
                        raise UserError(_('Error') + 'R3004: ' + _('CODA parsing error on information data record 3.2, seq nr %s! Please report this issue via your Odoo support channel.') % line[2:10])
                    statement['lines'][-1]['communication'] += rmspaces(line[10:115])
                elif line[1] == '3':
                    if infoLine['ref'] != rmspaces(line[2:10]):
                        raise UserError(_('Error') + 'R3005: ' + _('CODA parsing error on information data record 3.3, seq nr %s! Please report this issue via your Odoo support channel.') % line[2:10])
                    statement['lines'][-1]['communication'] += rmspaces(line[10:100])
            elif line[0] == '4':
                    comm_line = {}
                    comm_line['type'] = 'communication'
                    comm_line['sequence'] = len(statement['lines']) + 1
                    comm_line['ref'] = rmspaces(line[2:10])
                    comm_line['ref_move'] = rmspaces(line[2:6])
                    comm_line['ref_move_detail'] = rmspaces(line[6:10])
                    comm_line['communication'] = line[32:112]
                    statement['lines'].append(comm_line)
            elif line[0] == '8':
                # new balance record
                statement['debit'] = line[41]
                statement['paperSeqNumber'] = rmspaces(line[1:4])
                statement['balance_end_real'] = float(rmspaces(line[42:57])) / 1000
                statement['balance_end_realDate'] = time.strftime(tools.DEFAULT_SERVER_DATE_FORMAT, time.strptime(rmspaces(line[57:63]), '%d%m%y'))
                if statement['debit'] == '1':    # 1=Debit
                    statement['balance_end_real'] = - statement['balance_end_real']
            elif line[0] == '9':
                statement['balanceMin'] = float(rmspaces(line[22:37])) / 1000
                statement['balancePlus'] = float(rmspaces(line[37:52])) / 1000
                if not statement.get('balance_end_real'):
                    statement['balance_end_real'] = statement['balance_start'] + statement['balancePlus'] - statement['balanceMin']
        ret_statements = []
        for i, statement in enumerate(statements):
            statement['coda_note'] = ''
            statement_line = []
            statement_data = {
                'name': int(statement['paperSeqNumber']),
                'date': statement['date'],
                'balance_start': statement['balance_start'],
                'balance_end_real': statement['balance_end_real'],
            }
            temp_data = {}
            for line in statement['lines']:
                to_add = statement_line and statement_line[-1]['ref'][:4] == line.get('ref_move') and statement_line[-1] or temp_data
                if line['type'] == 'information':
                    if line['communication_struct']:
                        to_add['note'] = "\n".join([to_add.get('note', ''), 'Communication: '] + parse_structured_communication(line['communication_type'], line['communication'])[1])
                    else:
                        to_add['note'] = "\n".join([to_add.get('note', ''), line['communication']])
                elif line['type'] == 'communication':
                    statement['coda_note'] = "%s[%s] %s\n" % (statement['coda_note'], str(line['ref']), line['communication'])
                elif line['type'] == 'normal'\
                        or (line['type'] == 'globalisation' and line['ref_move'] in statement['globalisation_stack'] and line['transaction_type'] in [1, 2]):
                    note = []
                    if line.get('counterpartyName'):
                        note.append(_('Counter Party') + ': ' + line['counterpartyName'])
                    else:
                        line['counterpartyName'] = False
                    if line.get('counterpartyNumber'):
                        try:
                            if int(line['counterpartyNumber']) == 0:
                                line['counterpartyNumber'] = False
                        except:
                            pass
                        if line['counterpartyNumber']:
                            note.append(_('Counter Party Account') + ': ' + line['counterpartyNumber'])
                    else:
                        line['counterpartyNumber'] = False

                    if line.get('counterpartyAddress'):
                        note.append(_('Counter Party Address') + ': ' + line['counterpartyAddress'])
                    structured_com = False
                    if line['communication_struct']:
                        structured_com, extend_notes = parse_structured_communication(line['communication_type'], line['communication'])
                        note.extend(extend_notes)
                    elif line.get('communication'):
                        note.append(_('Communication') + ': ' + rmspaces(line['communication']))
                    if not self.split_transactions and statement_line and line['ref_move'] == statement_line[-1]['ref'][:4]:
                        to_add['amount'] = to_add.get('amount', 0) + line['amount']
                        to_add['note'] = to_add.get('note', '') + "\n" + "\n".join(note)
                    else:
                        line_data = {
                            'name': structured_com or line.get('communication', '') or '/',
                            'note': "\n".join(note),
                            'transaction_type': parse_operation(line['transaction_type'], line['transaction_family'], line['transaction_code'], line['transaction_category']),
                            'date': line['entryDate'],
                            'amount': line['amount'],
                            'account_number': line.get('counterpartyNumber', None),
                            'partner_name': line['counterpartyName'],
                            'ref': self.split_transactions and line['ref'] or line['ref_move'],
                            'sequence': line['sequence'],
                            'unique_import_id': str(statement['codaSeqNumber']) + '-' + str(statement['date']) + '-' + str(line['ref']),
                        }
                        if temp_data.get('note'):
                            line_data['note'] = temp_data.pop('note') + '\n' + line_data['note']
                        if temp_data.get('amount'):
                            line_data['amount'] += temp_data.pop('amount')
                        statement_line.append(line_data)
            if statement['coda_note'] != '':
                statement_data.update({'coda_note': _('Communication: ') + '\n' + statement['coda_note']})
            statement_data.update({'transactions': statement_line})
            ret_statements.append(statement_data)
        currency_code = statement['currency']
        acc_number = statements[0] and statements[0]['acc_number'] or False
        return currency_code, acc_number, ret_statements
