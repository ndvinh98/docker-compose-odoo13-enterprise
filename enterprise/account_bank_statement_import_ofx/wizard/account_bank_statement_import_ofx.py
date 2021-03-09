# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
import io
import logging
import re
import unicodedata
from xml.etree import ElementTree

try:
    from ofxparse import OfxParser
    from ofxparse.ofxparse import OfxParserException
    OfxParserClass = OfxParser
except ImportError:
    logging.getLogger(__name__).warning("The ofxparse python library is not installed, ofx import will not work.")
    OfxParser = OfxParserException = None
    OfxParserClass = object

from odoo import models, _
from odoo.exceptions import UserError


class PatchedOfxParser(OfxParserClass):
    """ This class monkey-patches the ofxparse library in order to fix the following known bug: ',' is a valid
        decimal separator for amounts, as we can encounter in ofx files made by european banks.
    """

    @classmethod
    def decimal_separator_cleanup(cls_, tag):
        if hasattr(tag, "contents"):
            tag.string = tag.contents[0].replace(',', '.')

    @classmethod
    def parseStatement(cls_, stmt_ofx):
        ledger_bal_tag = stmt_ofx.find('ledgerbal')
        if hasattr(ledger_bal_tag, "contents"):
            balamt_tag = ledger_bal_tag.find('balamt')
            cls_.decimal_separator_cleanup(balamt_tag)
        avail_bal_tag = stmt_ofx.find('availbal')
        if hasattr(avail_bal_tag, "contents"):
            balamt_tag = avail_bal_tag.find('balamt')
            cls_.decimal_separator_cleanup(balamt_tag)
        return super(PatchedOfxParser, cls_).parseStatement(stmt_ofx)

    @classmethod
    def parseTransaction(cls_, txn_ofx):
        amt_tag = txn_ofx.find('trnamt')
        cls_.decimal_separator_cleanup(amt_tag)
        return super(PatchedOfxParser, cls_).parseTransaction(txn_ofx)

    @classmethod
    def parseInvestmentPosition(cls_, ofx):
        tag = ofx.find('units')
        cls_.decimal_separator_cleanup(tag)
        tag = ofx.find('unitprice')
        cls_.decimal_separator_cleanup(tag)
        return super(PatchedOfxParser, cls_).parseInvestmentPosition(ofx)

    @classmethod
    def parseInvestmentTransaction(cls_, ofx):
        tag = ofx.find('units')
        cls_.decimal_separator_cleanup(tag)
        tag = ofx.find('unitprice')
        cls_.decimal_separator_cleanup(tag)
        return super(PatchedOfxParser, cls_).parseInvestmentTransaction(ofx)

    @classmethod
    def parseOfxDateTime(cls_, ofxDateTime):
        res = re.search("^[0-9]*\.([0-9]{0,5})", ofxDateTime)
        if res:
            msec = datetime.timedelta(seconds=float("0." + res.group(1)))
        else:
            msec = datetime.timedelta(seconds=0)

        # Some banks seem to return some OFX dates as YYYY-MM-DD; so we remove
        # the '-' characters to support them as well
        ofxDateTime = ofxDateTime.replace('-', '')

        try:
            local_date = datetime.datetime.strptime(
                ofxDateTime[:14], '%Y%m%d%H%M%S'
            )
            return local_date + msec
        except:
            if ofxDateTime[:8] == "00000000":
                return None

            return datetime.datetime.strptime(
                ofxDateTime[:8], '%Y%m%d') + msec


class AccountBankStatementImport(models.TransientModel):
    _inherit = 'account.bank.statement.import'

    def _check_ofx(self, data_file):
        if data_file.startswith(b"OFXHEADER"):
            #v1 OFX
            return True
        try:
            #v2 OFX
            return b"<ofx>" in data_file.lower()
        except ElementTree.ParseError:
            return False

    def _parse_file(self, data_file):
        if not self._check_ofx(data_file):
            return super(AccountBankStatementImport, self)._parse_file(data_file)
        if OfxParser is None:
            raise UserError(_("The library 'ofxparse' is missing, OFX import cannot proceed."))

        try:
            ofx = PatchedOfxParser.parse(io.BytesIO(data_file))
        except UnicodeDecodeError:
            # Replacing utf-8 chars with ascii equivalent
            encoding = re.findall(b'encoding="(.*?)"', data_file)
            encoding = encoding[0] if len(encoding) > 1 else 'utf-8'
            data_file = unicodedata.normalize('NFKD', data_file.decode(encoding)).encode('ascii', 'ignore')
            ofx = PatchedOfxParser.parse(io.BytesIO(data_file))
        vals_bank_statement = []
        account_lst = set()
        currency_lst = set()
        for account in ofx.accounts:
            account_lst.add(account.number)
            currency_lst.add(account.statement.currency)
            transactions = []
            total_amt = 0.00
            for transaction in account.statement.transactions:
                # Since ofxparse doesn't provide account numbers, we'll have to find res.partner and res.partner.bank here
                # (normal behaviour is to provide 'account_number', which the generic module uses to find partner/bank)
                bank_account_id = partner_id = False
                partner_bank = self.env['res.partner.bank'].search([('partner_id.name', '=', transaction.payee)], limit=1)
                if partner_bank:
                    bank_account_id = partner_bank.id
                    partner_id = partner_bank.partner_id.id
                vals_line = {
                    'date': transaction.date,
                    'name': transaction.payee + (transaction.memo and ': ' + transaction.memo or ''),
                    'ref': transaction.id,
                    'amount': transaction.amount,
                    'unique_import_id': transaction.id,
                    'bank_account_id': bank_account_id,
                    'partner_id': partner_id,
                    'sequence': len(transactions) + 1,
                }
                total_amt += float(transaction.amount)
                transactions.append(vals_line)

            vals_bank_statement.append({
                'transactions': transactions,
                # WARNING: the provided ledger balance is not necessarily the ending balance of the statement
                # see https://github.com/odoo/odoo/issues/3003
                'balance_start': float(account.statement.balance) - total_amt,
                'balance_end_real': account.statement.balance,
            })

        if account_lst and len(account_lst) == 1:
            account_lst = account_lst.pop()
            currency_lst = currency_lst.pop()
        else:
            account_lst = None
            currency_lst = None

        return currency_lst, account_lst, vals_bank_statement
