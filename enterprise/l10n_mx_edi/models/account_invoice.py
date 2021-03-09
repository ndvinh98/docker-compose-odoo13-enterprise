# -*- coding: utf-8 -*-

import base64
from itertools import groupby
import re
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from io import BytesIO
import requests
from pytz import timezone

from lxml import etree
from lxml.objectify import fromstring
from zeep import Client
from zeep.transports import Transport

from odoo import _, api, fields, models, tools
from odoo.tools.xml_utils import _check_with_xsd
from odoo.tools import DEFAULT_SERVER_TIME_FORMAT
from odoo.tools import float_round
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_repr

from odoo.addons.l10n_mx_edi.tools.run_after_commit import run_after_commit

CFDI_TEMPLATE_33 = 'l10n_mx_edi.cfdiv33'
CFDI_XSLT_CADENA = 'l10n_mx_edi/data/%s/cadenaoriginal.xslt'
CFDI_XSLT_CADENA_TFD = 'l10n_mx_edi/data/xslt/3.3/cadenaoriginal_TFD_1_1.xslt'
# Mapped from original SAT state to l10n_mx_edi_sat_status selection value
# https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc?wsdl
CFDI_SAT_QR_STATE = {
    'No Encontrado': 'not_found',
    'Cancelado': 'cancelled',
    'Vigente': 'valid',
}

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def create_list_html(array):
    '''Convert an array of string to a html list.
    :param array: A list of strings
    :return: an empty string if not array, an html list otherwise.
    '''
    if not array:
        return ''
    msg = ''
    for item in array:
        msg += '<li>' + item + '</li>'
    return '<ul>' + msg + '</ul>'


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'l10n_mx_edi.pac.sw.mixin']

    l10n_mx_edi_pac_status = fields.Selection(
        selection=[
            ('retry', 'Retry'),
            ('to_sign', 'To sign'),
            ('signed', 'Signed'),
            ('to_cancel', 'To cancel'),
            ('cancelled', 'Cancelled')
        ],
        string='PAC status',
        help='Refers to the status of the invoice inside the PAC.',
        readonly=True,
        copy=False)
    l10n_mx_edi_sat_status = fields.Selection(
        selection=[
            ('none', 'State not defined'),
            ('undefined', 'Not Synced Yet'),
            ('not_found', 'Not Found'),
            ('cancelled', 'Cancelled'),
            ('valid', 'Valid'),
        ],
        string='SAT status',
        help='Refers to the status of the invoice inside the SAT system.',
        readonly=True,
        copy=False,
        required=True,
        tracking=True,
        default='undefined')
    l10n_mx_edi_cfdi_name = fields.Char(string='CFDI name', copy=False, readonly=True,
        help='The attachment name of the CFDI.')
    l10n_mx_edi_partner_bank_id = fields.Many2one('res.partner.bank',
        string='Partner bank',
        readonly=True,
        states={'draft': [('readonly', False)]},
        domain="[('partner_id', '=', partner_id)]",
        help='The bank account the client will pay from. Leave empty if '
        'unkown and the XML will show "Unidentified".')
    l10n_mx_edi_payment_method_id = fields.Many2one('l10n_mx_edi.payment.method',
        string='Payment Way',
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='Indicates the way the invoice was/will be paid, where the '
        'options could be: Cash, Nominal Check, Credit Card, etc. Leave empty '
        'if unkown and the XML will show "Unidentified".',
        default=lambda self: self.env.ref('l10n_mx_edi.payment_method_otros',
                                          raise_if_not_found=False))
    l10n_mx_edi_cfdi_uuid = fields.Char(string='Fiscal Folio', copy=False, readonly=True,
        help='Folio in electronic invoice, is returned by SAT when send to stamp.',
        compute='_compute_cfdi_values')
    l10n_mx_edi_cfdi = fields.Binary(string='Cfdi content', copy=False, readonly=True,
        help='The cfdi xml content encoded in base64.',
        compute='_compute_cfdi_values')
    l10n_mx_edi_cfdi_supplier_rfc = fields.Char(string='Supplier RFC', copy=False, readonly=True,
        help='The supplier tax identification number.',
        compute='_compute_cfdi_values')
    l10n_mx_edi_cfdi_customer_rfc = fields.Char(string='Customer RFC', copy=False, readonly=True,
        help='The customer tax identification number.',
        compute='_compute_cfdi_values')
    l10n_mx_edi_cfdi_amount = fields.Monetary(string='Total Amount', copy=False, readonly=True,
        help='The total amount reported on the cfdi.',
        compute='_compute_cfdi_values')
    l10n_mx_edi_time_invoice = fields.Char(
        string='Time invoice', readonly=True, copy=False,
        states={'draft': [('readonly', False)]},
        help="Keep empty to use the current México central time")
    l10n_mx_edi_usage = fields.Selection([
        ('G01', 'Acquisition of merchandise'),
        ('G02', 'Returns, discounts or bonuses'),
        ('G03', 'General expenses'),
        ('I01', 'Constructions'),
        ('I02', 'Office furniture and equipment investment'),
        ('I03', 'Transportation equipment'),
        ('I04', 'Computer equipment and accessories'),
        ('I05', 'Dices, dies, molds, matrices and tooling'),
        ('I06', 'Telephone communications'),
        ('I07', 'Satellite communications'),
        ('I08', 'Other machinery and equipment'),
        ('D01', 'Medical, dental and hospital expenses.'),
        ('D02', 'Medical expenses for disability'),
        ('D03', 'Funeral expenses'),
        ('D04', 'Donations'),
        ('D05', 'Real interest effectively paid for mortgage loans (room house)'),
        ('D06', 'Voluntary contributions to SAR'),
        ('D07', 'Medical insurance premiums'),
        ('D08', 'Mandatory School Transportation Expenses'),
        ('D09', 'Deposits in savings accounts, premiums based on pension plans.'),
        ('D10', 'Payments for educational services (Colegiatura)'),
        ('P01', 'To define'),
    ], 'Usage', default='P01',
        help='Used in CFDI 3.3 to express the key to the usage that will '
        'gives the receiver to this invoice. This value is defined by the '
        'customer. \nNote: It is not cause for cancellation if the key set is '
        'not the usage that will give the receiver of the document.')
    l10n_mx_edi_origin = fields.Char(
        string='CFDI Origin', copy=False,
        help='In some cases like payments, credit notes, debit notes, '
        'invoices re-signed or invoices that are redone due to payment in '
        'advance will need this field filled, the format is: \nOrigin Type|'
        'UUID1, UUID2, ...., UUIDn.\nWhere the origin type could be:\n'
        u'- 01: Nota de crédito\n'
        u'- 02: Nota de débito de los documentos relacionados\n'
        u'- 03: Devolución de mercancía sobre facturas o traslados previos\n'
        u'- 04: Sustitución de los CFDI previos\n'
        '- 05: Traslados de mercancias facturados previamente\n'
        '- 06: Factura generada por los traslados previos\n'
        u'- 07: CFDI por aplicación de anticipo')
    l10n_mx_edi_cer_source = fields.Char(
        'Certificate Source',
        help='Used in CFDI like attribute derived from the exception of '
        'certificates of Origin of the Free Trade Agreements that Mexico '
        'has celebrated with several countries. If it has a value, it will '
        'indicate that it serves as certificate of origin and this value will '
        'be set in the CFDI node "NumCertificadoOrigen".')
    l10n_mx_edi_external_trade = fields.Boolean(
        'Need external trade?', compute='_compute_need_external_trade',
        inverse='_inverse_need_external_trade', store=True,
        help='If this field is active, the CFDI that generates this invoice '
        'will include the complement "External Trade".')

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    @api.model
    def l10n_mx_edi_retrieve_attachments(self):
        '''Retrieve all the cfdi attachments generated for this invoice.

        :return: An ir.attachment recordset
        '''
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
        if cfdi is None and self.l10n_mx_edi_cfdi:
            cfdi = base64.decodestring(self.l10n_mx_edi_cfdi)
        return fromstring(cfdi) if cfdi else None

    @api.model
    def l10n_mx_edi_get_et_etree(self, cfdi):
        """Get the ComercioExterior node from the cfdi.
        :param cfdi: The cfdi as etree
        :return: the ComercioExterior node
        """
        if not hasattr(cfdi, 'Complemento'):
            return None
        attribute = 'cce11:ComercioExterior[1]'
        namespace = {'cce11': 'http://www.sat.gob.mx/ComercioExterior11'}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        return node[0] if node else None

    @api.model
    def l10n_mx_edi_get_payment_method_cfdi(self):
        self.ensure_one()
        cfdi = self.l10n_mx_edi_get_xml_etree()
        return cfdi.get('MetodoPago') if cfdi is not None else None

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
    def _get_l10n_mx_edi_cadena(self):
        self.ensure_one()
        #get the xslt path
        xslt_path = CFDI_XSLT_CADENA_TFD
        #get the cfdi as eTree
        cfdi = base64.decodestring(self.l10n_mx_edi_cfdi)
        cfdi = self.l10n_mx_edi_get_xml_etree(cfdi)
        cfdi = self.l10n_mx_edi_get_tfd_etree(cfdi)
        #return the cadena
        return self.l10n_mx_edi_generate_cadena(xslt_path, cfdi)

    @api.model
    def l10n_mx_edi_generate_cadena(self, xslt_path, cfdi_as_tree):
        '''Generate the cadena of the cfdi based on an xslt file.
        The cadena is the sequence of data formed with the information contained within the cfdi.
        This can be encoded with the certificate to create the digital seal.
        Since the cadena is generated with the invoice data, any change in it will be noticed resulting in a different
        cadena and so, ensure the invoice has not been modified.

        :param xslt_path: The path to the xslt file.
        :param cfdi_as_tree: The cfdi converted as a tree
        :return: A string computed with the invoice data called the cadena
        '''
        xslt_root = etree.parse(tools.file_open(xslt_path))
        return str(etree.XSLT(xslt_root)(cfdi_as_tree))

    @api.model
    def l10n_mx_edi_is_customer_address_required(self):
        '''Look in the customer address to know if enough address information can be found to justify the creation
         of an address block in the xml.

        :return: True if at least one required field is found.
        '''
        self.ensure_one()
        partner_id = self.partner_id.commercial_partner_id
        if self.partner_id.type == 'invoice':
            partner_id = self.partner_id
        address_fields = ['street_name',
                          'street_number',
                          'street_number2',
                          'l10n_mx_edi_colony',
                          'l10n_mx_edi_locality',
                          'city',
                          'state_id',
                          'country_id',
                          'zip']
        for field in address_fields:
            if getattr(partner_id, field):
                return True
        return False

    def l10n_mx_edi_amount_to_text(self):
        """Method to transform a float amount to text words
        E.g. 100 - ONE HUNDRED
        :returns: Amount transformed to words mexican format for invoices
        :rtype: str
        """
        self.ensure_one()
        currency = self.currency_id.name.upper()
        # M.N. = Moneda Nacional (National Currency)
        # M.E. = Moneda Extranjera (Foreign Currency)
        currency_type = 'M.N' if currency == 'MXN' else 'M.E.'
        # Split integer and decimal part
        amount_i, amount_d = divmod(self.amount_total, 1)
        amount_d = round(amount_d, 2)
        amount_d = int(round(amount_d * 100, 2))
        words = self.currency_id.with_context(lang=self.partner_id.lang or 'es_ES').amount_to_text(amount_i).upper()
        invoice_words = '%(words)s %(amount_d)02d/100 %(curr_t)s' % dict(
            words=words, amount_d=amount_d, curr_t=currency_type)
        return invoice_words

    def l10n_mx_edi_is_required(self):
        self.ensure_one()
        return (self.is_sale_document() and self.company_id.country_id == self.env.ref('base.mx'))

    def l10n_mx_edi_log_error(self, message):
        self.ensure_one()
        self.message_post(body=_('Error during the process: %s') % message, subtype='account.mt_invoice_validated')

    # -------------------------------------------------------------------------
    # SAT/PAC service methods
    # -------------------------------------------------------------------------

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
        for inv in self:
            cfdi = base64.decodestring(inv.l10n_mx_edi_cfdi)
            try:
                transport = Transport(timeout=20)
                client = Client(url, transport=transport)
                response = client.service.timbrar(username, password, cfdi, False)
            except Exception as e:
                inv.l10n_mx_edi_log_error(str(e))
                continue
            res = response.resultados
            msg = getattr(res[0] if res else response, 'mensaje', None)
            code = getattr(res[0] if res else response, 'status', None)
            xml_signed = getattr(res[0] if res else response, 'cfdiTimbrado', None)
            if xml_signed:
                xml_signed = base64.b64encode(xml_signed)
            inv._l10n_mx_edi_post_sign_process(
                xml_signed if xml_signed else None, code, msg)

    def _l10n_mx_edi_solfact_cancel(self, pac_info):
        '''CANCEL for Solucion Factible.
        '''
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        for inv in self:
            uuids = [inv.l10n_mx_edi_cfdi_uuid]
            certificate_ids = inv.company_id.l10n_mx_edi_certificate_ids
            certificate_id = certificate_ids.sudo().get_valid_certificate()
            cer_pem = certificate_id.get_pem_cer(
                certificate_id.content)
            key_pem = certificate_id.get_pem_key(
                certificate_id.key, certificate_id.password)
            key_password = certificate_id.password
            try:
                transport = Transport(timeout=20)
                client = Client(url, transport=transport)
                response = client.service.cancelar(
                    username, password, uuids, cer_pem, key_pem, key_password)
            except Exception as e:
                inv.l10n_mx_edi_log_error(str(e))
                continue
            res = response.resultados
            code = getattr(res[0], 'statusUUID', None) if res else getattr(response, 'status', None)
            cancelled = code in ('201', '202')  # cancelled or previously cancelled
            # no show code and response message if cancel was success
            msg = '' if cancelled else getattr(res[0] if res else response, 'mensaje', None)
            code = '' if cancelled else code
            inv._l10n_mx_edi_post_cancel_process(cancelled, code, msg)

    def _l10n_mx_edi_finkok_info(self, company_id, service_type):
        test = company_id.l10n_mx_edi_pac_test_env
        username = company_id.l10n_mx_edi_pac_username
        password = company_id.l10n_mx_edi_pac_password
        if service_type == 'sign':
            url = 'http://demo-facturacion.finkok.com/servicios/soap/stamp.wsdl'\
                if test else 'http://facturacion.finkok.com/servicios/soap/stamp.wsdl'
        else:
            url = 'http://demo-facturacion.finkok.com/servicios/soap/cancel.wsdl'\
                if test else 'http://facturacion.finkok.com/servicios/soap/cancel.wsdl'
        return {
            'url': url,
            'multi': False,  # TODO: implement multi
            'username': 'cfdi@vauxoo.com' if test else username,
            'password': 'vAux00__' if test else password,
        }

    def _l10n_mx_edi_finkok_sign(self, pac_info):
        '''SIGN for Finkok.
        '''
        url = pac_info['url']
        username = pac_info['username']
        password = pac_info['password']
        for inv in self:
            cfdi = base64.decodestring(inv.l10n_mx_edi_cfdi)
            try:
                transport = Transport(timeout=20)
                client = Client(url, transport=transport)
                response = client.service.stamp(cfdi, username, password)
            except Exception as e:
                inv.l10n_mx_edi_log_error(str(e))
                continue
            code = 0
            msg = None
            if response.Incidencias:
                code = getattr(response.Incidencias.Incidencia[0], 'CodigoError', None)
                msg = getattr(response.Incidencias.Incidencia[0], 'MensajeIncidencia', None)
            xml_signed = getattr(response, 'xml', None)
            if xml_signed:
                xml_signed = base64.b64encode(xml_signed.encode('utf-8'))
            inv._l10n_mx_edi_post_sign_process(xml_signed, code, msg)

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
            cer_pem = certificate_id.get_pem_cer(
                certificate_id.content)
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
                response = client.service.cancel(
                    invoices_list, username, password, company_id.vat, cer_pem, key_pem)
            except Exception as e:
                inv.l10n_mx_edi_log_error(str(e))
                continue
            if not getattr(response, 'Folios', None):
                code = getattr(response, 'CodEstatus', None)
                msg = _("Cancelling got an error") if code else _('A delay of 2 hours has to be respected before to cancel')
            else:
                code = getattr(response.Folios.Folio[0], 'EstatusUUID', None)
                cancelled = code in ('201', '202')  # cancelled or previously cancelled
                # no show code and response message if cancel was success
                code = '' if cancelled else code
                msg = '' if cancelled else _("Cancelling got an error")
            inv._l10n_mx_edi_post_cancel_process(cancelled, code, msg)

    @api.model
    def l10n_mx_edi_get_pac_version(self):
        '''Returns the cfdi version to generate the CFDI.
        In December, 1, 2017 the CFDI 3.2 is deprecated, after of July 1, 2018
        the CFDI 3.3 could be used.
        '''
        version = self.env['ir.config_parameter'].sudo().get_param(
            'l10n_mx_edi_cfdi_version', '3.3')
        return version

    @run_after_commit
    def _l10n_mx_edi_call_service(self, service_type):
        '''Call the right method according to the pac_name, it's info returned by the '_l10n_mx_edi_%s_info' % pac_name'
        method and the service_type passed as parameter.
        :param service_type: sign or cancel
        '''
        # Regroup the invoices by company (= by pac)
        comp_x_records = groupby(self, lambda r: r.company_id)
        for company_id, records in comp_x_records:
            pac_name = company_id.l10n_mx_edi_pac
            if not pac_name:
                continue
            # Get the informations about the pac
            pac_info_func = '_l10n_mx_edi_%s_info' % pac_name
            service_func = '_l10n_mx_edi_%s_%s' % (pac_name, service_type)
            pac_info = getattr(self, pac_info_func)(company_id, service_type)
            # Call the service with invoices one by one or all together according to the 'multi' value.
            multi = pac_info.pop('multi', False)
            if multi:
                # rebuild the recordset
                records = self.env['account.move'].search(
                    [('id', 'in', self.ids), ('company_id', '=', company_id.id)])
                getattr(records, service_func)(pac_info)
            else:
                for record in records:
                    getattr(record, service_func)(pac_info)

    def _l10n_mx_edi_post_sign_process(self, xml_signed, code=None, msg=None):
        '''Post process the results of the sign service.

        :param xml_signed: the xml signed datas codified in base64
        :param code: an eventual error code
        :param msg: an eventual error msg
        '''
        self.ensure_one()
        if xml_signed:
            # Post append addenda
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
            xml_signed = self.l10n_mx_edi_append_addenda(xml_signed)
            post_msg = [_('The content of the attachment has been updated')]
        else:
            body_msg = _('The sign service requested failed')
            post_msg = []
        if code:
            post_msg.extend([_('Code: %s') % code])
        if msg:
            post_msg.extend([_('Message: %s') % msg])
        self.message_post(
            body=body_msg + create_list_html(post_msg),
            subtype='account.mt_invoice_validated')

    def _l10n_mx_edi_sign(self):
        '''Call the sign service with records that can be signed.
        '''
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
        else:
            body_msg = _('The cancel service requested failed')
        post_msg = []
        if code:
            post_msg.extend([_('Code: %s') % code])
        if msg:
            post_msg.extend([_('Message: %s') % msg])
        self.message_post(
            body=body_msg + create_list_html(post_msg),
            subtype='account.mt_invoice_validated')

    def _l10n_mx_edi_cancel(self):
        '''Call the cancel service with records that can be signed.
        '''
        records = self.search([
            ('l10n_mx_edi_pac_status', 'in', ['to_sign', 'signed', 'to_cancel', 'retry']),
            ('id', 'in', self.ids)])
        for record in records:
            if record.l10n_mx_edi_pac_status in ['to_sign', 'retry']:
                record.l10n_mx_edi_pac_status = False
                record.message_post(body=_('The cancel service has been called with success'),
                    subtype='account.mt_invoice_validated')
            else:
                record.l10n_mx_edi_pac_status = 'to_cancel'
        records = self.search([
            ('l10n_mx_edi_pac_status', '=', 'to_cancel'),
            ('id', 'in', self.ids)])
        records._l10n_mx_edi_call_service('cancel')

    # -------------------------------------------------------------------------
    # Account invoice methods
    # -------------------------------------------------------------------------

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        '''Set the payment bank account on the invoice as the first of the selected partner.
        '''
        # OVERRIDE
        res = super(AccountMove, self)._onchange_partner_id()
        if self.commercial_partner_id.bank_ids:
            self.l10n_mx_edi_partner_bank_id = self.commercial_partner_id.bank_ids[0].id
        return res

    def button_draft(self):
        """Reset l10n_mx_edi_time_invoice when invoice state set to draft"""
        # OVERRIDE
        if self and any([r.l10n_mx_edi_is_required() for r in self]):
            signed = self.filtered(lambda r: r.l10n_mx_edi_is_required() and
                                   not r.company_id.l10n_mx_edi_pac_test_env and
                                   r.l10n_mx_edi_cfdi_uuid)
            signed.l10n_mx_edi_update_sat_status()
            not_allow = signed.filtered(lambda r: r.l10n_mx_edi_sat_status != 'cancelled' or r.l10n_mx_edi_pac_status == 'to_cancel')
            for record in not_allow:
                record.message_post(
                    subject=_('An error occurred while setting to draft.'),
                    message_type='comment',
                    body=_('This invoice does not have a properly cancelled XML and '
                           'it was signed at least once, please cancel properly with '
                           'the SAT.'))
            allow = (self - not_allow).filtered(lambda inv: inv.state == 'cancel')
            allow.write({'l10n_mx_edi_time_invoice': False,
                         'l10n_mx_edi_pac_status': False})
            for record in allow.filtered('l10n_mx_edi_cfdi_uuid'):
                record.l10n_mx_edi_origin = record._set_cfdi_origin('04', [record.l10n_mx_edi_cfdi_uuid])
            return super(AccountMove, self - not_allow).button_draft()
        else:
            return super(AccountMove, self).button_draft()

    def _reverse_moves(self, default_values_list, cancel=False):
        """When is created the invoice refund is assigned the reference to
        the invoice that was generate it"""
        # OVERRIDE
        for i, move in enumerate(self):
            if move.l10n_mx_edi_is_required() and move.l10n_mx_edi_cfdi_uuid:
                default_values_list[i]['l10n_mx_edi_origin'] = '%s|%s' % ('01', move.l10n_mx_edi_cfdi_uuid)
        return super(AccountMove, self)._reverse_moves(default_values_list, cancel=cancel)

    @api.depends('l10n_mx_edi_cfdi_name', 'l10n_mx_edi_pac_status')
    def _compute_cfdi_values(self):
        '''Fill the invoice fields from the cfdi values.
        '''
        for inv in self:
            attachment_id = inv.l10n_mx_edi_retrieve_last_attachment()
            # At this moment, the attachment contains the file size in its 'datas' field because
            # to save some memory, the attachment will store its data on the physical disk.
            # To avoid this problem, we read the 'datas' directly on the disk.
            datas = attachment_id._file_read(attachment_id.store_fname) if attachment_id else None
            inv.l10n_mx_edi_cfdi_uuid = None
            if not datas:
                if attachment_id:
                    _logger.error('The CFDI attachment cannot be found')
                inv.l10n_mx_edi_cfdi = None
                inv.l10n_mx_edi_cfdi_supplier_rfc = None
                inv.l10n_mx_edi_cfdi_customer_rfc = None
                inv.l10n_mx_edi_cfdi_amount = None
                continue
            inv.l10n_mx_edi_cfdi = datas
            cfdi = base64.decodestring(datas).replace(
                b'xmlns:schemaLocation', b'xsi:schemaLocation')
            tree = inv.l10n_mx_edi_get_xml_etree(cfdi)
            # if already signed, extract uuid
            tfd_node = inv.l10n_mx_edi_get_tfd_etree(tree)
            if tfd_node is not None:
                inv.l10n_mx_edi_cfdi_uuid = tfd_node.get('UUID')
            inv.l10n_mx_edi_cfdi_amount = tree.get('Total', tree.get('total'))
            inv.l10n_mx_edi_cfdi_supplier_rfc = tree.Emisor.get(
                'Rfc', tree.Emisor.get('rfc'))
            inv.l10n_mx_edi_cfdi_customer_rfc = tree.Receptor.get(
                'Rfc', tree.Receptor.get('rfc'))
            certificate = tree.get('noCertificado', tree.get('NoCertificado'))

    @api.depends('partner_id')
    def _compute_need_external_trade(self):
        """Assign the "Need external trade?" value how in the partner"""
        out_invoice = self.filtered(lambda i: i.type == 'out_invoice')
        for record in out_invoice:
            record.l10n_mx_edi_external_trade = record.partner_id.l10n_mx_edi_external_trade
        for record in self - out_invoice:
            record.l10n_mx_edi_external_trade = False

    def _inverse_need_external_trade(self):
        return True

    def _l10n_mx_edi_create_taxes_cfdi_values(self):
        '''Create the taxes values to fill the CFDI template.
        '''
        self.ensure_one()
        values = {
            'total_withhold': 0,
            'total_transferred': 0,
            'withholding': [],
            'transferred': [],
        }
        taxes = {}
        for line in self.invoice_line_ids.filtered('price_subtotal'):
            price = line.price_unit * (1.0 - (line.discount or 0.0) / 100.0)
            tax_line = {tax['id']: tax for tax in line.tax_ids.compute_all(
                price, line.currency_id, line.quantity, line.product_id, line.partner_id, self.type in ('in_refund', 'out_refund'))['taxes']}
            for tax in line.tax_ids.filtered(lambda r: r.l10n_mx_cfdi_tax_type != 'Exento'):
                tax_dict = tax_line.get(tax.id, {})
                amount = round(abs(tax_dict.get(
                    'amount', tax.amount / 100 * float("%.2f" % line.price_subtotal))), 2)
                rate = round(abs(tax.amount), 2)
                if tax.id not in taxes:
                    taxes.update({tax.id: {
                        'name': (tax.invoice_repartition_line_ids.tag_ids[0].name
                                 if tax.mapped('invoice_repartition_line_ids.tag_ids') else tax.name).upper(),
                        'amount': amount,
                        'rate': rate if tax.amount_type == 'fixed' else rate / 100.0,
                        'type': tax.l10n_mx_cfdi_tax_type,
                        'tax_amount': tax_dict.get('amount', tax.amount),
                    }})
                else:
                    taxes[tax.id].update({
                        'amount': taxes[tax.id]['amount'] + amount
                    })
                if tax.amount >= 0:
                    values['total_transferred'] += amount
                else:
                    values['total_withhold'] += amount
        values['transferred'] = [tax for tax in taxes.values() if tax['tax_amount'] >= 0]
        values['withholding'] = self._l10n_mx_edi_group_withholding(
            [tax for tax in taxes.values() if tax['tax_amount'] < 0])
        return values

    @api.model
    def _l10n_mx_edi_group_withholding(self, withholding):
        """In the Taxes node the withholding must be group by tax type"""
        if not withholding:
            return withholding
        new_withholding = {}
        for tax in withholding:
            if tax['name'] not in new_withholding:
                new_withholding.update({tax['name']: tax})
                continue
            new_withholding[tax['name']].update({'amount': new_withholding[
                tax['name']]['amount'] + tax['amount']})
        return list(new_withholding.values())

    @staticmethod
    def _l10n_mx_get_serie_and_folio(number):
        values = {'serie': None, 'folio': None}
        number = (number or '').strip()
        number_matchs = [rn for rn in re.finditer('\d+', number)]
        if number_matchs:
            last_number_match = number_matchs[-1]
            values['serie'] = number[:last_number_match.start()] or None
            values['folio'] = last_number_match.group().lstrip('0') or None
        return values

    @staticmethod
    def _get_string_cfdi(text, size=100):
        """Replace from text received the characters that are not found in the
        regex. This regex is taken from SAT documentation
        https://goo.gl/C9sKH6
        text: Text to remove extra characters
        size: Cut the string in size len
        Ex. 'Product ABC (small size)' - 'Product ABC small size'"""
        if not text:
            return None
        text = text.replace('|', ' ')
        return text.strip()[:size]

    def _l10n_mx_edi_get_payment_policy(self):
        self.ensure_one()
        version = self.l10n_mx_edi_get_pac_version()
        term_ids = self.invoice_payment_term_id.line_ids
        if version == '3.2':
            if len(term_ids.ids) > 1:
                return 'Pago en parcialidades'
            else:
                return 'Pago en una sola exhibición'
        elif version == '3.3' and self.invoice_date_due and self.invoice_date:
            if self.type == 'out_refund':
                return 'PUE'
            # In CFDI 3.3 - SAT 2018 rule 2.7.1.44, the payment policy is PUE
            # if the invoice will be paid before 17th of the following month,
            # PPD otherwise
            date_pue = (fields.Date.from_string(self.invoice_date) +
                        relativedelta(day=17, months=1))
            invoice_date_due = fields.Date.from_string(self.invoice_date_due)
            if (invoice_date_due > date_pue or len(term_ids) > 1):
                return 'PPD'
            return 'PUE'
        return ''

    def _l10n_mx_edi_create_cfdi_values(self):
        '''Create the values to fill the CFDI template.
        '''
        self.ensure_one()
        precision_digits = self.currency_id.l10n_mx_edi_decimal_places
        if precision_digits is False:
            raise UserError(_(
                "The SAT does not provide information for the currency %s.\n"
                "You must get manually a key from the PAC to confirm the "
                "currency rate is accurate enough."), self.currency_id)
        partner_id = self.partner_id
        if self.partner_id.type != 'invoice':
            partner_id = self.partner_id.commercial_partner_id
        values = {
            'record': self,
            'currency_name': self.currency_id.name,
            'supplier': self.company_id.partner_id.commercial_partner_id,
            'issued': self.journal_id.l10n_mx_address_issued_id,
            'customer': partner_id,
            'fiscal_regime': self.company_id.l10n_mx_edi_fiscal_regime,
            'payment_method': self.l10n_mx_edi_payment_method_id.code,
            'use_cfdi': self.l10n_mx_edi_usage,
            'conditions': self._get_string_cfdi(
                self.invoice_payment_term_id.name, 1000) if self.invoice_payment_term_id else False,
        }

        values.update(self._l10n_mx_get_serie_and_folio(self.name))
        ctx = dict(company_id=self.company_id.id, date=self.invoice_date)
        mxn = self.env.ref('base.MXN').with_context(ctx)
        invoice_currency = self.currency_id.with_context(ctx)
        values['rate'] = ('%.6f' % (
            invoice_currency._convert(1, mxn, self.company_id, self.invoice_date or fields.Date.today(), round=False))) if self.currency_id.name != 'MXN' else False

        values['document_type'] = 'ingreso' if self.type == 'out_invoice' else 'egreso'
        values['payment_policy'] = self._l10n_mx_edi_get_payment_policy()
        domicile = self.journal_id.l10n_mx_address_issued_id or self.company_id
        values['domicile'] = '%s %s, %s' % (
                domicile.city,
                domicile.state_id.name,
                domicile.country_id.name,
        )

        values['decimal_precision'] = precision_digits
        subtotal_wo_discount = lambda l: float_round(
            l.price_subtotal / (1 - l.discount/100) if l.discount != 100 else
            l.price_unit * l.quantity, int(precision_digits))
        values['subtotal_wo_discount'] = subtotal_wo_discount
        get_discount = lambda l, d: ('%.*f' % (
            int(d), subtotal_wo_discount(l) - l.price_subtotal)) if l.discount else False
        values['total_discount'] = get_discount
        total_discount = sum([float(get_discount(p, precision_digits)) for p in self.invoice_line_ids])
        values['amount_untaxed'] = '%.*f' % (
            precision_digits, sum([subtotal_wo_discount(p) for p in self.invoice_line_ids]))
        values['amount_discount'] = '%.*f' % (precision_digits, total_discount) if total_discount else None

        values['taxes'] = self._l10n_mx_edi_create_taxes_cfdi_values()
        values['amount_total'] = '%0.*f' % (precision_digits,
            float(values['amount_untaxed']) - float(values['amount_discount'] or 0) + (
                values['taxes']['total_transferred'] or 0) - (values['taxes']['total_withhold'] or 0))

        values['tax_name'] = lambda t: {'ISR': '001', 'IVA': '002', 'IEPS': '003'}.get(t, False)

        if self.l10n_mx_edi_partner_bank_id:
            digits = [s for s in self.l10n_mx_edi_partner_bank_id.acc_number if s.isdigit()]
            acc_4number = ''.join(digits)[-4:]
            values['account_4num'] = acc_4number if len(acc_4number) == 4 else None
        else:
            values['account_4num'] = None

        values.update(self._get_external_trade_values(values))
        return values

    def _get_external_trade_values(self, values):
        """Create the values to fill the CFDI template with external trade.
        """
        self.ensure_one()
        if not self.l10n_mx_edi_external_trade:
            return values

        date = self.invoice_date or fields.Date.today()
        company_id = self.company_id
        ctx = dict(company_id=company_id.id, date=date)
        customer = values['customer']
        values.update({
            'usd': self.env.ref('base.USD').with_context(ctx),
            'mxn': self.env.ref('base.MXN').with_context(ctx),
            'europe_group': self.env.ref('base.europe'),
            'receiver_reg_trib': customer.vat,
        })
        values['quantity_aduana'] = lambda p, i: sum([
            l.l10n_mx_edi_qty_umt for l in i.invoice_line_ids
            if l.product_id == p])
        values['unit_value_usd'] = lambda l, c, u: c._convert(
            l.l10n_mx_edi_price_unit_umt, u, company_id, date)
        values['amount_usd'] = lambda origin, dest, amount: origin._convert(
            amount, dest, company_id, date, round=False)
        # http://omawww.sat.gob.mx/informacion_fiscal/factura_electronica/Documents/Complementoscfdi/GuiaComercioExterior3_3.pdf
        # ValorDolares : it depends of the currency  (p. 62-63):
        #   - if currency is MXN: ValorDolares = Importe (subtotal without discounts) / TipoCambioUSD
        #   - if currency is USD: ValorDolares = Importe
        #   - if currency is anoter: ValorDolares = Importe x TipoCambio / TipoCambioUSD
        # There is a common mistake to mutiply the Qty UMT with the unit price UMT. (p. 76)
        #
        # TotalUSD : must be the sum of all the Valor Dolares fields (p. 48)
        values['valor_usd'] = lambda l, u, c: c._convert(
            l.price_subtotal / (1 - l.discount/100) if l.discount != 100 else
            l.price_unit * l.quantity, u, company_id, date)
        values['total_usd'] = lambda i, u, c: sum([values['valor_usd'](l, u, c)
            for l in i])

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

    def l10n_mx_edi_append_addenda(self, xml_signed):
        self.ensure_one()
        addenda = (
            self.partner_id.l10n_mx_edi_addenda or
            self.partner_id.commercial_partner_id.l10n_mx_edi_addenda)
        if not addenda:
            return xml_signed
        values = {
            'record': self,
        }
        addenda_node_str = addenda.render(values=values).strip()
        if not addenda_node_str:
            return xml_signed
        tree = fromstring(base64.decodestring(xml_signed))
        addenda_node = fromstring(addenda_node_str)
        if addenda_node.tag != '{http://www.sat.gob.mx/cfd/3}Addenda':
            node = etree.Element(etree.QName(
                'http://www.sat.gob.mx/cfd/3', 'Addenda'))
            node.append(addenda_node)
            addenda_node = node
        tree.append(addenda_node)
        self.message_post(
            body=_('Addenda has been added in the CFDI with success'),
            subtype='account.mt_invoice_validated')
        xml_signed = base64.encodestring(etree.tostring(
            tree, pretty_print=True, xml_declaration=True, encoding='UTF-8'))
        attachment_id = self.l10n_mx_edi_retrieve_last_attachment()
        attachment_id.write({
            'datas': xml_signed,
            'mimetype': 'application/xml'
        })
        return xml_signed

    def _l10n_mx_edi_create_cfdi(self):
        '''Creates and returns a dictionnary containing 'cfdi' if the cfdi is well created, 'error' otherwise.
        '''
        self.ensure_one()
        qweb = self.env['ir.qweb']
        error_log = []
        company_id = self.company_id
        pac_name = company_id.l10n_mx_edi_pac
        if self.l10n_mx_edi_external_trade:
            # Call the onchange to obtain the values of l10n_mx_edi_qty_umt
            # and l10n_mx_edi_price_unit_umt, this is necessary when the
            # invoice is created from the sales order or from the picking
            self.invoice_line_ids.onchange_quantity()
            self.invoice_line_ids._set_price_unit_umt()
        values = self._l10n_mx_edi_create_cfdi_values()

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
            return {'error': _('Please check your configuration: ') + create_list_html(error_log)}

        # -Compute date and time of the invoice
        time_invoice = datetime.strptime(self.l10n_mx_edi_time_invoice,
                                         DEFAULT_SERVER_TIME_FORMAT).time()
        # -----------------------
        # Create the EDI document
        # -----------------------
        version = self.l10n_mx_edi_get_pac_version()

        # -Compute certificate data
        values['date'] = datetime.combine(
            fields.Datetime.from_string(self.invoice_date), time_invoice).strftime('%Y-%m-%dT%H:%M:%S')
        values['certificate_number'] = certificate_id.serial_number
        values['certificate'] = certificate_id.sudo().get_data()[0]

        # -Compute cfdi
        cfdi = qweb.render(CFDI_TEMPLATE_33, values=values)
        cfdi = cfdi.replace(b'xmlns__', b'xmlns:')
        node_sello = 'Sello'
        attachment = self.env.ref('l10n_mx_edi.xsd_cached_cfdv33_xsd', False)
        xsd_datas = base64.b64decode(attachment.datas) if attachment else b''

        # -Compute cadena
        tree = self.l10n_mx_edi_get_xml_etree(cfdi)
        cadena = self.l10n_mx_edi_generate_cadena(CFDI_XSLT_CADENA % version, tree)
        tree.attrib[node_sello] = certificate_id.sudo().get_encrypted_cadena(cadena)

        # Check with xsd
        if xsd_datas:
            try:
                with BytesIO(xsd_datas) as xsd:
                    _check_with_xsd(tree, xsd)
            except (IOError, ValueError):
                _logger.info(
                    _('The xsd file to validate the XML structure was not found'))
            except Exception as e:
                return {'error': (_('The cfdi generated is not valid') +
                                    create_list_html(str(e).split('\\n')))}

        return {'cfdi': etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8')}

    def _l10n_mx_edi_retry(self):
        '''Try to generate the cfdi attachment and then, sign it.
        '''
        version = self.l10n_mx_edi_get_pac_version()
        for inv in self:
            cfdi_values = inv._l10n_mx_edi_create_cfdi()
            error = cfdi_values.pop('error', None)
            cfdi = cfdi_values.pop('cfdi', None)
            if error:
                # cfdi failed to be generated
                inv.l10n_mx_edi_pac_status = 'retry'
                inv.message_post(body=error, subtype='account.mt_invoice_validated')
                _logger.error('The CFDI generated for the invoice %s is not valid: %s' % (inv.name, str(error)))
                continue
            # cfdi has been successfully generated
            inv.l10n_mx_edi_pac_status = 'to_sign'
            filename = ('%s-%s-MX-Invoice-%s.xml' % (
                inv.journal_id.code, inv.name, version.replace('.', '-'))).replace('/', '')
            ctx = self.env.context.copy()
            ctx.pop('default_type', False)
            inv.l10n_mx_edi_cfdi_name = filename
            attachment_id = self.env['ir.attachment'].with_context(ctx).create({
                'name': filename,
                'res_id': inv.id,
                'res_model': inv._name,
                'datas': base64.encodestring(cfdi),
                'description': 'Mexican invoice',
                })
            inv.message_post(
                body=_('CFDI document generated (may be not signed)'),
                attachment_ids=[attachment_id.id],
                subtype='account.mt_invoice_validated')
            inv._l10n_mx_edi_sign()

    def post(self):
        # OVERRIDE
        # Assign time and date coming from a certificate.
        for move in self.filtered(lambda move: move.l10n_mx_edi_is_required()):

            # Line having a negative amount is not allowed.
            for line in move.invoice_line_ids:
                if line.price_subtotal < 0:
                    raise UserError(_("Invoice lines having a negative amount are not allowed to generate the CFDI. Please create a credit note instead."))

            date_mx = self.env['l10n_mx_edi.certificate'].sudo().get_mx_current_datetime()
            if not move.invoice_date:
                move.invoice_date = date_mx.date()
                move.with_context(
                    check_move_validity=False)._onchange_invoice_date()
            if not move.l10n_mx_edi_time_invoice:
                move.l10n_mx_edi_time_invoice = date_mx
                move._l10n_mx_edi_update_hour_timezone()

        result = super(AccountMove, self).post()

        # Generates the cfdi attachments for mexican companies when validated.
        version = self.l10n_mx_edi_get_pac_version().replace('.', '-')
        trans_field = 'transaction_ids' in self._fields
        for move in self.filtered(lambda move: move.l10n_mx_edi_is_required()):
            if move.type == 'out_refund' and move.reversed_entry_id and not move.reversed_entry_id.l10n_mx_edi_cfdi_uuid:
                move.message_post(
                    body='<p style="color:red">' + _(
                        'The invoice related has no valid fiscal folio. For this '
                        'reason, this refund didn\'t generate a fiscal document.') + '</p>',
                    subtype='account.mt_invoice_validated')
                continue

            move.l10n_mx_edi_cfdi_name = ('%s-%s-MX-Invoice-%s.xml' % (move.journal_id.code, move.invoice_payment_ref, version)).replace('/', '')
            subscription = 'subscription_id' in move.invoice_line_ids._fields and move.invoice_line_ids.filtered('subscription_id')
            if subscription or (trans_field and move.mapped('transaction_ids')):
                move = move.with_context(disable_after_commit=True)
            move._l10n_mx_edi_retry()
        return result

    def button_cancel(self):
        inv_mx = self.filtered(lambda r: r.l10n_mx_edi_is_required())
        if not inv_mx:
            return super(AccountMove, self).button_cancel()
        inv_mx.l10n_mx_edi_update_sat_status()
        to_cancel = inv_mx.filtered(
            lambda inv: inv.l10n_mx_edi_pac_status in [
                False, 'retry', 'to_sign', 'cancelled'] or
            inv.l10n_mx_edi_sat_status == 'cancelled')
        is_from_cron = self._context.get('called_from_cron', False)
        if is_from_cron:
            to_cancel |= inv_mx
        for invoice in (inv_mx - to_cancel) if not is_from_cron else []:
            invoice.message_post(body=_(
                'On this invoice can not be used the cancel button, because '
                'the invoice is not cancelled in the SAT system. If you want '
                'to cancel this invoice, press the option "Request '
                'Cancellation", and when the SAT approve the cancellation '
                'this document will be cancelled automatically.'))

        result = super(AccountMove, to_cancel).button_cancel()

        # Cancel the cfdi attachments for mexican companies when cancelled.
        for move in to_cancel.filtered(lambda move: move.l10n_mx_edi_is_required()):
            if move.l10n_mx_edi_is_required():
                move._l10n_mx_edi_cancel()
        return result

    def l10n_mx_edi_update_pac_status(self):
        '''Synchronize both systems: Odoo & PAC if the invoices need to be signed or cancelled.
        '''
        for record in self:
            if record.l10n_mx_edi_pac_status in ('to_sign', 'retry'):
                record._l10n_mx_edi_retry()
            elif record.l10n_mx_edi_pac_status == 'to_cancel':
                record._l10n_mx_edi_cancel()

    def l10n_mx_edi_update_sat_status(self):
        '''Synchronize both systems: Odoo & SAT to make sure the invoice is valid.
        '''
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
        for inv in self.filtered('l10n_mx_edi_cfdi'):
            supplier_rfc = inv.l10n_mx_edi_cfdi_supplier_rfc
            customer_rfc = inv.l10n_mx_edi_cfdi_customer_rfc
            total = float_repr(inv.l10n_mx_edi_cfdi_amount,
                               precision_digits=inv.currency_id.decimal_places)
            uuid = inv.l10n_mx_edi_cfdi_uuid
            params = '?re=%s&amp;rr=%s&amp;tt=%s&amp;id=%s' % (
                tools.html_escape(tools.html_escape(supplier_rfc or '')),
                tools.html_escape(tools.html_escape(customer_rfc or '')),
                total or 0.0, uuid or '')
            soap_env = template.format(data=params)
            try:
                soap_xml = requests.post(url, data=soap_env,
                                         headers=headers, timeout=20)
                response = fromstring(soap_xml.text)
                status = response.xpath(
                    '//a:Estado', namespaces=namespace)
            except Exception as e:
                inv.l10n_mx_edi_log_error(str(e))
                continue
            inv.l10n_mx_edi_sat_status = CFDI_SAT_QR_STATE.get(
                status[0] if status else '', 'none')

    def _l10n_mx_edi_sat_synchronously(self, batch_size=10):
        """Update the SAT status synchronously

        This method Calls :meth:`~.l10n_mx_edi_update_sat_status` by batches,
        ensuring changes are committed after processing each batch. This is
        intended to be able to process a lot of records on a safely manner,
        avoiding a possible sistematic failure withoud any invoice updated.

        This is especially useful when running crons.

        :param batch_size: the number of invoices to process by batch
        :type batch_size: int
        """
        for idx in range(0, len(self), batch_size):
            with self.env.cr.savepoint():
                self[idx:idx+batch_size].l10n_mx_edi_update_sat_status()

    def _set_cfdi_origin(self, rtype='', uuids=[]):
        """Try to write the origin in of the CFDI, it is important in order
        to have a centralized way to manage this elements due to the fact
        that this logic can be used in several places functionally speaking
        all around Odoo.
        :param rtype:
            - 01: Nota de crédito
            - 02: Nota de débito de los documentos relacionados
            - 03: Devolución de mercancía sobre facturas o traslados previos
            - 04: Sustitución de los CFDI previos
            - 05: Traslados de mercancias facturados previamente
            - 06: Factura generada por los traslados previos
            - 07: CFDI por aplicación de anticipo
        :param uuids:
        :return:
        """
        self.ensure_one()
        types = ['01', '02', '03', '04', '05', '06', '07']
        if not rtype in types:
            raise UserError(_('Invalid given type of document for field CFDI '
                                'Origin'))
        uuids = [u for u in uuids if isinstance(u, str)]
        ids = ','.join(uuids)
        l10n_mx_edi_origin = self.l10n_mx_edi_origin
        old_rtype = l10n_mx_edi_origin.split('|')[0] if l10n_mx_edi_origin else False
        if old_rtype and old_rtype not in types:
            raise UserError(_('Invalid type of document for field CFDI '
                              'Origin'))
        if not l10n_mx_edi_origin or old_rtype != rtype:
            origin = '%s|%s' % (rtype, ids)
            self.update({'l10n_mx_edi_origin': origin})
            return origin
        try:
            old_ids = l10n_mx_edi_origin.split('|')[1].split(',')
        except IndexError:
            raise UserError(
                _('The cfdi origin field must be filled with type and list of '
                  'cfdi separated by comma like this '
                  '"01|89966ACC-0F5C-447D-AEF3-3EED22E711EE,89966ACC-0F5C-447D-AEF3-3EED22E711EE"'
                  '\n get %s instead' % l10n_mx_edi_origin))
        ids = ','.join(old_ids + uuids)
        origin = '%s|%s' % (rtype, ids)
        self.update({'l10n_mx_edi_origin': origin})
        return origin

    def _l10n_mx_edi_update_hour_timezone(self):
        for inv in self:
            partner = inv.journal_id.l10n_mx_address_issued_id or inv.company_id.partner_id.commercial_partner_id
            tz = self._l10n_mx_edi_get_timezone(partner.state_id.code)

            # Check the TZ should be forced for the current journal
            tz_force = self.env['ir.config_parameter'].sudo().get_param(
                'l10n_mx_edi_tz_%s' % inv.journal_id.id, default=None)
            if tz_force:
                tz = timezone(tz_force)

            datetime_mx_tz = datetime.now(tz)
            inv.l10n_mx_edi_time_invoice = datetime_mx_tz.strftime("%H:%M:%S")

    def l10n_mx_edi_request_cancellation(self):
        if self.filtered(lambda inv: inv.state not in ['draft', 'posted']):
            raise UserError(_(
                'Invoice must be in draft or open state in order to be '
                'cancelled.'))
        if self.filtered(lambda inv: inv.journal_id.restrict_mode_hash_table):
            raise UserError(_(
                'You cannot modify a posted entry of this journal.\nFirst you '
                'should set the journal to allow cancelling entries.'))
        self.l10n_mx_edi_update_sat_status()
        invoices = self.filtered(lambda inv:
                                 inv.l10n_mx_edi_sat_status != 'cancelled')
        invoices._l10n_mx_edi_cancel()

    def l10n_mx_edi_cancellation(self):
        """This method only could be called from a server action or a cron.
        Is used to cancel in Odoo al the invoices that are cancelled in the
        SAT."""
        self.l10n_mx_edi_update_sat_status()
        cancelled = self.filtered(
            lambda inv: inv.l10n_mx_edi_sat_status == 'cancelled')
        env_demo = self.mapped('company_id').filtered(
            'l10n_mx_edi_pac_test_env')
        cancelled |= self.filtered(lambda inv: inv.company_id in env_demo)
        cancelled.button_cancel()

    def l10n_mx_edi_action_open_to_cancel(self):
        """Searches all the invoices not canceled in Odoo, but marked as to
        cancel in the PAC or previously canceled in the PAC."""
        invoices = self.search([
            ('state', 'not in', ['cancel']), '|',
            ('l10n_mx_edi_pac_status', 'in', ['to_cancel', 'cancelled']),
            ('l10n_mx_edi_sat_status', '=', 'cancelled')]).filtered(
                lambda inv: inv.l10n_mx_edi_is_required())
        message = invoices.l10n_mx_edi_cancellation_messages().get('to_cancel')
        for inv in invoices:
            inv.message_post(body=message)
        invoices.with_context(called_from_cron=True).l10n_mx_edi_cancellation()

    def l10n_mx_edi_action_cancel_signed_sat(self):
        """Searches all the invoices canceled in Odoo, but valid in the SAT
        system and return to open in Odoo."""
        invoices = self.search([
            ('state', '=', 'cancel'), '|',
            ('l10n_mx_edi_pac_status', '=', 'signed'),
            ('l10n_mx_edi_sat_status', '=', 'valid')]).filtered(
                lambda inv: inv.l10n_mx_edi_is_required())
        invoices.l10n_mx_edi_update_sat_status()
        messages = invoices.l10n_mx_edi_cancellation_messages()
        for inv in invoices.filtered(lambda i: i.l10n_mx_edi_sat_status == 'valid'):
            inv.reversed_entry_id.button_cancel()
            inv.message_post(body=messages.get('revert'))

    def l10n_mx_edi_action_revert_cancellation(self):
        """Used when the customer do not approve the cancellation"""
        for inv in self.filtered(lambda i: i.l10n_mx_edi_is_required() and
                                 i.l10n_mx_edi_pac_status in ['to_cancel', 'cancelled']):
            inv.l10n_mx_edi_update_sat_status()
            if inv.l10n_mx_edi_sat_status == 'valid':
                inv.write({'l10n_mx_edi_pac_status': 'signed'})

    @api.model
    def l10n_mx_edi_cancellation_messages(self):
        """Method to return the cancellation messages, is called from a cron
        because the cron labels cannot be translated and that take the user
        language"""
        return {
            'to_open': _(
                'This invoice was returned to open because the CFDI is signed '
                'in the SAT system.'),
            'revert': _(
                'The reverted move in the journal entry of this invoice was '
                'cancelled because the CFDI is signed in the SAT system.'),
            'to_cancel': _(
                'This invoice already was cancelled in the SAT, now will try '
                'to cancel in Odoo.'),
        }

    @api.model
    def _l10n_mx_edi_get_timezone(self, state):
        # northwest area
        if state == 'BCN':
            return timezone('America/Tijuana')
        # Southeast area
        elif state == 'ROO':
            return timezone('America/Cancun')
        # Pacific area
        elif state in ('BCS', 'CHH', 'SIN', 'NAY'):
            return timezone('America/Chihuahua')
        # Sonora
        elif state == 'SON':
            return timezone('America/Hermosillo')
        # By default, takes the central area timezone
        return timezone('America/Mexico_City')
