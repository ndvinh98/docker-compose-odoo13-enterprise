# -*- coding: utf-8 -*-

import base64
from datetime import datetime
from itertools import groupby
import logging
import requests

from lxml import etree
from lxml.objectify import fromstring
from zeep import Client
from zeep.transports import Transport
from odoo import _, api, fields, models
from odoo.tools import DEFAULT_SERVER_TIME_FORMAT, float_is_zero
from odoo.tools.float_utils import float_compare
from odoo.tools.misc import html_escape
from odoo.exceptions import UserError

from . import account_invoice

from odoo.addons.l10n_mx_edi.tools.run_after_commit import run_after_commit

_logger = logging.getLogger(__name__)

CFDI_TEMPLATE = 'l10n_mx_edi.payment10'
CFDI_XSLT_CADENA = 'l10n_mx_edi/data/3.3/cadenaoriginal.xslt'
CFDI_XSLT_CADENA_TFD = 'l10n_mx_edi/data/xslt/3.3/cadenaoriginal_TFD_1_1.xslt'
CFDI_SAT_QR_STATE = {
    'No Encontrado': 'not_found',
    'Cancelado': 'cancelled',
    'Vigente': 'valid',
}


class AccountPayment(models.Model):
    _name = 'account.payment'
    _inherit = ['account.payment', 'l10n_mx_edi.pac.sw.mixin']

    l10n_mx_edi_pac_status = fields.Selection(
        selection=[
            ('none', 'CFDI not necessary'),
            ('retry', 'Retry'),
            ('to_sign', 'To sign'),
            ('signed', 'Signed'),
            ('to_cancel', 'To cancel'),
            ('cancelled', 'Cancelled')
        ],
        string='PAC status', default='none',
        help='Refers to the status of the CFDI inside the PAC.',
        readonly=True, copy=False)
    l10n_mx_edi_sat_status = fields.Selection(
        selection=[
            ('none', 'State not defined'),
            ('undefined', 'Not Synced Yet'),
            ('not_found', 'Not Found'),
            ('cancelled', 'Cancelled'),
            ('valid', 'Valid'),
        ],
        string='SAT status',
        help='Refers to the status of the CFDI inside the SAT system.',
        readonly=True, copy=False, required=True,
        tracking=True, default='undefined')
    l10n_mx_edi_cfdi_name = fields.Char(string='CFDI name', copy=False, readonly=True,
        help='The attachment name of the CFDI.')
    l10n_mx_edi_payment_method_id = fields.Many2one(
        'l10n_mx_edi.payment.method',
        string='Payment Way',
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='Indicates the way the payment was/will be received, where the '
        'options could be: Cash, Nominal Check, Credit Card, etc.')
    l10n_mx_edi_cfdi = fields.Binary(
        string='Cfdi content', copy=False, readonly=True,
        help='The cfdi xml content encoded in base64.',
        compute='_compute_cfdi_values')
    l10n_mx_edi_cfdi_uuid = fields.Char(string='Fiscal Folio', copy=False, readonly=True,
        help='Folio in electronic invoice, is returned by SAT when send to stamp.',
        compute='_compute_cfdi_values')
    l10n_mx_edi_cfdi_supplier_rfc = fields.Char('Supplier RFC', copy=False, readonly=True,
        help='The supplier tax identification number.',
        compute='_compute_cfdi_values')
    l10n_mx_edi_cfdi_customer_rfc = fields.Char('Customer RFC', copy=False, readonly=True,
        help='The customer tax identification number.',
        compute='_compute_cfdi_values')
    l10n_mx_edi_origin = fields.Char(
        string='CFDI Origin', copy=False,
        help='In some cases the payment must be regenerated to fix data in it. '
        'In that cases is necessary this field filled, the format is: '
        '\n04|UUID1, UUID2, ...., UUIDn.\n'
        'Example:\n"04|89966ACC-0F5C-447D-AEF3-3EED22E711EE,89966ACC-0F5C-447D-AEF3-3EED22E711EE"')
    l10n_mx_edi_expedition_date = fields.Date(
        string='Expedition Date', copy=False,
        help='Save the expedition date of the CFDI that according to the SAT '
        'documentation must be the date when the CFDI is issued.')
    l10n_mx_edi_time_payment = fields.Char(
        string='Time payment', readonly=True, copy=False,
        states={'draft': [('readonly', False)]},
        help="Keep empty to use the current Mexico central time")
    l10n_mx_edi_partner_bank_id = fields.Many2one(
        'res.partner.bank', 'Partner Bank', help='If the payment was made '
        'with a financial institution define the bank account used in this '
        'payment.')

    def post(self):
        """Generate CFDI to payment after that invoice is paid"""
        res = super(AccountPayment, self.with_context(
            l10n_mx_edi_manual_reconciliation=False)).post()
        for record in self.filtered(lambda r: r.l10n_mx_edi_is_required()):
            partner = record.journal_id.l10n_mx_address_issued_id or record.company_id.partner_id.commercial_partner_id
            tz = self.env['account.move']._l10n_mx_edi_get_timezone(
                partner.state_id.code)
            date_mx = datetime.now(tz)
            record.write({
                'l10n_mx_edi_expedition_date': date_mx,
                'l10n_mx_edi_time_payment': date_mx.strftime(
                    DEFAULT_SERVER_TIME_FORMAT),
                'l10n_mx_edi_cfdi_name': ('%s-%s-MX-Payment-10.xml' % (
                    record.journal_id.code, record.name)),
            })
            record._l10n_mx_edi_retry()
        return res

    # -----------------------------------------------------------------------
    # Cancellation
    # -----------------------------------------------------------------------

    def cancel(self):
        result = super(AccountPayment, self).cancel()
        for record in self.filtered(lambda r: r.l10n_mx_edi_pac_status in [
                'to_sign', 'signed', 'to_cancel']):
            record._l10n_mx_edi_cancel()
        return result

    def _l10n_mx_edi_cancel(self):
        """Call the cancel service with records that can be cancelled."""
        records = self.search([
            ('l10n_mx_edi_pac_status', 'in', ['to_sign', 'signed', 'to_cancel', 'retry']),
            ('id', 'in', self.ids)])
        for record in records:
            if record.l10n_mx_edi_pac_status in ['to_sign', 'retry']:
                record.l10n_mx_edi_pac_status = False
                record.message_post(body=_('The cancel service has been called with success'))
            else:
                record.l10n_mx_edi_pac_status = 'to_cancel'
        records = self.search([
            ('l10n_mx_edi_pac_status', '=', 'to_cancel'),
            ('id', 'in', self.ids)])
        records._l10n_mx_edi_call_service('cancel')

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    @api.model
    def l10n_mx_edi_retrieve_attachments(self):
        """Retrieve all the cfdi attachments generated for this payment.

        :return: An ir.attachment recordset
        """
        self.ensure_one()
        if not self.l10n_mx_edi_cfdi_name:
            return []
        domain = [
            ('res_id', '=', self.id),
            ('res_model', '=', self._name),
            ('name', '=', self.l10n_mx_edi_cfdi_name)]
        return self.env['ir.attachment'].search(domain)

    @api.model
    def l10n_mx_edi_retrieve_last_attachment(self):
        attachment_ids = self.l10n_mx_edi_retrieve_attachments()
        return attachment_ids and attachment_ids[0] or None

    @api.model
    def l10n_mx_edi_get_xml_etree(self, cfdi=None):
        '''Get an objectified tree representing the cfdi.
        If the cfdi is not specified, retrieve it from the attachment.

        :param cfdi: The cfdi as string
        :return: An objectified tree
        '''
        #TODO helper which is not of too much help and should be removed
        self.ensure_one()
        if cfdi is None:
            cfdi = base64.decodestring(self.l10n_mx_edi_cfdi)
        return fromstring(cfdi)

    @api.model
    def l10n_mx_edi_get_tfd_etree(self, cfdi):
        '''Get the TimbreFiscalDigital node from the cfdi.

        :param cfdi: The cfdi as etree
        :return: the TimbreFiscalDigital node
        '''
        if not hasattr(cfdi, 'Complemento'):
            return None
        attribute = 'tfd:TimbreFiscalDigital[1]'
        namespace = {'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        return node[0] if node else None

    @api.model
    def l10n_mx_edi_get_payment_etree(self, cfdi):
        '''Get the Complement node from the cfdi.

        :param cfdi: The cfdi as etree
        :return: the Payment node
        '''
        if not hasattr(cfdi, 'Complemento'):
            return None
        attribute = '//pago10:DoctoRelacionado'
        namespace = {'pago10': 'http://www.sat.gob.mx/Pagos'}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        return node

    @api.model
    def _get_l10n_mx_edi_cadena(self):
        self.ensure_one()
        #get the xslt path
        xslt_path = CFDI_XSLT_CADENA_TFD
        #get the cfdi as eTree
        cfdi = base64.decodestring(self.l10n_mx_edi_cfdi)
        cfdi = self.l10n_mx_edi_get_xml_etree(cfdi)
        cfdi = self.l10n_mx_edi_get_tfd_etree(cfdi)
        #return the cadena
        return self.env['account.move'].l10n_mx_edi_generate_cadena(xslt_path, cfdi)

    def l10n_mx_edi_is_required(self):
        self.ensure_one()
        required = (
            self.payment_type == 'inbound' and
            self.company_id.country_id == self.env.ref('base.mx') and
            not self.invoice_ids.filtered(lambda i: i.type != 'out_invoice'))
        if not required:
            return required
        if self.l10n_mx_edi_pac_status != 'none':
            return True
        if self.invoice_ids and False in self.invoice_ids.mapped('l10n_mx_edi_cfdi_uuid'):
            raise UserError(_(
                'Some of the invoices that will be paid with this record '
                'are not signed, and the UUID is required to indicate '
                'the invoices that are paid with this CFDI'))
        messages = []
        if not self.invoice_ids:
            messages.append(_(
                '<b>This payment <b>has not</b> invoices related.'
                '</b><br/><br/>'
                'Which actions can you take?\n'
                '<ul>'
                '<ol>If this is an payment advance, you need to create a new '
                'invoice with a product that will represent the payment in '
                'advance and reconcile such invoice with this payment. For '
                'more information please read '
                '<a href="http://omawww.sat.gob.mx/informacion_fiscal/factura_electronica/Documents/Complementoscfdi/Caso_uso_Anticipo.pdf">'
                'this SAT reference.</a></ol>'
                '<ol>If you already have the invoices that are paid make the '
                'payment matching of them.</ol>'
                '</ul>'
                '<p>If you follow this steps once you finish them and the '
                'paid amount is bellow the sum of invoices the payment '
                'will be automatically signed'
                '</p>'))
        categ_force = self._l10n_mx_edi_get_force_rep_category()
        force = self._context.get('force_ref') or (
            categ_force and categ_force in self.partner_id.category_id)
        if self.invoice_ids and not self.invoice_ids.filtered(
                lambda i: i.l10n_mx_edi_get_payment_method_cfdi() == 'PPD') and not force:
            messages.append(_(
                '<b>The invoices related with this payment have the payment '
                'method as <b>PUE</b>.'
                '</b><br/><br/>'
                'When an invoice has the payment method <b>PUE</b> do not '
                'requires generate a payment complement. For more information '
                'please read '
                '<a href="http://omawww.sat.gob.mx/informacion_fiscal/factura_electronica/Documents/Complementoscfdi/Guia_comple_pagos.pdf">'
                'this SAT reference.</a>, Pag. 3. Or read the '
                '<a href="https://www.odoo.com/documentation/user/11.0/es/accounting/localizations/mexico.html#payments-just-available-for-cfdi-3-3">'
                'Odoo documentation</a> to know how to indicate the payment '
                'method in the invoice CFDI.'
                ))
        if messages:
            self.message_post(body=account_invoice.create_list_html(messages))
            return force or False
        return required

    @api.model
    def _l10n_mx_edi_get_force_rep_category(self):
        return self.env.ref(
            'l10n_mx_edi.res_partner_category_force_rep', False)

    def l10n_mx_edi_log_error(self, message):
        self.ensure_one()
        self.message_post(body=_('Error during the process: %s') % message)

    @api.depends('l10n_mx_edi_cfdi_name')
    def _compute_cfdi_values(self):
        """Fill the invoice fields from the cfdi values."""
        for rec in self:
            attachment_id = rec.l10n_mx_edi_retrieve_last_attachment()
            attachment_id = attachment_id[0] if attachment_id else None
            # At this moment, the attachment contains the file size in its 'datas' field because
            # to save some memory, the attachment will store its data on the physical disk.
            # To avoid this problem, we read the 'datas' directly on the disk.
            datas = attachment_id._file_read(attachment_id.store_fname) if attachment_id else None
            rec.l10n_mx_edi_cfdi_uuid = None
            if not datas:
                if attachment_id:
                    _logger.exception('The CFDI attachment cannot be found')
                rec.l10n_mx_edi_cfdi = None
                rec.l10n_mx_edi_cfdi_supplier_rfc = None
                rec.l10n_mx_edi_cfdi_customer_rfc = None
                continue
            rec.l10n_mx_edi_cfdi = datas
            tree = rec.l10n_mx_edi_get_xml_etree(base64.decodestring(datas))
            tfd_node = rec.l10n_mx_edi_get_tfd_etree(tree)
            if tfd_node is not None:
                rec.l10n_mx_edi_cfdi_uuid = tfd_node.get('UUID')
            rec.l10n_mx_edi_cfdi_supplier_rfc = tree.Emisor.get(
                'Rfc', tree.Emisor.get('rfc'))
            rec.l10n_mx_edi_cfdi_customer_rfc = tree.Receptor.get(
                'Rfc', tree.Receptor.get('rfc'))
            certificate = tree.get('noCertificado', tree.get('NoCertificado'))

    def _l10n_mx_edi_retry(self):
        rep_is_required = self.filtered(lambda r: r.l10n_mx_edi_is_required())
        for rec in rep_is_required:
            cfdi_values = rec._l10n_mx_edi_create_cfdi_payment()
            error = cfdi_values.pop('error', None)
            cfdi = cfdi_values.pop('cfdi', None)
            if error:
                # cfdi failed to be generated
                rec.l10n_mx_edi_pac_status = 'retry'
                rec.message_post(body=error)
                continue
            # cfdi has been successfully generated
            rec.l10n_mx_edi_pac_status = 'to_sign'
            filename = ('%s-%s-MX-Payment-10.xml' % (
                rec.journal_id.code, rec.name))
            ctx = self.env.context.copy()
            ctx.pop('default_type', False)
            rec.l10n_mx_edi_cfdi_name = filename
            attachment_id = self.env['ir.attachment'].with_context(ctx).create({
                'name': filename,
                'res_id': rec.id,
                'res_model': rec._name,
                'datas': base64.encodestring(cfdi),
                'description': _('Mexican CFDI to payment'),
                })
            rec.message_post(
                body=_('CFDI document generated (may be not signed)'),
                attachment_ids=[attachment_id.id])
            rec._l10n_mx_edi_sign()
        (self - rep_is_required).write({
            'l10n_mx_edi_pac_status': 'none',
        })

    def _l10n_mx_edi_create_cfdi_payment(self):
        self.ensure_one()
        qweb = self.env['ir.qweb']
        error_log = []
        company_id = self.company_id
        pac_name = company_id.l10n_mx_edi_pac
        values = self._l10n_mx_edi_create_cfdi_values()
        if 'error' in values:
            error_log.append(values.get('error'))

        # -----------------------
        # Check the configuration
        # -----------------------
        # -Check certificate
        certificate_ids = company_id.l10n_mx_edi_certificate_ids
        certificate_id = certificate_ids.sudo().get_valid_certificate()
        if not certificate_id:
            error_log.append(_('No valid certificate found'))

        # -Check PAC
        if pac_name:
            pac_test_env = company_id.l10n_mx_edi_pac_test_env
            pac_password = company_id.l10n_mx_edi_pac_password
            if not pac_test_env and not pac_password:
                error_log.append(_('No PAC credentials specified.'))
        else:
            error_log.append(_('No PAC specified.'))

        if error_log:
            return {'error': _('Please check your configuration: ') + account_invoice.create_list_html(error_log)}

        # -Compute date and time of the invoice
        partner = self.journal_id.l10n_mx_address_issued_id or self.company_id.partner_id.commercial_partner_id
        tz = self.env['account.move']._l10n_mx_edi_get_timezone(
            partner.state_id.code)
        date_mx = datetime.now(tz)
        if not self.l10n_mx_edi_expedition_date:
            self.l10n_mx_edi_expedition_date = date_mx.date()
        if not self.l10n_mx_edi_time_payment:
            self.l10n_mx_edi_time_payment = date_mx.strftime(
                DEFAULT_SERVER_TIME_FORMAT)

        time_invoice = datetime.strptime(self.l10n_mx_edi_time_payment,
                                         DEFAULT_SERVER_TIME_FORMAT).time()

        # -----------------------
        # Create the EDI document
        # -----------------------

        # -Compute certificate data
        values['date'] = datetime.combine(
            fields.Datetime.from_string(self.l10n_mx_edi_expedition_date),
            time_invoice).strftime('%Y-%m-%dT%H:%M:%S')
        values['certificate_number'] = certificate_id.serial_number
        values['certificate'] = certificate_id.sudo().get_data()[0]

        # -Compute cfdi
        cfdi = qweb.render(CFDI_TEMPLATE, values=values)

        # -Compute cadena
        tree = self.l10n_mx_edi_get_xml_etree(cfdi)
        cadena = self.env['account.move'].l10n_mx_edi_generate_cadena(
            CFDI_XSLT_CADENA, tree)

        # Post append cadena
        tree.attrib['Sello'] = certificate_id.sudo().get_encrypted_cadena(cadena)

        # TODO - Check with XSD
        return {'cfdi': etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8')}

    def _l10n_mx_edi_create_cfdi_values(self):
        """Create the values to fill the CFDI template with complement to
        payments."""
        self.ensure_one()
        invoice_obj = self.env['account.move']
        precision_digits = self.env['decimal.precision'].precision_get(
            self.currency_id.name)
        values = {
            'record': self,
            'supplier': self.company_id.partner_id.commercial_partner_id,
            'issued': self.journal_id.l10n_mx_address_issued_id,
            'customer': self.partner_id.commercial_partner_id,
            'fiscal_regime': self.company_id.l10n_mx_edi_fiscal_regime,
            'invoice': invoice_obj,
        }

        values.update(invoice_obj._l10n_mx_get_serie_and_folio(self.name))

        values['decimal_precision'] = precision_digits
        values.update(self.l10n_mx_edi_payment_data())
        return values

    def get_cfdi_related(self):
        """To node CfdiRelacionados get documents related with each invoice
        from l10n_mx_edi_origin, hope the next structure:
            relation type|UUIDs separated by ,"""
        self.ensure_one()
        if not self.l10n_mx_edi_origin:
            return {}
        origin = self.l10n_mx_edi_origin.split('|')
        uuids = origin[1].split(',') if len(origin) > 1 else []
        return {
            'type': origin[0],
            'related': [u.strip() for u in uuids],
            }

    def _l10n_mx_edi_invoice_payment_data(self):
        """Provide a single method to fetch the Totals paid in the Payment
        and makes the l10n_mx_edi_payment_data method more inheritable"""
        self.ensure_one()
        total_paid = total_curr = total_currency = 0
        for invoice in self.invoice_ids:
            amount = [p for p in invoice._get_reconciled_info_JSON_values() if (
                p.get('account_payment_id', False) == self.id or not p.get(
                    'account_payment_id') and (not p.get('move_id') or p.get(
                        'move_id') == invoice.id))]
            amount_payment = sum([data.get('amount', 0.0) for data in amount])
            amount_payment = amount_payment if sum([
                p.get('amount') for p in invoice._get_reconciled_info_JSON_values()]) <= invoice.amount_total else invoice.amount_total
            total_paid += amount_payment if invoice.currency_id != self.currency_id else 0
            total_currency += amount_payment if invoice.currency_id == self.currency_id else 0
            total_curr += invoice.currency_id.with_context(
                date=self.payment_date)._convert(
                    amount_payment, self.currency_id, self.company_id,
                    self.payment_date)
        return dict(
            total_paid=total_paid,
            total_curr=total_curr,
            total_currency=total_currency)

    def l10n_mx_edi_payment_data(self):
        self.ensure_one()
        # Based on "En caso de no contar con la hora se debe registrar 12:00:00"
        mxn = self.env.ref('base.MXN')
        date = datetime.combine(
            fields.Datetime.from_string(self.payment_date),
            datetime.strptime('12:00:00', '%H:%M:%S').time()).strftime('%Y-%m-%dT%H:%M:%S')
        res = self._l10n_mx_edi_invoice_payment_data()
        total_paid = res.get('total_paid', 0)
        total_curr = res.get('total_curr', 0)
        total_currency = res.get('total_currency', 0)
        precision = self.env['decimal.precision'].precision_get('Account')
        if not self.move_reconciled and float_compare(
                self.amount, total_curr, precision_digits=precision) > 0:
            return {'error': _(
                '<b>The amount paid is bigger than the sum of the invoices.'
                '</b><br/><br/>'
                'Which actions can you take?\n'
                '<ul>'
                '<ol>If the customer has more invoices, go to those invoices '
                'and reconcile them with this payment.</ol>'
                '<ol>If the customer <b>has not</b> more invoices to be paid '
                'You need to create a new invoice with a product that will '
                'represent the payment in advance and reconcile such invoice '
                'with this payment.</ol>'
                '</ul>'
                '<p>If you follow this steps once you finish them and the '
                'paid amount is bellow the sum of invoices the payment '
                'will be automatically signed'
                '</p><blockquote>For more information please read '
                '<a href="http://omawww.sat.gob.mx/informacion_fiscal/factura_electronica/Documents/Complementoscfdi/Guia_comple_pagos.pdf">'
                ' this SAT reference </a>, Pag. 22</blockquote>')
            }
        ctx = dict(company_id=self.company_id.id, date=self.payment_date)
        rate = ('%.6f' % (self.currency_id.with_context(**ctx)._convert(
            1, mxn, self.company_id, self.payment_date, round=False))) if self.currency_id.name != 'MXN' else False
        partner_bank = self.l10n_mx_edi_partner_bank_id.bank_id
        company_bank = self.journal_id.bank_account_id
        payment_code = self.l10n_mx_edi_payment_method_id.code
        acc_emitter_ok = payment_code in [
            '02', '03', '04', '05', '06', '28', '29', '99']
        acc_receiver_ok = payment_code in [
            '02', '03', '04', '05', '28', '29', '99']
        bank_name_ok = payment_code in ['02', '03', '04', '28', '29', '99']
        vat = 'XEXX010101000' if partner_bank.country and partner_bank.country != self.env.ref(
            'base.mx') else partner_bank.l10n_mx_edi_vat
        return {
            'mxn': mxn,
            'payment_date': date,
            'payment_rate': rate,
            'pay_vat_ord': False,
            'pay_account_ord': False,
            'pay_vat_receiver': False,
            'pay_account_receiver': False,
            'pay_ent_type': False,
            'pay_certificate': False,
            'pay_string': False,
            'pay_stamp': False,
            'total_paid': total_paid,
            'total_currency': total_currency,
            'pay_vat_ord': vat if acc_emitter_ok else None,
            'pay_name_ord': partner_bank.name if bank_name_ok else None,
            'pay_account_ord': (self.l10n_mx_edi_partner_bank_id.acc_number or '').replace(
                ' ', '') if acc_emitter_ok else None,
            'pay_vat_receiver': company_bank.bank_id.l10n_mx_edi_vat if acc_receiver_ok else None,
            'pay_account_receiver': (company_bank.acc_number or '').replace(
                ' ', '') if acc_receiver_ok else None,
        }

    def _l10n_mx_edi_sign(self):
        """Call the sign service with records that can be signed."""
        records = self.search([
            ('l10n_mx_edi_pac_status', 'not in', ['signed', 'to_cancel', 'cancelled', 'retry']),
            ('id', 'in', self.ids)])
        records._l10n_mx_edi_call_service('sign')

    def _l10n_mx_edi_post_cancel_process(self, cancelled, code=None, msg=None):
        '''Post process the results of the cancel service.

        :param cancelled: is the cancel has been done with success
        :param code: an eventual error code
        :param msg: an eventual error msg
        '''

        self.ensure_one()
        if cancelled:
            body_msg = _('The cancel service has been called with success')
            self.l10n_mx_edi_pac_status = 'cancelled'
            legal = _(
                '''<h3 style="color:red">Legal warning</h3>
                <p> Regarding the issue of the CFDI with' Complement for
                receipt of payments', where there are errors in the receipt, this
                may be canceled provided it is replaced by another with the correct data.
                If the error consists in which the payment receipt
                complement should not have been issued because the consideration
                had already been paid in full; replaced by another with an
                amount of one peso.</p>
                <p><a href="http://www.sat.gob.mx/informacion_fiscal/factura_electronica/Documents/Complementoscfdi/Guia_comple_pagos.pdf">
                For more information here (Pag. 5)</a></p>''')
            self.message_post(body=legal)
        else:
            body_msg = _('The cancel service requested failed')
        post_msg = []
        if code:
            post_msg.extend([_('Code: %s') % code])
        if msg:
            post_msg.extend([_('Message: %s') % msg])
        self.message_post(
            body=body_msg + account_invoice.create_list_html(post_msg))

    @run_after_commit
    def _l10n_mx_edi_call_service(self, service_type):
        """Call the right method according to the pac_name, it's info returned
        by the '_l10n_mx_edi_%s_info' % pac_name'
        method and the service_type passed as parameter.
        :param service_type: sign or cancel"""
        invoice_obj = self.env['account.move']
        # Regroup the invoices by company (= by pac)
        comp_x_records = groupby(self, lambda r: r.company_id)
        for company_id, records in comp_x_records:
            pac_name = company_id.l10n_mx_edi_pac
            if not pac_name:
                continue
            # Get the informations about the pac
            pac_info_func = '_l10n_mx_edi_%s_info' % pac_name
            service_func = '_l10n_mx_edi_%s_%s' % (pac_name, service_type)
            pac_info = getattr(invoice_obj, pac_info_func)(company_id, service_type)
            # Call the service with invoices one by one or all together according to the 'multi' value.
            # TODO - Check multi
            for record in records:
                getattr(record, service_func)(pac_info)

    # -------------------------------------------------------------------------
    # SAT/PAC service methods
    # -------------------------------------------------------------------------

    def _l10n_mx_edi_get_payment_write_off(self):
        self.ensure_one()
        res = {}
        for invoice in self.invoice_ids:
            foreign_currency = invoice.currency_id if invoice.currency_id != invoice.company_id.currency_id else False

            pay_term_line_ids = invoice.line_ids.filtered(lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
            partials = pay_term_line_ids.mapped('matched_debit_ids') + pay_term_line_ids.mapped('matched_credit_ids')
            for partial in partials:
                counterpart_lines = partial.debit_move_id + partial.credit_move_id
                counterpart_line = counterpart_lines.filtered(lambda line: line not in invoice.line_ids)
                if counterpart_line.journal_id != invoice.company_id.currency_exchange_journal_id:
                    continue

                if foreign_currency and partial.currency_id == foreign_currency:
                    amount = partial.amount_currency
                else:
                    amount = partial.company_currency_id._convert(partial.amount, invoice.currency_id, invoice.company_id, invoice.date)

                if float_is_zero(amount, precision_rounding=invoice.currency_id.rounding):
                    continue
                res[invoice.id] = amount
        return res

    @api.model
    def _l10n_mx_edi_solfact_info(self, company_id, service_type):
        test = company_id.l10n_mx_edi_pac_test_env
        username = company_id.l10n_mx_edi_pac_username
        password = company_id.l10n_mx_edi_pac_password
        url = 'https://testing.solucionfactible.com/ws/services/Timbrado?wsdl'\
            if test else 'https://solucionfactible.com/ws/services/Timbrado?wsdl'
        return {
            'url': url,
            'multi': False,  # TODO: implement multi
            'username': 'testing@solucionfactible.com' if test else username,
            'password': 'timbrado.SF.16672' if test else password,
        }

    def _l10n_mx_edi_solfact_sign(self, pac_info):
        '''SIGN for Solucion Factible.
        '''
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        for rec in self:
            cfdi = base64.decodestring(rec.l10n_mx_edi_cfdi)
            try:
                transport = Transport(timeout=20)
                client = Client(url, transport=transport)
                response = client.service.timbrar(username, password, cfdi, False)
            except Exception as e:
                rec.l10n_mx_edi_log_error(str(e))
                continue
            msg = getattr(response.resultados[0], 'mensaje', None)
            code = getattr(response.resultados[0], 'status', None)
            xml_signed = getattr(response.resultados[0], 'cfdiTimbrado', None)
            if xml_signed:
                xml_signed = base64.b64encode(xml_signed)
            rec._l10n_mx_edi_post_sign_process(
                xml_signed if xml_signed else None, code, msg)

    def _l10n_mx_edi_solfact_cancel(self, pac_info):
        '''CANCEL for Solucion Factible.
        '''
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        for rec in self:
            uuids = [rec.l10n_mx_edi_cfdi_uuid]
            certificate_ids = rec.company_id.l10n_mx_edi_certificate_ids
            certificate_id = certificate_ids.sudo().get_valid_certificate()
            cer_pem = certificate_id.get_pem_cer(certificate_id.content)
            key_pem = certificate_id.get_pem_key(
                certificate_id.key, certificate_id.password)
            key_password = certificate_id.password
            try:
                transport = Transport(timeout=20)
                client = Client(url, transport=transport)
                response = client.service.cancelar(username, password, uuids, cer_pem, key_pem, key_password)
            except Exception as e:
                rec.l10n_mx_edi_log_error(str(e))
                continue
            code = getattr(response.resultados[0], 'statusUUID', None)
            cancelled = code in ('201', '202')  # cancelled or previously cancelled
            # no show code and response message if cancel was success
            msg = '' if cancelled else getattr(response.resultados[0], 'mensaje', None)
            code = '' if cancelled else code
            rec._l10n_mx_edi_post_cancel_process(cancelled, code, msg)

    def _l10n_mx_edi_finkok_sign(self, pac_info):
        """SIGN for Finkok."""
        # TODO - Duplicated with the invoice one
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        for rec in self:
            cfdi = base64.decodestring(rec.l10n_mx_edi_cfdi)
            try:
                transport = Transport(timeout=20)
                client = Client(url, transport=transport)
                response = client.service.stamp(cfdi, username, password)
            except Exception as e:
                rec.l10n_mx_edi_log_error(str(e))
                continue
            code = 0
            msg = None
            if response.Incidencias:
                code = getattr(response.Incidencias.Incidencia[0], 'CodigoError', None)
                msg = getattr(response.Incidencias.Incidencia[0], 'MensajeIncidencia', None)
            xml_signed = getattr(response, 'xml', None)
            if xml_signed:
                xml_signed = base64.b64encode(xml_signed.encode('utf-8'))
            rec._l10n_mx_edi_post_sign_process(xml_signed, code, msg)

    def _l10n_mx_edi_finkok_cancel(self, pac_info):
        '''CANCEL for Finkok.
        '''
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        for inv in self:
            uuid = inv.l10n_mx_edi_cfdi_uuid
            certificate_ids = inv.company_id.l10n_mx_edi_certificate_ids
            certificate_id = certificate_ids.sudo().get_valid_certificate()
            company_id = self.company_id
            cer_pem = certificate_id.get_pem_cer(certificate_id.content)
            key_pem = certificate_id.get_pem_key(
                certificate_id.key, certificate_id.password)
            cancelled = False
            code = False
            try:
                transport = Transport(timeout=20)
                client = Client(url, transport=transport)
                uuid_type = client.get_type('ns0:stringArray')()
                uuid_type.string = [uuid]
                invoices_list = client.get_type('ns1:UUIDS')(uuid_type)
                response = client.service.cancel(invoices_list, username, password, company_id.vat, cer_pem, key_pem)
            except Exception as e:
                inv.l10n_mx_edi_log_error(str(e))
                continue
            if not (hasattr(response, 'Folios') and response.Folios):
                msg = _('A delay of 2 hours has to be respected before to cancel')
            else:
                code = getattr(response.Folios.Folio[0], 'EstatusUUID', None)
                cancelled = code in ('201', '202')  # cancelled or previously cancelled
                # no show code and response message if cancel was success
                code = '' if cancelled else code
                msg = '' if cancelled else _("Cancelling got an error")
            inv._l10n_mx_edi_post_cancel_process(cancelled, code, msg)

    def _l10n_mx_edi_post_sign_process(self, xml_signed, code=None, msg=None):
        """Post process the results of the sign service.

        :param xml_signed: the xml signed datas codified in base64
        :param code: an eventual error code
        :param msg: an eventual error msg
        """
        # TODO - Duplicated
        self.ensure_one()
        if xml_signed:
            body_msg = _('The sign service has been called with success')
            # Update the pac status
            self.l10n_mx_edi_pac_status = 'signed'
            self.l10n_mx_edi_cfdi = xml_signed
            # Update the content of the attachment
            attachment_id = self.l10n_mx_edi_retrieve_last_attachment()
            attachment_id.write({
                'datas': xml_signed,
                'mimetype': 'application/xml'
            })
            post_msg = [_('The content of the attachment has been updated')]
        else:
            body_msg = _('The sign service requested failed')
            post_msg = []
        if code:
            post_msg.extend([_('Code: %s') % code])
        if msg:
            post_msg.extend([_('Message: %s') % msg])
        self.message_post(
            body=body_msg + account_invoice.create_list_html(post_msg))

    def l10n_mx_edi_update_pac_status(self):
        """Synchronize both systems: Odoo & PAC if the invoices need to be
        signed or cancelled."""
        # TODO - Duplicated
        for record in self:
            if record.l10n_mx_edi_pac_status == 'to_sign':
                record._l10n_mx_edi_sign()
            elif record.l10n_mx_edi_pac_status == 'to_cancel':
                record._l10n_mx_edi_cancel()
            elif record.l10n_mx_edi_pac_status == 'retry':
                record._l10n_mx_edi_retry()

    def l10n_mx_edi_update_sat_status(self):
        """Synchronize both systems: Odoo & SAT to make sure the invoice is valid.
        """
        url = 'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc?wsdl'
        headers = {'SOAPAction': 'http://tempuri.org/IConsultaCFDIService/Consulta', 'Content-Type': 'text/xml; charset=utf-8'}
        template = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:ns0="http://tempuri.org/" xmlns:ns1="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
   <SOAP-ENV:Header/>
   <ns1:Body>
      <ns0:Consulta>
         <ns0:expresionImpresa>${data}</ns0:expresionImpresa>
      </ns0:Consulta>
   </ns1:Body>
</SOAP-ENV:Envelope>"""
        namespace = {'a': 'http://schemas.datacontract.org/2004/07/Sat.Cfdi.Negocio.ConsultaCfdi.Servicio'}
        for rec in self.filtered('l10n_mx_edi_cfdi'):
            supplier_rfc = rec.l10n_mx_edi_cfdi_supplier_rfc
            customer_rfc = rec.l10n_mx_edi_cfdi_customer_rfc
            total = 0
            uuid = rec.l10n_mx_edi_cfdi_uuid
            params = '?re=%s&amp;rr=%s&amp;tt=%s&amp;id=%s' % (
                html_escape(html_escape(supplier_rfc or '')),
                html_escape(html_escape(customer_rfc or '')),
                total or 0.0, uuid or '')
            soap_env = template.format(data=params)
            try:
                soap_xml = requests.post(url, data=soap_env,
                                         headers=headers, timeout=20)
                response = fromstring(soap_xml.text)
                status = response.xpath(
                    '//a:Estado', namespaces=namespace)
            except Exception as e:
                rec.l10n_mx_edi_log_error(str(e))
                continue
            rec.l10n_mx_edi_sat_status = CFDI_SAT_QR_STATE.get(
                status[0] if status else '', 'none')

    def l10n_mx_edi_force_payment_complement(self):
        '''Allow force the CFDI generation when the complement is not required
        '''
        self.with_context(force_ref=True)._l10n_mx_edi_retry()

    def _l10n_mx_edi_sat_synchronously(self, batch_size=10):
        """Update the SAT status synchronously

        This method Calls :meth:`~.l10n_mx_edi_update_sat_status` by batches,
        ensuring changes are committed after processing each batch. This is
        intended to be able to process a lot of records on a safely manner,
        avoiding a possible sistematic failure withoud any payment updated.

        This is especially useful when running crons.

        :param batch_size: the number of payments to process by batch
        :type batch_size: int
        """
        for idx in range(0, len(self), batch_size):
            with self.env.cr.savepoint():
                self[idx:idx+batch_size].l10n_mx_edi_update_sat_status()

    def _set_cfdi_origin(self, uuid):
        """Try to write the origin in of the CFDI, it is important in order
        to have a centralized way to manage this elements due to the fact
        that this logic can be used in several places functionally speaking
        all around Odoo.
        :param uuid:
        :return:
        """
        self.ensure_one()
        origin = '04|%s' % uuid
        self.update({'l10n_mx_edi_origin': origin})
        return origin

    def action_draft(self):
        for record in self.filtered(lambda payment: payment.l10n_mx_edi_cfdi_uuid and payment.state == 'cancelled'):
            record.write({
                'l10n_mx_edi_expedition_date': False,
                'l10n_mx_edi_pac_status': 'none',
                'l10n_mx_edi_time_payment': False,
                'l10n_mx_edi_origin': record._set_cfdi_origin(
                    record.l10n_mx_edi_cfdi_uuid),
            })
        return super(AccountPayment, self).action_draft()

    def unlink(self):
        mx_payment = self.filtered(lambda r: r.l10n_mx_edi_is_required() and r.l10n_mx_edi_cfdi)
        mx_payment.with_context(disable_after_commit=True)._l10n_mx_edi_cancel()
        mx_payment.l10n_mx_edi_update_sat_status()
        env_demo = mx_payment.mapped('company_id').filtered(
            'l10n_mx_edi_pac_test_env')
        if mx_payment.filtered(
                lambda p: p.company_id not in env_demo and p.l10n_mx_edi_pac_status in [
                    'to_cancel', 'cancelled'] and p.l10n_mx_edi_sat_status != 'cancelled'):
            raise UserError(_('In order to delete a payment, you must first '
                              'cancel it in the SAT system.'))
        return super(AccountPayment, self).unlink()

    @api.onchange('partner_id')
    def _l10n_mx_onchange_partner_bank_id(self):
        self.l10n_mx_edi_partner_bank_id = False
        if len(self.partner_id.commercial_partner_id.bank_ids) == 1:
            self.l10n_mx_edi_partner_bank_id = self.partner_id.commercial_partner_id.bank_ids  # noqa


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    l10n_mx_edi_payment_method_id = fields.Many2one(
        'l10n_mx_edi.payment.method',
        string='Payment Way',
        help='Indicates the way the payment was/will be received, where the '
        'options could be: Cash, Nominal Check, Credit Card, etc.')
    l10n_mx_edi_partner_bank_id = fields.Many2one(
        'res.partner.bank', 'Partner Bank', help='If the payment was made '
        'with a financial institution define the bank account used in this '
        'payment.')

    def _prepare_payment_vals(self, invoice):
        res = super(AccountPaymentRegister, self)._prepare_payment_vals(invoice)
        res.update({
            'l10n_mx_edi_payment_method_id': self.l10n_mx_edi_payment_method_id.id,
            'l10n_mx_edi_partner_bank_id': self.l10n_mx_edi_partner_bank_id.id,
        })
        return res
