# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time

from datetime import datetime

from odoo import models, fields, api, _

from odoo.exceptions import UserError

from odoo.tools.float_utils import float_repr
from odoo.tools.xml_utils import create_xml_node, create_xml_node_chain
from odoo.tools.misc import remove_accents

from lxml import etree

import re


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    sdd_mandate_id = fields.Many2one(string='Originating SEPA mandate',
                                     comodel_name='sdd.mandate',
                                     readonly=True,
                                     help="The mandate used to generate this payment, if any.")
    sdd_mandate_usable = fields.Boolean(string="Could a SDD mandate be used?",
        help="Technical field used to inform the end user there is a SDD mandate that could be used to register that payment",
        compute='_compute_usable_mandate',)

    @api.model
    def split_node(self, string_node, max_size):
        # Split a string node according to its max_size in byte
        byte_node = string_node.encode()
        if len(byte_node) <= max_size:
            return string_node, ''
        while byte_node[max_size] >= 0x80 and byte_node[max_size] < 0xc0:
            max_size -= 1
        return byte_node[0:max_size].decode(), byte_node[max_size:].decode()

    @api.depends('payment_date', 'partner_id', 'company_id')
    def _compute_usable_mandate(self):
        """ returns the first mandate found that can be used for this payment,
        or none if there is no such mandate.
        """
        for payment in self:
            payment.sdd_mandate_usable = bool(payment.get_usable_mandate())

    @api.model
    def _sanitize_communication(self, communication):
        """ Returns a sanitized version of the communication given in parameter,
            so that:
                - it contains only latin characters
                - it does not contain any //
                - it does not start or end with /
                - it is maximum 140 characters long
            (these are the SEPA compliance criteria)
        """
        communication = self.split_node(communication, 140)[0]
        while '//' in communication:
            communication = communication.replace('//', '/')
        if communication.startswith('/'):
            communication = communication[1:]
        if communication.endswith('/'):
            communication = communication[:-1]
        communication = re.sub('[^-A-Za-z0-9/?:().,\'+ ]', '', remove_accents(communication))
        return communication

    def post(self):
        """ Overridden to register SDD payments on mandates.
        """
        for record in self:
            if record.payment_method_code == 'sdd':
                usable_mandate = record.get_usable_mandate()
                if not usable_mandate:
                    raise UserError(_("Unable to post payment due to no usable mandate being available at date %s for partner '%s'. Please create one before encoding a SEPA Direct Debit payment." % (str(record.payment_date), record.partner_id.name)))
                record._register_on_mandate(usable_mandate)

        super(AccountPayment, self).post()

    def generate_xml(self, company_id, required_collection_date, askBatchBooking):
        """ Generates a SDD XML file containing the payments corresponding to this recordset,
        associating them to the given company, with the specified
        collection date.
        """
        document = etree.Element("Document",nsmap={None:'urn:iso:std:iso:20022:tech:xsd:pain.008.001.02', 'xsi': "http://www.w3.org/2001/XMLSchema-instance"})
        CstmrDrctDbtInitn = etree.SubElement(document, 'CstmrDrctDbtInitn')

        self._sdd_xml_gen_header(company_id, CstmrDrctDbtInitn)

        payments_per_journal = self._group_payments_per_bank_journal()
        payment_info_counter = 0
        for (journal, journal_payments) in payments_per_journal.items():
            journal_payments._sdd_xml_gen_payment_group(company_id, required_collection_date, askBatchBooking,payment_info_counter, journal, CstmrDrctDbtInitn)
            payment_info_counter += 1


        return etree.tostring(document, pretty_print=True, xml_declaration=True, encoding='utf-8')

    def get_usable_mandate(self):
        """ Returns the sdd mandate that can be used to generate this payment, or
        None if there is none.
        """
        return self.env['sdd.mandate']._sdd_get_usable_mandate(
            self.company_id.id or self.env.company.id,
            self.partner_id.commercial_partner_id.id,
            self.payment_date)

    def _sdd_xml_gen_header(self, company_id, CstmrDrctDbtInitn):
        """ Generates the header of the SDD XML file.
        """
        GrpHdr = create_xml_node(CstmrDrctDbtInitn, 'GrpHdr')
        create_xml_node(GrpHdr, 'MsgId', str(time.time()))  # Using time makes sure the identifier is unique in an easy way
        create_xml_node(GrpHdr, 'CreDtTm', datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
        create_xml_node(GrpHdr, 'NbOfTxs', str(len(self)))
        create_xml_node(GrpHdr, 'CtrlSum', float_repr(sum(x.amount for x in self), precision_digits=2))  # This sum ignores the currency, it is used as a checksum (see SEPA rulebook)
        InitgPty = create_xml_node(GrpHdr, 'InitgPty')
        create_xml_node(InitgPty, 'Nm', self.split_node(company_id.name, 70)[0])
        create_xml_node_chain(InitgPty, ['Id','OrgId','Othr','Id'], company_id.sdd_creditor_identifier)

    def _sdd_xml_gen_payment_group(self, company_id, required_collection_date, askBatchBooking, payment_info_counter, journal, CstmrDrctDbtInitn):
        """ Generates a group of payments in the same PmtInfo node, provided
        that they share the same journal."""
        PmtInf = create_xml_node(CstmrDrctDbtInitn, 'PmtInf')
        create_xml_node(PmtInf, 'PmtInfId', str(payment_info_counter))
        create_xml_node(PmtInf, 'PmtMtd', 'DD')
        create_xml_node(PmtInf, 'BtchBookg',askBatchBooking and 'true' or 'false')
        create_xml_node(PmtInf, 'NbOfTxs', str(len(self)))
        create_xml_node(PmtInf, 'CtrlSum', float_repr(sum(x.amount for x in self), precision_digits=2))  # This sum ignores the currency, it is used as a checksum (see SEPA rulebook)

        PmtTpInf = create_xml_node_chain(PmtInf, ['PmtTpInf','SvcLvl','Cd'], 'SEPA')[0]
        create_xml_node_chain(PmtTpInf, ['LclInstrm','Cd'], 'CORE')
        create_xml_node(PmtTpInf, 'SeqTp', 'FRST')
        #Note: FRST refers to the COLLECTION of payments, not the type of mandate used
        #This value is only used for informatory purpose.

        create_xml_node(PmtInf, 'ReqdColltnDt', fields.Date.from_string(required_collection_date).strftime("%Y-%m-%d"))
        create_xml_node_chain(PmtInf, ['Cdtr','Nm'], self.split_node(company_id.name, 70)[0])  # SEPA regulation gives a maximum size of 70 characters for this field
        create_xml_node_chain(PmtInf, ['CdtrAcct','Id','IBAN'], journal.bank_account_id.sanitized_acc_number)
        create_xml_node_chain(PmtInf, ['CdtrAgt', 'FinInstnId', 'BIC'], (journal.bank_id.bic or '').replace(' ', '').upper())

        CdtrSchmeId_Othr = create_xml_node_chain(PmtInf, ['CdtrSchmeId','Id','PrvtId','Othr','Id'], company_id.sdd_creditor_identifier)[-2]
        create_xml_node_chain(CdtrSchmeId_Othr, ['SchmeNm','Prtry'], 'SEPA')

        for payment in self:
            payment.sdd_xml_gen_payment(company_id, payment.partner_id, self.split_node(payment.name, 35)[0], PmtInf)

    def sdd_xml_gen_payment(self,company_id, partner, end2end_name, PmtInf):
        """ Appends to a SDD XML file being generated all the data related to the
        payments of a given partner.
        """
        #The two following conditions should never execute.
        #They are here to be sure future modifications won't ever break everything.
        if self.company_id != company_id:
            raise UserError(_("Trying to generate a Direct Debit XML file containing payments from another company than that file's creditor."))

        if self.payment_method_id.code != 'sdd':
            raise UserError(_("Trying to generate a Direct Debit XML for payments coming from another payment method than SEPA Direct Debit."))

        if not self.sdd_mandate_id:
            raise UserError(_("The payment must be linked to a SEPA Direct Debit mandate in order to generate a Direct Debit XML."))

        if self.sdd_mandate_id.state == 'revoked':
            raise UserError(_("The SEPA Direct Debit mandate associated to the payment has been revoked and cannot be used anymore."))

        DrctDbtTxInf = create_xml_node_chain(PmtInf, ['DrctDbtTxInf','PmtId','EndToEndId'], end2end_name)[0]

        InstdAmt = create_xml_node(DrctDbtTxInf, 'InstdAmt', float_repr(self.amount, precision_digits=2))
        InstdAmt.attrib['Ccy'] = self.currency_id.name

        MndtRltdInf = create_xml_node_chain(DrctDbtTxInf, ['DrctDbtTx','MndtRltdInf','MndtId'], self.sdd_mandate_id.name)[-2]
        create_xml_node(MndtRltdInf, 'DtOfSgntr', fields.Date.to_string(self.sdd_mandate_id.start_date))
        create_xml_node_chain(DrctDbtTxInf, ['DbtrAgt', 'FinInstnId', 'BIC'], (self.sdd_mandate_id.partner_bank_id.bank_id.bic or '').replace(' ', '').upper())
        Dbtr = create_xml_node_chain(DrctDbtTxInf, ['Dbtr','Nm'], self.sdd_mandate_id.partner_bank_id.acc_holder_name or partner.name)[0]

        if partner.contact_address:
            PstlAdr = create_xml_node(Dbtr, 'PstlAdr')
            if partner.country_id and partner.country_id.code:
                create_xml_node(PstlAdr, 'Ctry', partner.country_id.code)
            n_line = 0
            contact_address = partner.contact_address.replace('\n', ' ').strip()
            while contact_address and n_line < 2:
                create_xml_node(PstlAdr, 'AdrLine', self.split_node(contact_address, 70)[0])
                contact_address = self.split_node(contact_address, 70)[1]
                n_line = n_line + 1

        if self.sdd_mandate_id.debtor_id_code:
            chain_keys = ['Id', 'PrvtId', 'Othr', 'Id']
            if partner.commercial_partner_id.is_company:
                chain_keys = ['Id', 'OrgId', 'Othr', 'Id']
            create_xml_node_chain(Dbtr, chain_keys, self.sdd_mandate_id.debtor_id_code)

        create_xml_node_chain(DrctDbtTxInf, ['DbtrAcct','Id','IBAN'], self.sdd_mandate_id.partner_bank_id.sanitized_acc_number)

        if self.communication:
            create_xml_node_chain(DrctDbtTxInf, ['RmtInf', 'Ustrd'], self._sanitize_communication(self.communication))

    def _group_payments_per_bank_journal(self):
        """ Groups the payments of this recordset per associated journal, in a dictionnary of recordsets.
        """
        rslt = {}
        for payment in self:
            if rslt.get(payment.journal_id, False):
                rslt[payment.journal_id] += payment
            else:
                rslt[payment.journal_id] = payment
        return rslt

    def _register_on_mandate(self, mandate):
        for record in self:
            if mandate.partner_id != record.partner_id.commercial_partner_id:
                raise UserError(_("Trying to register a payment on a mandate belonging to a different partner."))

            record.sdd_mandate_id = mandate
            mandate.write({'paid_invoice_ids': [(4, invoice.id, None) for invoice in record.invoice_ids]})

            if mandate.one_off:
                mandate.action_close_mandate()

    def create_payments(self):
        if self.payment_method_code == 'sdd':
            rslt = self.env['account.payment']
            for invoice in self.invoice_ids:
                mandate = invoice._sdd_get_usable_mandate()
                if not mandate:
                    raise UserError(_("This invoice cannot be paid via SEPA Direct Debit, as there is no valid mandate available for its customer at its creation date."))
                rslt += invoice._sdd_pay_with_mandate(mandate)
            return rslt

        return super(AccountPayment, self).create_payments()
