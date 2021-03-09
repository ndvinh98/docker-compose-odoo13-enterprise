# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import io
import logging
import math
import re
from functools import partial

from lxml import etree

from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Codes from the updated document of 30 june 2017
codes = {
    # ExternalBankTransactionDomain1Code #######################################
    'PMNT': _('Payments'),
    'CAMT': _('Cash Management'),
    'DERV': _('Derivatives'),
    'LDAS': _('Loans, Deposits & Syndications'),
    'FORX': _('Foreign Exchange'),
    'PMET': _('Precious Metal'),
    'CMDT': _('Commodities'),
    'TRAD': _('Trade Services'),
    'SECU': _('Securities'),
    'ACMT': _('Account Management'),
    'XTND': _('Extended Domain'),
    # ExternalBankTransactionFamily1Code #######################################
    'RCDT': _('Received Credit Transfers'),  # Payments
    'ICDT': _('Issued Credit Transfers'),
    'RCCN': _('Received Cash Concentration Transactions'),
    'ICCN': _('Issued Cash Concentration Transactions'),
    'RDDT': _('Received Direct Debits'),
    'IDDT': _('Issued Direct Debits'),
    'RCHQ': _('Received Cheques'),
    'ICHQ': _('Issued Cheques'),
    'CCRD': _('Customer Card Transactions'),
    'MCRD': _('Merchant Card Transactions'),
    'LBOX': _('Lockbox Transactions'),
    'CNTR': _('Counter Transactions'),
    'DRFT': _('Drafts/BillOfOrders'),
    'RRCT': _('Received Real Time Credit Transfer'),
    'IRCT': _('Issued Real Time Credit Transfer'),
    'CAPL': _('Cash Pooling'),  # Cash Management
    'ACCB': _('Account Balancing'),
    'OCRD': _('OTC Derivatives – Credit Derivatives'),  # Derivatives
    'OIRT': _('OTC Derivatives – Interest Rates'),
    'OEQT': _('OTC Derivatives – Equity'),
    'OBND': _('OTC Derivatives – Bonds'),
    'OSED': _('OTC Derivatives – Structured Exotic Derivatives'),
    'OSWP': _('OTC Derivatives – Swaps'),
    'LFUT': _('Listed Derivatives – Futures'),
    'LOPT': _('Listed Derivatives – Options'),
    'FTLN': _('Fixed Term Loans'),  # Loans, Deposits & Syndications
    'NTLN': _('Notice Loans'),
    'FTDP': _('Fixed Term Deposits'),
    'NTDP': _('Notice Deposits'),
    'MGLN': _('Mortgage Loans'),
    'CSLN': _('Consumer Loans'),
    'SYDN': _('Syndications'),
    'SPOT': _('Spots'),  # Foreign Exchange
    'FWRD': _('Forwards'),
    'SWAP': _('Swaps'),
    'FTUR': _('Futures'),
    'NDFX': _('Non Deliverable'),
    'SPOT': _('Spots'),  # Precious Metal
    'FTUR': _('Futures'),
    'OPTN': _('Options'),
    'DLVR': _('Delivery'),
    'SPOT': _('Spots'),  # Commodities
    'FTUR': _('Futures'),
    'OPTN': _('Options'),
    'DLVR': _('Delivery'),
    'LOCT': _('Stand-By Letter Of Credit'),  # Trade Services
    'DCCT': _('Documentary Credit'),
    'CLNC': _('Clean Collection'),
    'DOCC': _('Documentary Collection'),
    'GUAR': _('Guarantees'),
    'SETT': _('Trade, Clearing and Settlement'),  # Securities
    'NSET': _('Non Settled'),
    'BLOC': _('Blocked Transactions'),
    'OTHB': _('CSD Blocked Transactions'),
    'COLL': _('Collateral Management'),
    'CORP': _('Corporate Action'),
    'CUST': _('Custody'),
    'COLC': _('Custody Collection'),
    'LACK': _('Lack'),
    'CASH': _('Miscellaneous Securities Operations'),
    'OPCL': _('Opening & Closing'),  # Account Management
    'ACOP': _('Additional Miscellaneous Credit Operations'),
    'ADOP': _('Additional Miscellaneous Debit Operations'),
    # ExternalBankTransactionSubFamily1Code ####################################
    # Generic Sub-Families
    'FEES': _('Fees'),  # Miscellaneous Credit Operations
    'COMM': _('Commission'),
    'COME': _('Commission excluding taxes'),
    'COMI': _('Commission including taxes'),
    'COMT': _('Non Taxable commissions'),
    'TAXE': _('Taxes'),
    'CHRG': _('Charges'),
    'INTR': _('Interest'),
    'RIMB': _('Reimbursements'),
    'ADJT': _('Adjustments'),
    'FEES': _('Fees'),  # Miscellaneous Debit Operations
    'COMM': _('Commission'),
    'COME': _('Commission excluding taxes'),
    'COMI': _('Commission including taxes'),
    'COMT': _('Non Taxable commissions'),
    'TAXE': _('Taxes'),
    'CHRG': _('Charges'),
    'INTR': _('Interest'),
    'RIMB': _('Reimbursements'),
    'ADJT': _('Adjustments'),
    'IADD': _('Invoice Accepted with Differed Due Date'),
    'FEES': _('Fees'),  # Generic Sub-Families
    'COMM': _('Commission'),
    'COME': _('Commission excluding taxes'),
    'COMI': _('Commission including taxes'),
    'COMT': _('Non Taxable commissions'),
    'TAXE': _('Taxes'),
    'CHRG': _('Charges'),
    'INTR': _('Interest'),
    'RIMB': _('Reimbursements'),
    'DAJT': _('Credit Adjustments'),
    'CAJT': _('Debit Adjustments'),
    # Payments Sub-Families
    'BOOK': _('Internal Book Transfer'),  # Received Credit Transfer
    'STDO': _('Standing Order'),
    'XBST': _('Cross-Border Standing Order'),
    'ESCT': _('SEPA Credit Transfer'),
    'DMCT': _('Domestic Credit Transfer'),
    'XBCT': _('Cross-Border Credit Transfer'),
    'VCOM': _('Credit Transfer with agreed Commercial Information'),
    'FICT': _('Financial Institution Credit Transfer'),
    'PRCT': _('Priority Credit Transfer'),
    'SALA': _('Payroll/Salary Payment'),
    'XBSA': _('Cross-Border Payroll/Salary Payment'),
    'SDVA': _('Same Day Value Credit Transfer'),
    'RPCR': _('Reversal due to Payment Cancellation Request'),
    'RRTN': _('Reversal due to Payment Return/reimbursement of a Credit Transfer'),
    'AUTT': _('Automatic Transfer'),
    'ATXN': _('ACH Transaction'),
    'ACOR': _('ACH Corporate Trade'),
    'APAC': _('ACH Pre-Authorised'),
    'ASET': _('ACH Settlement'),
    'ARET': _('ACH Return'),
    'AREV': _('ACH Reversal'),
    'ACDT': _('ACH Credit'),
    'ADBT': _('ACH Debit'),
    'TTLS': _('Treasury Tax And Loan Service'),
    'BOOK': _('Internal Book Transfer'),  # Issued Credit Transfer
    'STDO': _('Standing Order'),
    'XBST': _('Cross-Border Standing Order'),
    'ESCT': _('SEPA Credit Transfer'),
    'DMCT': _('Domestic Credit Transfer'),
    'XBCT': _('Cross-Border Credit Transfer'),
    'FICT': _('Financial Institution Credit Transfer'),
    'PRCT': _('Priority Credit Transfer'),
    'VCOM': _('Credit Transfer with agreed Commercial Information'),
    'SALA': _('Payroll/Salary Payment'),
    'XBSA': _('Cross-Border Payroll/Salary Payment'),
    'RPCR': _('Reversal due to Payment Cancellation Request'),
    'RRTN': _('Reversal due to Payment Return/reimbursement of a Credit Transfer'),
    'SDVA': _('Same Day Value Credit Transfer'),
    'AUTT': _('Automatic Transfer'),
    'ATXN': _('ACH Transaction'),
    'ACOR': _('ACH Corporate Trade'),
    'APAC': _('ACH Pre-Authorised'),
    'ASET': _('ACH Settlement'),
    'ARET': _('ACH Return'),
    'AREV': _('ACH Reversal'),
    'ACDT': _('ACH Credit'),
    'ADBT': _('ACH Debit'),
    'TTLS': _('Treasury Tax And Loan Service'),
    'COAT': _('Corporate Own Account Transfer'),  # Received Cash Concentration
    'ICCT': _('Intra Company Transfer'),
    'XICT': _('Cross-Border Intra Company Transfer'),
    'FIOA': _('Financial Institution Own Account Transfer'),
    'BACT': _('Branch Account Transfer'),
    'ACON': _('ACH Concentration'),
    'COAT': _('Corporate Own Account Transfer'),  # Issued Cash Concentration
    'ICCT': _('Intra Company Transfer'),
    'XICT': _('Cross-Border Intra Company Transfer'),
    'FIOA': _('Financial Institution Own Account Transfer'),
    'BACT': _('Branch Account Transfer'),
    'ACON': _('ACH Concentration'),
    'PMDD': _('Direct Debit'),  # Received Direct Debit
    'URDD': _('Direct Debit under reserve'),
    'ESDD': _('SEPA Core Direct Debit'),
    'BBDD': _('SEPA B2B Direct Debit'),
    'XBDD': _('Cross-Border Direct Debit'),
    'OODD': _('One-Off Direct Debit'),
    'PADD': _('Pre-Authorised Direct Debit'),
    'FIDD': _('Financial Institution Direct Debit Payment'),
    'RCDD': _('Reversal due to a Payment Cancellation Request'),
    'UPDD': _('Reversal due to Return/Unpaid Direct Debit'),
    'PRDD': _('Reversal due to Payment Reversal'),
    'PMDD': _('Direct Debit Payment'),  # Issued Direct Debit
    'URDD': _('Direct Debit under reserve'),
    'ESDD': _('SEPA Core Direct Debit'),
    'BBDD': _('SEPA B2B Direct Debit'),
    'OODD': _('One-Off Direct Debit'),
    'XBDD': _('Cross-Border Direct Debit'),
    'PADD': _('Pre-Authorised Direct Debit'),
    'FIDD': _('Financial Institution Direct Debit Payment'),
    'RCDD': _('Reversal due to a Payment Cancellation Request'),
    'UPDD': _('Reversal due to Return/Unpaid Direct Debit'),
    'PRDD': _('Reversal due to Payment Reversal'),
    'CCHQ': _('Cheque'),  # Received Cheque
    'URCQ': _('Cheque Under Reserve'),
    'UPCQ': _('Unpaid Cheque'),
    'CQRV': _('Cheque Reversal'),
    'CCCH': _('Certified Customer Cheque'),
    'CLCQ': _('Circular Cheque'),
    'NPCC': _('Non-Presented Circular Cheque'),
    'CRCQ': _('Crossed Cheque'),
    'ORCQ': _('Order Cheque'),
    'OPCQ': _('Open Cheque'),
    'BCHQ': _('Bank Cheque'),
    'XBCQ': _('Foreign Cheque'),
    'XRCQ': _('Foreign Cheque Under Reserve'),
    'XPCQ': _('Unpaid Foreign Cheque'),
    'CDIS': _('Controlled Disbursement'),
    'ARPD': _('ARP Debit'),
    'CASH': _('Cash Letter'),
    'CSHA': _('Cash Letter Adjustment'),
    'CCHQ': _('Cheque'),  # Issued Cheque
    'URCQ': _('Cheque Under Reserve'),
    'UPCQ': _('Unpaid Cheque'),
    'CQRV': _('Cheque Reversal'),
    'CCCH': _('Certified Customer Cheque'),
    'CLCQ': _('Circular Cheque'),
    'NPCC': _('Non-Presented Circular Cheque'),
    'CRCQ': _('Crossed Cheque'),
    'ORCQ': _('Order Cheque'),
    'OPCQ': _('Open Cheque'),
    'BCHQ': _('Bank Cheque'),
    'XBCQ': _('Foreign Cheque'),
    'XRCQ': _('Foreign Cheque Under Reserve'),
    'XPCQ': _('Unpaid Foreign Cheque'),
    'CDIS': _('Controlled Disbursement'),
    'ARPD': _('ARP Debit'),
    'CASH': _('Cash Letter'),
    'CSHA': _('Cash Letter Adjustment'),
    'CWDL': _('Cash Withdrawal'),  # Customer Card Transaction
    'CDPT': _('Cash Deposit'),
    'XBCW': _('Cross-Border Cash Withdrawal'),
    'POSD': _('Point-of-Sale (POS) Payment - Debit Card'),
    'POSC': _('Credit Card Payment'),
    'XBCP': _('Cross-Border Credit Card Payment'),
    'SMRT': _('Smart-Card Payment'),
    'POSP': _('Point-of-Sale (POS) Payment'),  # Merchant Card Transaction
    'POSC': _('Credit Card Payment'),
    'SMCD': _('Smart-Card Payment'),
    'UPCT': _('Unpaid Card Transaction'),
    'CDPT': _('Cash Deposit'),  # Counter Transaction
    'CWDL': _('Cash Withdrawal'),
    'BCDP': _('Branch Deposit'),
    'BCWD': _('Branch Withdrawal'),
    'CHKD': _('Cheque Deposit'),
    'MIXD': _('Mixed Deposit'),
    'MSCD': _('Miscellaneous Deposit'),
    'FCDP': _('Foreign Currency Deposit'),
    'FCWD': _('Foreign Currency Withdrawal'),
    'TCDP': _('Travellers Cheques Deposit'),
    'TCWD': _('Travellers Cheques Withdrawal'),
    'LBCA': _('Credit Adjustment'),  # Lockbox
    'LBDB': _('Debit'),
    'LBDP': _('Deposit'),
    'STAM': _('Settlement at Maturity'),  # Drafts / Bill to Order
    'STLR': _('Settlement under reserve'),
    'DDFT': _('Discounted Draft'),
    'UDFT': _('Dishonoured/Unpaid Draft'),
    'DMCG': _('Draft Maturity Change'),
    'BOOK': _('Internal Book Transfer'),  # Received Real-Time Credit Transfer
    'STDO': _('Standing Order'),
    'XBST': _('Cross-Border Standing Order'),
    'ESCT': _('SEPA Credit Transfer'),
    'DMCT': _('Domestic Credit Transfer'),
    'XBCT': _('Cross-Border Credit Transfer'),
    'VCOM': _('Credit Transfer with agreed Commercial Information'),
    'FICT': _('Financial Institution Credit Transfer'),
    'PRCT': _('Priority Credit Transfer'),
    'SALA': _('Payroll/Salary Payment'),
    'XBSA': _('Cross-Border Payroll/Salary Payment'),
    'SDVA': _('Same Day Value Credit Transfer'),
    'RPCR': _('Reversal due to Payment Cancellation Request'),
    'RRTN': _('Reversal due to Payment Return/reimbursement of a Credit Transfer'),
    'AUTT': _('Automatic Transfer'),
    'ATXN': _('ACH Transaction'),
    'ACOR': _('ACH Corporate Trade'),
    'APAC': _('ACH Pre-Authorised'),
    'ASET': _('ACH Settlement'),
    'ARET': _('ACH Return'),
    'AREV': _('ACH Reversal'),
    'ACDT': _('ACH Credit'),
    'ADBT': _('ACH Debit'),
    'TTLS': _('Treasury Tax And Loan Service'),
    'BOOK': _('Internal Book Transfer'),  # Issued Real-Time Credit Transfer
    'STDO': _('Standing Order'),
    'XBST': _('Cross-Border Standing Order'),
    'ESCT': _('SEPA Credit Transfer'),
    'DMCT': _('Domestic Credit Transfer'),
    'XBCT': _('Cross-Border Credit Transfer'),
    'FICT': _('Financial Institution Credit Transfer'),
    'PRCT': _('Priority Credit Transfer'),
    'VCOM': _('Credit Transfer with agreed Commercial Information'),
    'SALA': _('Payroll/Salary Payment'),
    'XBSA': _('Cross-Border Payroll/Salary Payment'),
    'RPCR': _('Reversal due to Payment Cancellation Request'),
    'RRTN': _('Reversal due to Payment Return/reimbursement of a Credit Transfer'),
    'SDVA': _('Same Day Value Credit Transfer'),
    'AUTT': _('Automatic Transfer'),
    'ATXN': _('ACH Transaction'),
    'ACOR': _('ACH Corporate Trade'),
    'APAC': _('ACH Pre-Authorised'),
    'ASET': _('ACH Settlement'),
    'ARET': _('ACH Return'),
    'AREV': _('ACH Reversal'),
    'ACDT': _('ACH Credit'),
    'ADBT': _('ACH Debit'),
    'TTLS': _('Treasury Tax And Loan Service'),
    # Cash Management Sub-Families
    'XBRD': _('Cross-Border'),  # Cash Pooling
    'ZABA': _('Zero Balancing'),  # Account Balancing
    'SWEP': _('Sweeping'),
    'TOPG': _('Topping'),
    'DSBR': _('Controlled Disbursement'),
    'ODFT': _('Overdraft'),
    'XBRD': _('Cross-Border'),
    # Derivatives Sub-Families
    'SWUF': _('Upfront Payment'),
    'SWRS': _('Reset Payment'),
    'SWPP': _('Partial Payment'),
    'SWFP': _('Final Payment'),
    'SWCC': _('Client Owned Collateral'),
    # Loans, Deposits & Syndications Sub-Families
    'DDWN': _('Drawdown'),
    'RNEW': _('Renewal'),
    'PPAY': _('Principal Payment'),
    'DPST': _('Deposit'),
    'RPMT': _('Repayment'),
    # Trade Services Sub-Families
    'FRZF': _('Freeze of funds'),
    'SOSI': _('Settlement of Sight Import document'),
    'SOSE': _('Settlement of Sight Export document'),
    'SABG': _('Settlement against bank guarantee'),
    'STLR': _('Settlement under reserve'),
    'STLR': _('Settlement under reserve'),
    'STAC': _('Settlement after collection'),
    'STLM': _('Settlement'),
    # Securities Sub-Families
    'PAIR': _('Pair-Off'),  # Trade, Clearing and Settlement & Non Settled
    'TRAD': _('Trade'),
    'NETT': _('Netting'),
    'TRPO': _('Triparty Repo'),
    'TRVO': _('Triparty Reverse Repo'),
    'RVPO': _('Reverse Repo'),
    'REPU': _('Repo'),
    'SECB': _('Securities Borrowing'),
    'SECL': _('Securities Lending'),
    'BSBO': _('Buy Sell Back'),
    'BSBC': _('Sell Buy Back'),
    'FCTA': _('Factor Update'),
    'ISSU': _('Depositary Receipt Issue'),
    'INSP': _('Inspeci/Share Exchange'),
    'OWNE': _('External Account Transfer'),
    'OWNI': _('Internal Account Transfer'),
    'NSYN': _('Non Syndicated'),
    'PLAC': _('Placement'),
    'PORT': _('Portfolio Move'),
    'SYND': _('Syndicated'),
    'TBAC': _('TBA closing'),
    'TURN': _('Turnaround'),
    'REDM': _('Redemption'),
    'SUBS': _('Subscription'),
    'CROS': _('Cross Trade'),
    'SWIC': _('Switch'),
    'REAA': _('Redemption Asset Allocation'),
    'SUAA': _('Subscription Asset Allocation'),
    'PRUD': _('Principal Pay-down/pay-up'),
    'TOUT': _('Transfer Out'),
    'TRIN': _('Transfer In'),
    'XCHC': _('Exchange Traded CCP'),
    'XCHG': _('Exchange Traded'),
    'XCHN': _('Exchange Traded Non-CCP'),
    'OTCC': _('OTC CCP'),
    'OTCG': _('OTC'),
    'OTCN': _('OTC Non-CCP'),
    'XCHC': _('Exchange Traded CCP'),  # Blocked Transactions & CSD Blocked Transactions
    'XCHG': _('Exchange Traded'),
    'XCHN': _('Exchange Traded Non-CCP'),
    'OTCC': _('OTC CCP'),
    'OTCG': _('OTC'),
    'OTCN': _('OTC Non-CCP'),
    'MARG': _('Margin Payments'),  # Collateral Management
    'TRPO': _('Triparty Repo'),
    'REPU': _('Repo'),
    'SECB': _('Securities Borrowing'),
    'SECL': _('Securities Lending'),
    'OPBC': _('Option broker owned collateral'),
    'OPCC': _('Option client owned collateral'),
    'FWBC': _('Forwards broker owned collateral'),
    'FWCC': _('Forwards client owned collateral'),
    'MGCC': _('Margin client owned cash collateral'),
    'SWBC': _('Swap broker owned collateral'),
    'EQCO': _('Equity mark client owned'),
    'EQBO': _('Equity mark broker owned'),
    'CMCO': _('Corporate mark client owned'),
    'CMBO': _('Corporate mark broker owned'),
    'SLBC': _('Lending Broker Owned Cash Collateral'),
    'SLCC': _('Lending Client Owned Cash Collateral'),
    'CPRB': _('Corporate Rebate'),
    'BIDS': _('Repurchase offer/Issuer Bid/Reverse Rights.'),  # Corporate Action & Custody
    'BONU': _('Bonus Issue/Capitalisation Issue'),
    'BPUT': _('Put Redemption'),
    'CAPG': _('Capital Gains Distribution'),
    'CONV': _('Conversion'),
    'DECR': _('Decrease in Value'),
    'DRAW': _('Drawing'),
    'DRIP': _('Dividend Reinvestment'),
    'DTCH': _('Dutch Auction'),
    'DVCA': _('Cash Dividend'),
    'DVOP': _('Dividend Option'),
    'EXOF': _('Exchange'),
    'EXRI': _('Call on intermediate securities'),
    'EXWA': _('Warrant Exercise/Warrant Conversion'),
    'INTR': _('Interest Payment'),
    'LIQU': _('Liquidation Dividend / Liquidation Payment'),
    'MCAL': _('Full Call / Early Redemption'),
    'MRGR': _('Merger'),
    'ODLT': _('Odd Lot Sale/Purchase'),
    'PCAL': _('Partial Redemption with reduction of nominal value'),
    'PRED': _('Partial Redemption Without Reduction of Nominal Value'),
    'PRII': _('Interest Payment with Principle'),
    'PRIO': _('Priority Issue'),
    'REDM': _('Final Maturity'),
    'RHTS': _('Rights Issue/Subscription Rights/Rights Offer'),
    'SHPR': _('Equity Premium Reserve'),
    'TEND': _('Tender'),
    'TREC': _('Tax Reclaim'),
    'RWPL': _('Redemption Withdrawing Plan'),
    'SSPL': _('Subscription Savings Plan'),
    'CSLI': _('Cash in lieu'),
    'CHAR': _('Charge/fees'),  # Miscellaneous Securities Operations
    'BKFE': _('Bank Fees'),
    'CLAI': _('Compensation/Claims'),
    'MNFE': _('Management Fees'),
    'OVCH': _('Overdraft Charge'),
    'TRFE': _('Transaction Fees'),
    'UNCO': _('Underwriting Commission'),
    'STAM': _('Stamp duty'),
    'WITH': _('Withholding Tax'),
    'BROK': _('Brokerage fee'),
    'PRIN': _('Interest Payment with Principle'),
    'TREC': _('Tax Reclaim'),
    'GEN1': _('Withdrawal/distribution'),
    'GEN2': _('Deposit/Contribution'),
    'ERWI': _('Borrowing fee'),
    'ERWA': _('Lending income'),
    'SWEP': _('Sweep'),
    'SWAP': _('Swap Payment'),
    'FUTU': _('Future Variation Margin'),
    'RESI': _('Futures Residual Amount'),
    'FUCO': _('Futures Commission'),
    'INFD': _('Fixed Deposit Interest Amount'),
    # Account Management Sub-Families
    'ACCO': _('Account Opening'),
    'ACCC': _('Account Closing'),
    'ACCT': _('Account Transfer'),
    'VALD': _('Value Date'),
    'BCKV': _('Back Value'),
    'YTDA': _('YTD Adjustment'),
    'FLTA': _('Float adjustment'),
    'ERTA': _('Exchange Rate Adjustment'),
    'PSTE': _('Posting Error'),
    # General
    'NTAV': _('Not available'),
    'OTHR': _('Other'),
    'MCOP': _('Miscellaneous Credit Operations'),
    'MDOP': _('Miscellaneous Debit Operations'),
}


def _generic_get(*nodes, xpath, namespaces, placeholder=None):
    if placeholder is not None:
        xpath = xpath.format(placeholder=placeholder)
    for node in nodes:
        item = node.xpath(xpath, namespaces=namespaces)
        if item:
            return item[0]
    return False

_get_amount = partial(_generic_get,
    xpath='ns:Amt/text() | ns:AmtDtls/ns:TxAmt/ns:Amt/text()')

_get_credit_debit_indicator = partial(_generic_get,
    xpath='ns:CdtDbtInd/text()')

_get_transaction_date = partial(_generic_get,
    xpath=('ns:ValDt/ns:Dt/text()'
           '| ns:BookgDt/ns:Dt/text()'
           '| ns:BookgDt/ns:DtTm/text()'))

_get_partner_name = partial(_generic_get,
    xpath='.//ns:RltdPties/ns:{placeholder}/ns:Nm/text()')

_get_account_number = partial(_generic_get,
    xpath=('.//ns:RltdPties/ns:{placeholder}Acct/ns:Id/ns:IBAN/text()'
           '| (.//ns:{placeholder}Acct/ns:Id/ns:Othr/ns:Id)[1]/text()'))

_get_main_ref = partial(_generic_get,
    xpath='.//ns:RmtInf/ns:Strd/ns:{placeholder}RefInf/ns:Ref/text()')

_get_other_ref = partial(_generic_get,
    xpath=('ns:AcctSvcrRef/text()'
           '| {placeholder}ns:Refs/ns:TxId/text()'
           '| {placeholder}ns:Refs/ns:InstrId/text()'
           '| {placeholder}ns:Refs/ns:EndToEndId/text()'
           '| {placeholder}ns:Refs/ns:MndtId/text()'
           '| {placeholder}ns:Refs/ns:ChqNb/text()'))

_get_additional_entry_info = partial(_generic_get,
    xpath='ns:AddtlNtryInf/text()')

def _get_signed_amount(*nodes, namespaces):
    amount = float(_get_amount(*nodes, namespaces=namespaces))
    sign = _get_credit_debit_indicator(*nodes, namespaces=namespaces)
    return amount if sign == 'CRDT' else -amount

def _get_counter_party(*nodes, namespaces):
    ind = _get_credit_debit_indicator(*nodes, namespaces=namespaces)
    return 'Dbtr' if ind == 'CRDT' else 'Cdtr'

def _set_amount_currency_and_currency_id(node, path, entry_vals, currency, curr_cache, has_multi_currency, namespaces):
    instruc_amount = node.xpath('%s/text()' % path, namespaces=namespaces)
    instruc_curr = node.xpath('%s/@Ccy' % path, namespaces=namespaces)
    if (has_multi_currency and instruc_amount and instruc_curr and
            instruc_curr[0] != currency and instruc_curr[0] in curr_cache):
        entry_vals['amount_currency'] = math.copysign(abs(sum(map(float, instruc_amount))), entry_vals['amount'])
        entry_vals['currency_id'] = curr_cache[instruc_curr[0]]

def _get_transaction_name(node, namespaces):
    xpaths = ('.//ns:RmtInf/ns:Ustrd/text()',
              './/ns:RmtInf/ns:Strd/ns:CdtrRefInf/ns:Ref/text()',
               'ns:AddtlNtryInf/text()')
    for xpath in xpaths:
        transaction_name = node.xpath(xpath, namespaces=namespaces)
        if transaction_name:
            return ' '.join(transaction_name)
    return '/'

def _get_ref(node, counter_party, prefix, namespaces):
    ref = _get_main_ref(node, placeholder=counter_party, namespaces=namespaces)
    if ref is False:  # Explicitely match False, not a falsy value
        ref = _get_other_ref(node, placeholder=prefix, namespaces=namespaces)
    return ref

def _get_unique_import_id(entry, sequence, name, date, unique_import_set, namespaces):
    unique_import_ref = entry.xpath('ns:AcctSvcrRef/text()', namespaces=namespaces)
    if unique_import_ref and not _is_full_of_zeros(unique_import_ref[0]) and unique_import_ref[0] != 'NOTPROVIDED':
        entry_ref = entry.xpath('ns:NtryRef/text()', namespaces=namespaces)
        if entry_ref:
            return '{}-{}'.format(unique_import_ref[0], entry_ref[0])
        elif not entry_ref and unique_import_ref[0] not in unique_import_set:
            return unique_import_ref[0]
        else:
            return '{}-{}'.format(unique_import_ref[0], sequence)
    else:
        return '{}-{}-{}'.format(name, date, sequence)

def _get_transaction_type(node, namespaces):
    code = node.xpath('ns:Domn/ns:Cd/text()', namespaces=namespaces)
    family = node.xpath('ns:Domn/ns:Fmly/ns:Cd/text()', namespaces=namespaces)
    subfamily = node.xpath('ns:Domn/ns:Fmly/ns:SubFmlyCd/text()', namespaces=namespaces)
    if code:
        return {'transaction_type': "{code}: {family} ({subfamily})".format(
            code=codes[code[0]],
            family=family and codes[family[0]] or '',
            subfamily=subfamily and codes[subfamily[0]] or '',
        )}
    return {}

def _get_partner_address(node, ns, ph):
    StrtNm = node.xpath('ns:RltdPties/ns:{}/ns:PstlAdr/ns:StrtNm/text()'.format(ph), namespaces=ns)
    BldgNb = node.xpath('ns:RltdPties/ns:{}/ns:PstlAdr/ns:BldgNb/text()'.format(ph), namespaces=ns)
    PstCd = node.xpath('ns:RltdPties/ns:{}/ns:PstlAdr/ns:PstCd/text()'.format(ph), namespaces=ns)
    TwnNm = node.xpath('ns:RltdPties/ns:{}/ns:PstlAdr/ns:TwnNm/text()'.format(ph), namespaces=ns)
    Ctry = node.xpath('ns:RltdPties/ns:{}/ns:PstlAdr/ns:Ctry/text()'.format(ph), namespaces=ns)
    AdrLine = node.xpath('ns:RltdPties/ns:{}/ns:PstlAdr/ns:AdrLine/text()'.format(ph), namespaces=ns)
    address = "\n".join(AdrLine)
    if StrtNm:
        address = "\n".join([address, ", ".join(StrtNm + BldgNb)])
    if PstCd or TwnNm:
        address = "\n".join([address, " ".join(PstCd + TwnNm)])
    if Ctry:
        address = "\n".join([address, Ctry[0]])
    return address

def _is_full_of_zeros(strg):
    pattern_zero = re.compile('^0+$')
    return bool(pattern_zero.match(strg))

class AccountBankStatementImport(models.TransientModel):
    _inherit = 'account.bank.statement.import'

    def _check_camt(self, data_file):
        try:
            root = etree.parse(io.BytesIO(data_file)).getroot()
        except:
            return None
        if root.tag.find('camt.053') != -1:
            return root
        return None

    def _parse_file(self, data_file):
        root = self._check_camt(data_file)
        if root is not None:
            return self._parse_file_camt(root)
        return super(AccountBankStatementImport, self)._parse_file(data_file)

    def _parse_file_camt(self, root):
        ns = {k or 'ns': v for k, v in root.nsmap.items()}

        curr_cache = {c['name']: c['id'] for c in self.env['res.currency'].search_read([], ['id', 'name'])}
        statements_per_iban = {}
        currency_per_iban = {}
        unique_import_set = set([])
        currency = account_no = False
        has_multi_currency = self.env.user.user_has_groups('base.group_multi_currency')
        for statement in root[0].findall('ns:Stmt', ns):
            statement_vals = {}
            statement_vals['name'] = statement.xpath('ns:Id/text()', namespaces=ns)[0]
            statement_vals['date'] = (statement.xpath("ns:Bal/ns:Tp/ns:CdOrPrtry[ns:Cd='CLBD']/../../ns:Dt/ns:Dt/text()", namespaces=ns) or statement.xpath("ns:Bal/ns:Tp/ns:CdOrPrtry[ns:Cd='CLAV']/../../ns:Dt/ns:Dt/text()", namespaces=ns))[0]

            # Transaction Entries 0..n
            transactions = []
            sequence = 0

            # Currency 0..1
            currency = statement.xpath('ns:Acct/ns:Ccy/text() | ns:Bal/ns:Amt/@Ccy', namespaces=ns)[0]

            for entry in statement.findall('ns:Ntry', ns):
                # Date 0..1
                date = _get_transaction_date(entry, namespaces=ns) or statement_vals['date']

                transaction_details = entry.xpath('.//ns:TxDtls', namespaces=ns)
                for entry_details in transaction_details or [entry]:
                    sequence += 1
                    counter_party = _get_counter_party(entry_details, entry, namespaces=ns)
                    partner_name = _get_partner_name(entry_details, placeholder=counter_party, namespaces=ns)
                    entry_vals = {
                        'sequence': sequence,
                        'date': date,
                        'amount': _get_signed_amount(entry_details, entry, namespaces=ns),
                        'name': _get_transaction_name(entry_details, namespaces=ns),
                        'partner_name': partner_name,
                        'account_number': _get_account_number(entry_details, placeholder=counter_party, namespaces=ns),
                        'ref': _get_ref(entry_details, counter_party=counter_party, prefix='', namespaces=ns),
                    }

                    entry_vals['unique_import_id'] = _get_unique_import_id(
                        entry=entry_details,
                        sequence=sequence,
                        name=statement_vals['name'],
                        date=entry_vals['date'],
                        unique_import_set=unique_import_set,
                        namespaces=ns)

                    _set_amount_currency_and_currency_id(
                        node=entry_details,
                        path=transaction_details and 'ns:AmtDtls/ns:InstdAmt/ns:Amt' or 'ns:NtryDtls/ns:TxDtls/ns:AmtDtls/ns:InstdAmt/ns:Amt',
                        entry_vals=entry_vals,
                        currency=currency,
                        curr_cache=curr_cache,
                        has_multi_currency=has_multi_currency,
                        namespaces=ns)

                    BkTxCd = entry.xpath('ns:BkTxCd', namespaces=ns)[0]
                    entry_vals.update(_get_transaction_type(BkTxCd, namespaces=ns))
                    notes = [_get_additional_entry_info(entry, namespaces=ns) or ""]
                    partner_address = _get_partner_address(entry_details, ns, counter_party)
                    if partner_name:
                        notes.append(_('Counter Party: ') + partner_name)
                    if partner_address:
                        notes.append(_('Address:\n') + partner_address)
                    entry_vals['note'] = "\n".join(notes)

                    unique_import_set.add(entry_vals['unique_import_id'])
                    transactions.append(entry_vals)

            statement_vals['transactions'] = transactions

            # Start Balance
            # any (OPBD, PRCD, ITBD):
            #   OPBD : Opening Balance
            #   PRCD : Previous Closing Balance
            #   ITBD : Interim Balance (in the case of preceeding pagination)
            start_amount = float(statement.xpath("ns:Bal/ns:Tp/ns:CdOrPrtry[ns:Cd='OPBD' or ns:Cd='PRCD' or ns:Cd='ITBD' or ns:Cd='OPAV']/../../ns:Amt/text()",
                                                              namespaces=ns)[0])
            # Credit Or Debit Indicator 1..1
            sign = statement.xpath('ns:Bal/ns:CdtDbtInd/text()', namespaces=ns)[0]
            if sign == 'DBIT':
                start_amount *= -1
            statement_vals['balance_start'] = start_amount
            # Ending Balance
            # Statement Date
            # 'CLBD', otherwise 'CLAV'
            #   CLBD : Closing Balance
            #   CLAV : Closing Available
            end_amount = float((statement.xpath("ns:Bal/ns:Tp/ns:CdOrPrtry[ns:Cd='CLBD']/../../ns:Amt/text()", namespaces=ns) or statement.xpath("ns:Bal/ns:Tp/ns:CdOrPrtry[ns:Cd='CLAV']/../../ns:Amt/text()", namespaces=ns))[0])
            sign = (statement.xpath("ns:Bal/ns:Tp/ns:CdOrPrtry[ns:Cd='CLBD']/../../ns:CdtDbtInd/text()", namespaces=ns) or statement.xpath("ns:Bal/ns:Tp/ns:CdOrPrtry[ns:Cd='CLAV']/../../ns:CdtDbtInd/text()", namespaces=ns))[0]
            if sign == 'DBIT':
                end_amount *= -1
            statement_vals['balance_end_real'] = end_amount

            # Account Number    1..1
            # if not IBAN value then... <Othr><Id> would have.
            account_no = statement.xpath('ns:Acct/ns:Id/ns:IBAN/text() | ns:Acct/ns:Id/ns:Othr/ns:Id/text()', namespaces=ns)[0]

            # Save statements and currency
            statements_per_iban.setdefault(account_no, []).append(statement_vals)
            currency_per_iban[account_no] = currency

        # If statements target multiple journals, returns thoses targeting the current journal
        if len(statements_per_iban) > 1:
            account_no = self.env['account.journal'].browse(self.env.context.get('journal_id')).bank_acc_number
            _logger.warning("The following statements will not be imported because they are targeting another journal (current journal id: %s):\n- %s",
                            account_no, "\n- ".join("{}: {} statement(s)".format(iban, len(statements)) for iban, statements in statements_per_iban.items() if iban != account_no))
            if not account_no:
                raise UserError(_("Please set the IBAN account on your bank journal.\n\nThis CAMT file is targeting several IBAN accounts but none match the current journal."))

        # Otherwise, returns those from only account_no
        statement_list = statements_per_iban.get(account_no, [])
        currency = currency_per_iban.get(account_no)
        return currency, account_no, statement_list
