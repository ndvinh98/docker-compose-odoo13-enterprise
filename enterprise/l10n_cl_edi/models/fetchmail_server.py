# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import email
import logging
import os

from lxml import etree

from odoo.tests import Form
from xmlrpc import client as xmlrpclib

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

XML_NAMESPACES = {
    'ns0': 'http://www.sii.cl/SiiDte',
    'ns1': 'http://www.w3.org/2000/09/xmldsig#',
    'xml_schema': 'http://www.sii.cl/XMLSchema'
}

DEFAULT_DOC_NUMBER_PADDING = 6


class FetchmailServer(models.Model):
    _name = 'fetchmail.server'
    _inherit = 'fetchmail.server'

    l10n_cl_is_dte = fields.Boolean(
        'DTE server', help='By checking this option, this email account will be used to receive the electronic\n'
                           'invoices from the suppliers, and communications from the SII regarding the electronic\n'
                           'invoices issued. In this case, this email should match both emails declared on the SII\n'
                           'site in the section: "ACTUALIZACION DE DATOS DEL CONTRIBUYENTE", "Mail Contacto SII"\n'
                           'and "Mail Contacto Empresas".')
    l10n_cl_last_uid = fields.Integer(
        string='Last message UID', default=1,
        help='This value is pointing to the number of the last message unread by odoo '
             'in the inbox. This value will be updated by the system during its normal'
             'operation.')

    @api.constrains('l10n_cl_is_dte', 'server_type')
    def _check_server_type(self):
        for record in self:
            if record.l10n_cl_is_dte and record.server_type != 'imap':
                raise ValidationError(_('The server must be of type IMAP.'))

    def fetch_mail(self):
        for server in self.filtered(lambda s: s.l10n_cl_is_dte):
            _logger.info('Start checking for new emails on %s IMAP server %s', server.server_type, server.name)

            count, failed = 0, 0
            imap_server = None
            try:
                imap_server = server.connect()
                imap_server.select()

                result, data = imap_server.uid('search', None, '(UID %s:*)' % server.l10n_cl_last_uid)
                new_max_uid = server.l10n_cl_last_uid
                for uid in data[0].split():
                    if int(uid) <= server.l10n_cl_last_uid:
                        # We get always minimum 1 message.  If no new message, we receive the newest already managed.
                        continue

                    result, data = imap_server.uid('fetch', uid, '(RFC822)')

                    if not data[0]:
                        continue
                    message = data[0][1]

                    # To leave the mail in the state in which they were.
                    if 'Seen' not in data[1].decode('UTF-8'):
                        imap_server.uid('STORE', uid, '+FLAGS', '\\Seen')
                    else:
                        imap_server.uid('STORE', uid, '-FLAGS', '\\Seen')

                    # See details in message_process() in mail_thread.py
                    if isinstance(message, xmlrpclib.Binary):
                        message = bytes(message.data)
                    if isinstance(message, str):
                        message = message.encode('utf-8')
                    msg_txt = email.message_from_bytes(message)
                    try:
                        self._process_incoming_email(msg_txt)
                        new_max_uid = max(new_max_uid, int(uid))
                        self._cr.commit()
                    except Exception:
                        _logger.info('Failed to process mail %s from %s server %s.', server.server_type, server.name,
                                     exc_info=True)
                        failed += 1
                    count += 1
                server.write({'l10n_cl_last_uid': new_max_uid})
                _logger.info('Fetched %d email(s) on %s server %s; %d succeeded, %d failed.', count, server.server_type,
                             server.name, (count - failed), failed)
            except Exception:
                _logger.info('General failure when trying to fetch mail from %s server %s.', server.server_type,
                             server.name, exc_info=True)
            finally:
                if imap_server:
                    imap_server.close()
                    imap_server.logout()
                server.write({'date': fields.Datetime.now()})
        return super(FetchmailServer, self.filtered(lambda s: not s.l10n_cl_is_dte)).fetch_mail()

    def _process_incoming_email(self, msg_txt):
        parsed_values = self.env['mail.thread']._message_parse_extract_payload(msg_txt)
        body, attachments = parsed_values['body'], parsed_values['attachments']
        from_address = tools.decode_smtp_header(msg_txt.get('from'))
        for attachment in attachments:
            _logger.info('Processing attachment %s' % attachment.fname)
            attachment_ext = os.path.splitext(attachment.fname)[1]
            if attachment_ext != '.xml' or not self._is_dte_email(attachment.content):
                _logger.info('Attachment %s has been discarded! It is not a xml file or is not a DTE email' %
                             attachment.fname)
                continue
            xml_content = etree.fromstring(attachment.content)
            origin_type = self._get_xml_origin_type(xml_content)
            if origin_type == 'not_classified':
                _logger.info('Attachment %s has been discarded! Origin type: %s' % (attachment.fname, origin_type))
                continue
            company = self._get_dte_recipient_company(xml_content, origin_type)
            if not company or not self._is_dte_enabled_company(company):
                _logger.info('Attachment %s has been discarded! It is not a valid company (id: %s)' % (
                    attachment.fname, company.id))
                continue
            self._process_attachment_content(attachment.content, attachment.fname, from_address, origin_type,
                                             company.id)

    def _process_attachment_content(self, att_content, att_name, from_address, origin_type, company_id):
        """
        This could be called from a button if there is a need to be processed manually
        """
        if origin_type == 'incoming_supplier_document':
            for move in self._create_invoice_from_attachment(att_content, att_name, from_address, company_id):
                if move.partner_id:
                    try:
                        move._l10n_cl_send_receipt_acknowledgment()
                    except Exception as error:
                        move.message_post(body=error)
        elif origin_type == 'incoming_sii_dte_result':
            self._process_incoming_sii_dte_result(att_content)
        elif origin_type in ['incoming_acknowledge', 'incoming_commercial_accept', 'incoming_commercial_reject']:
            self._process_incoming_customer_claim(company_id, att_content, att_name, origin_type)

    def _process_incoming_sii_dte_result(self, att_content):
        xml_content = etree.fromstring(att_content)
        track_id = xml_content.findtext('.//TRACKID').zfill(10)
        moves = self.env['account.move'].search([('l10n_cl_sii_send_ident', '=', track_id)])
        status = xml_content.findtext('IDENTIFICACION/ESTADO')
        error_status = xml_content.findtext('REVISIONENVIO/REVISIONDTE/ESTADO')
        if error_status is not None:
            msg = _('Incoming SII DTE result:<br/> '
                    '<li><b>ESTADO</b>: %s</li>'
                    '<li><b>REVISIONDTE/ESTADO</b>: %s</li>'
                    '<li><b>REVISIONDTE/DETALLE</b>: %s</li>') % (
                      status, error_status, xml_content.findtext('REVISIONENVIO/REVISIONDTE/DETALLE'))
        else:
            msg = _('Incoming SII DTE result:<br/><li><b>ESTADO</b>: %s</li>') % status
        for move in moves:
            move.message_post(body=msg)

    def _process_incoming_customer_claim(self, company_id, att_content, att_name, origin_type):
        dte_tag = 'RecepcionDTE' if origin_type == 'incoming_acknowledge' else 'ResultadoDTE'
        xml_content = etree.fromstring(att_content)
        for dte in xml_content.xpath('//ns0:%s' % dte_tag, namespaces=XML_NAMESPACES):
            document_number = self._get_document_number(dte)
            issuer_vat = self._get_dte_issuer_vat(dte)
            partner = self._get_partner(issuer_vat)
            if not partner:
                _logger.error('Partner for incoming customer claim has not been found for %s' % issuer_vat)
                continue
            document_type_code = self._get_document_type_from_xml(dte)
            document_type = self.env['l10n_latam.document.type'].search(
                [('code', '=', document_type_code)], limit=1)
            zfill = self._get_doc_number_padding(company_id)
            name = '{} {}'.format(document_type.doc_code_prefix, document_number.zfill(zfill))
            move = self.env['account.move'].sudo().search([
                ('partner_id', '=', partner.id),
                ('type', 'in', ['out_invoice', 'out_refund']),
                ('l10n_latam_document_type_id', '=', document_type.id),
                ('l10n_cl_dte_status', '=', 'accepted'),
                ('name', '=', name),
                ('company_id', '=', company_id)
            ], limit=1)
            if not move:
                _logger.error('Move not found with partner: %s, name: %s, l10n_latam_document_type: %s, '
                              'company_id: %s' % (partner.id, name, document_type.id, company_id))
                continue
            status = {'incoming_acknowledge': 'received', 'incoming_commercial_accept': 'accepted'}.get(
                origin_type, 'claimed')
            move.write({'l10n_cl_dte_acceptation_status': status})
            move.with_context(no_new_invoice=True).message_post(
                body=_('DTE reception status established as <b>%s</b> by incoming email') % status,
                attachments=[(att_name, att_content)])

    def _check_document_number_exists(self, partner_id, document_number, document_type, company_id):
        name = '{} {}'.format(document_type.doc_code_prefix, document_number)
        return self.env['account.move'].sudo().search_count(
            [('type', 'in', ['in_invoice', 'in_refund']), ('name', '=', name), ('partner_id', '=', partner_id),
             ('company_id', '=', company_id)]) > 0

    def _create_invoice_from_attachment(self, att_content, att_name, from_address, company_id):
        moves = []
        xml_content = etree.fromstring(att_content)
        for dte_xml in xml_content.xpath('//ns0:DTE', namespaces=XML_NAMESPACES):
            document_number = self._get_document_number(dte_xml)
            document_type_code = self._get_document_type_from_xml(dte_xml)
            document_type = self.env['l10n_latam.document.type'].search([('code', '=', document_type_code)], limit=1)
            if not document_type:
                _logger.info('DTE has been discarded! Document type %s not found' % document_type_code)
                continue
            if document_type and document_type.internal_type not in ['invoice', 'debit_note', 'credit_note']:
                _logger.info('DTE has been discarded! The document type %s is not a vendor bill' % document_type_code)
                continue

            partner = self._get_partner(self._get_dte_issuer_vat(dte_xml))
            if partner and self._check_document_number_exists(partner.id, document_number, document_type, company_id):
                _logger.info('E-invoice already exist: %s', document_number)
                continue

            default_type = 'in_invoice' if document_type_code != '61' else 'in_refund'
            msgs = []
            try:
                invoice_form, msgs = self._get_invoice_form(
                    company_id, partner, default_type, from_address, dte_xml, document_number, document_type, msgs)

            except Exception as error:
                _logger.info(error)
                with Form(self.env['account.move'].with_context(
                        default_type=default_type, allowed_company_ids=[company_id])) as invoice_form:
                    msgs.append(error)
                    invoice_form.partner_id = partner
                    invoice_form.l10n_latam_document_number = document_number
                    invoice_form.l10n_latam_document_type_id = document_type

            move = invoice_form.save()

            dte_attachment = self.env['ir.attachment'].create({
                'name': 'DTE_{}.xml'.format(document_number),
                'res_model': self._name,
                'res_id': move.id,
                'type': 'binary',
                'datas': base64.b64encode(etree.tostring(dte_xml))
            })
            move.l10n_cl_dte_file = dte_attachment.id

            for msg in msgs:
                move.with_context(no_new_invoice=True).message_post(body=msg)

            msg = _('Vendor Bill DTE has been generated for the following vendor: </br>') if partner else \
                  _('Vendor not found: You can generate this vendor manually with the following information: </br>')
            move.with_context(no_new_invoice=True).message_post(
                body=msg + _(
                    '<li><b>Name</b>: %(name)s</li><li><b>RUT</b>: %(vat)s</li><li>'
                    '<b>Address</b>: %(address)s</li>') % {
                    'vat': self._get_dte_issuer_vat(xml_content) or '',
                    'name': self._get_dte_partner_name(xml_content) or '',
                    'address': self._get_dte_issuer_address(xml_content) or ''}, attachment_ids=[dte_attachment.id])

            move.l10n_cl_dte_acceptation_status = 'received'
            moves.append(move)
            _logger.info(_('New move has been created from DTE %s with id: %s') % (att_name, move.id))
        return moves

    def _get_invoice_form(self, company_id, partner, default_type, from_address, dte_xml, document_number,
                          document_type, msgs):
        """
        This method creates a draft vendor bill from the attached xml in the incoming email.
        """
        with Form(self.env['account.move'].with_context(
                default_type=default_type, allowed_company_ids=[company_id])) as invoice_form:
            invoice_form.partner_id = partner
            invoice_form.invoice_source_email = from_address

            invoice_date = dte_xml.findtext('.//ns0:FchEmis', namespaces=XML_NAMESPACES)
            if invoice_date is not None:
                invoice_form.invoice_date = fields.Date.from_string(invoice_date)
            # Set the date after invoice_date to avoid the onchange
            invoice_form.date = fields.Date.context_today(
                self.with_context(tz='America/Santiago'))

            invoice_date_due = dte_xml.findtext('.//ns0:FchVenc', namespaces=XML_NAMESPACES)
            if invoice_date_due is not None:
                invoice_form.invoice_date_due = fields.Date.from_string(invoice_date_due)

            journal = self._get_dte_purchase_journal(company_id)
            if journal:
                invoice_form.journal_id = journal

            currency = self._get_dte_currency(dte_xml)
            if currency:
                invoice_form.currency_id = currency

            invoice_form.l10n_latam_document_number = document_number
            invoice_form.l10n_latam_document_type_id = document_type

            for invoice_line in self._get_dte_lines(dte_xml, company_id, partner.id):
                with invoice_form.invoice_line_ids.new() as invoice_line_form:
                    invoice_line_form.product_id = invoice_line.get('product', False)
                    invoice_line_form.name = invoice_line.get('name')
                    invoice_line_form.quantity = invoice_line.get('quantity')
                    invoice_line_form.price_unit = invoice_line.get('price_unit')
                    invoice_line_form.discount = invoice_line.get('discount', 0)

                    if not invoice_line.get('default_tax'):
                        invoice_line_form.tax_ids.clear()
                    for tax in invoice_line.get('taxes', []):
                        invoice_line_form.tax_ids.add(tax)

            for reference_line in self._get_invoice_references(dte_xml):
                if not self._is_valid_reference_doc_type(
                        reference_line.get('l10n_cl_reference_doc_type_selection')):
                    msgs.append(_('There is an unidentified reference in this invoice:<br/>'
                                  '<li>Origin: %(origin_doc_number)s<li/>'
                                  '<li>Reference Code: %(reference_doc_code)s<li/>'
                                  '<li>Doc Type: %(l10n_cl_reference_doc_type_selection)s<li/>'
                                  '<li>Reason: %(reason)s<li/>'
                                  '<li>Date:%(date)s') % reference_line)
                    continue
                with invoice_form.l10n_cl_reference_ids.new() as reference_line_form:
                    reference_line_form.origin_doc_number = reference_line['origin_doc_number']
                    reference_line_form.reference_doc_code = reference_line['reference_doc_code']
                    reference_line_form.l10n_cl_reference_doc_type_selection = reference_line[
                        'l10n_cl_reference_doc_type_selection']
                    reference_line_form.reason = reference_line['reason']
                    reference_line_form.date = reference_line['date']

        return invoice_form, msgs

    def _is_dte_email(self, attachment_content):
        return b'http://www.sii.cl/SiiDte' in attachment_content or b'<RESULTADO_ENVIO>' in attachment_content

    def _get_dte_recipient_company(self, xml_content, origin_type):
        xml_tag_by_type = {
            'incoming_supplier_document': '//ns0:RutReceptor',
            'incoming_sii_dte_result': '//RUTEMISOR',
            'incoming_acknowledge': '//ns0:RutRecibe',
            'incoming_commercial_accept': '//ns0:RutRecibe',
            'incoming_commercial_reject': '//ns0:RutRecibe',
        }
        receiver_rut = xml_content.xpath(
            xml_tag_by_type.get(origin_type), namespaces=XML_NAMESPACES)
        if not receiver_rut:
            return None
        return self.env['res.company'].sudo().search([('vat', '=', receiver_rut[0].text)])

    def _is_dte_enabled_company(self, company):
        return False if not company.l10n_cl_dte_service_provider else True

    def _get_xml_origin_type(self, xml_content):
        tag = etree.QName(xml_content.tag).localname
        if tag == 'EnvioDTE':
            return 'incoming_supplier_document'
        if tag == 'RespuestaDTE':
            if xml_content.findtext('.//ns0:EstadoRecepDTE', namespaces=XML_NAMESPACES) == '0':
                return 'incoming_acknowledge'
            if xml_content.findtext('.//ns0:EstadoDTE', namespaces=XML_NAMESPACES) == '0':
                return 'incoming_commercial_accept'
            return 'incoming_commercial_reject'
        if tag == 'RESULTADO_ENVIO':
            return 'incoming_sii_dte_result'
        return 'not_classified'

    def _get_partner(self, partner_rut):
        return self.env['res.partner'].search([('vat', '=', partner_rut)], limit=1)

    def _get_dte_issuer_vat(self, xml_content):
        return (xml_content.findtext('.//ns0:RUTEmisor', namespaces=XML_NAMESPACES).upper() or
                xml_content.findtext('.//ns0:RutEmisor', namespaces=XML_NAMESPACES).upper())

    def _get_dte_partner_name(self, xml_content):
        return xml_content.findtext('.//ns0:RznSoc', namespaces=XML_NAMESPACES)

    def _get_dte_issuer_address(self, xml_content):
        return xml_content.findtext('.//ns0:DirOrigen', default='', namespaces=XML_NAMESPACES)

    def _get_dte_purchase_journal(self, company_id):
        return self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('l10n_latam_use_documents', '=', True),
            ('company_id', '=', company_id)
        ], limit=1)

    def _get_document_number(self, xml_content):
        return xml_content.findtext('.//ns0:Folio', namespaces=XML_NAMESPACES)

    def _get_document_type_from_xml(self, xml_content):
        return xml_content.findtext('.//ns0:TipoDTE', namespaces=XML_NAMESPACES)

    def _get_doc_number_padding(self, company_id):
        """Returns the document number padding used to create the name of the account move"""
        move = self.env['account.move'].sudo().search([
            ('company_id', '=', company_id)], order='create_date desc', limit=1)
        if not move:
            return DEFAULT_DOC_NUMBER_PADDING
        doc_number = move.name.split(' ')[1]
        return len(doc_number)

    def _use_default_tax(self, dte_xml):
        """We use the default tax if the DTE has the tag TasaIVA"""
        return dte_xml.findtext('.//ns0:TasaIVA', namespaces=XML_NAMESPACES) is not None

    def _get_withholding_taxes(self, company_id, dte_line):
        # Get withholding taxes from DTE line
        tax_codes = [int(element.text) for element in dte_line.findall('.//ns0:CodImpAdic', namespaces=XML_NAMESPACES)]
        return set(self.env['account.tax'].with_context(allowed_company_ids=[company_id]).search([
            ('company_id', '=', company_id),
            ('type_tax_use', '=', 'purchase'),
            ('l10n_cl_sii_code', 'in', tax_codes)
        ]))

    def _get_dte_currency(self, dte_xml):
        currency_name = dte_xml.findtext('.//ns0:Moneda', namespaces=XML_NAMESPACES)
        if currency_name is None:  # If the currency of the DTE is CLP then the tag doesn't exist
            currency_name = 'CLP'
        return self.env['res.currency'].with_context(active_test=False).search([('name', '=', currency_name)])

    def _get_vendor_product(self, product_code, product_name, company_id, partner_id):
        """
        This tries to match products specified in the vendor bill with current products in database.
        Criteria to attempt a match with existent products:
        1) check if product_code in the supplier info is present (if partner_id is established)
        2) if (1) fails, check if product supplier info name is present (if partner_id is established)
        3) if (1) and (2) fail, check product default_code
        4) if 3 previous criteria fail, check product name, and return false if fails
        """
        if partner_id:
            supplier_info_domain = [('name', '=', partner_id), ('company_id', 'in', [company_id, False])]
            if product_code:
                # 1st criteria
                supplier_info_domain.append(('product_code', '=', product_code))
            else:
                # 2nd criteria
                supplier_info_domain.append(('product_name', '=', product_name))
            supplier_info = self.env['product.supplierinfo'].sudo().search(supplier_info_domain, limit=1)
            if supplier_info:
                return supplier_info.product_id
        # 3rd criteria
        if product_code:
            product = self.env['product.product'].sudo().search([
                '|', ('default_code', '=', product_code), ('barcode', '=', product_code),
                ('company_id', 'in', [company_id, False]), ], limit=1)
            if product:
                return product
        # 4th criteria
        return self.env['product.product'].sudo().search([
            ('company_id', 'in', [company_id, False]), ('name', 'ilike', product_name)], limit=1)

    def _get_dte_lines(self, dte_xml, company_id, partner_id):
        """
        This parse DTE invoice detail lines and tries to match lines with existing products.
        If no products are found, it puts only the description of the products in the draft invoice lines
        """
        invoice_lines = []
        for dte_line in dte_xml.findall('.//ns0:Detalle', namespaces=XML_NAMESPACES):
            product_code = dte_line.findtext('.//ns0:VlrCodigo', namespaces=XML_NAMESPACES)
            product_name = dte_line.findtext('.//ns0:NmbItem', namespaces=XML_NAMESPACES)
            product = self._get_vendor_product(product_code, product_name, company_id, partner_id)
            # the QtyItem tag is not mandatory in certain cases (case 2 in documentation).
            # Should be set to 1 if not present.
            # See http://www.sii.cl/factura_electronica/formato_dte.pdf row 15 and row 22 of tag table
            quantity = float(dte_line.findtext('.//ns0:QtyItem', default=1, namespaces=XML_NAMESPACES))
            # in the same case, PrcItem is not mandatory if QtyItem is not present, but MontoItem IS mandatory
            # this happens whenever QtyItem is not present in the invoice.
            # See http://www.sii.cl/factura_electronica/formato_dte.pdf row 38 of tag table.
            price_unit = float(dte_line.findtext(
                './/ns0:PrcItem', default=dte_line.findtext('.//ns0:MontoItem', namespaces=XML_NAMESPACES),
                namespaces=XML_NAMESPACES))
            values = {
                'product': product,
                'name': product.name if product else dte_line.findtext('.//ns0:NmbItem', namespaces=XML_NAMESPACES),
                'quantity': quantity,
                'price_unit': price_unit,
                'discount': float(dte_line.findtext('.//ns0:DescuentoPct', default=0, namespaces=XML_NAMESPACES)),
                'default_tax': False
            }
            if dte_xml.findtext('.//ns0:TasaIVA', namespaces=XML_NAMESPACES) is not None:
                values['default_tax'] = True
                values['taxes'] = self._get_withholding_taxes(company_id, dte_line)
            invoice_lines.append(values)

        for desc_rcg_global in dte_xml.findall('.//ns0:DscRcgGlobal', namespaces=XML_NAMESPACES):
            line_type = desc_rcg_global.findtext('.//ns0:TpoMov', namespaces=XML_NAMESPACES)
            price_type = desc_rcg_global.findtext('.//ns0:TpoValor', namespaces=XML_NAMESPACES)
            valor_dr = (desc_rcg_global.findtext('.//ns0:ValorDROtrMnda', namespaces=XML_NAMESPACES) or
                        desc_rcg_global.findtext('.//ns0:ValorDR', namespaces=XML_NAMESPACES))
            values = {
                'name': 'DESCUENTO' if line_type == 'D' else 'RECARGO',
                'quantity': 1,
            }
            amount_dr = float(valor_dr)
            # The price unit of a discount line should be negative while surcharge should be positive
            price_unit_multiplier = 1 if line_type == 'D' else -1
            if price_type == '%':
                inde_exe_dr = desc_rcg_global.findtext('.//ns0:IndExeDR', namespaces=XML_NAMESPACES)
                if inde_exe_dr is None:  # Applied to items with tax
                    dte_amount_tag = (dte_xml.findtext('.//ns0:MntNetoOtrMnda', namespaces=XML_NAMESPACES) or
                                      dte_xml.findtext('.//ns0:MntNeto', namespaces=XML_NAMESPACES))
                    tax_amount_tag = dte_xml.findtext('.//ns0:IVA', namespaces=XML_NAMESPACES)
                    dte_amount = dte_amount_tag is not None and int(dte_amount_tag) or 0
                    tax_amount = tax_amount_tag is not None and int(tax_amount_tag) or 0
                    values['price_unit'] = round(sum([
                        dte_amount - (dte_amount / (1 - amount_dr / 100)),
                        tax_amount - (tax_amount / (1 - amount_dr / 100))
                    ])) * price_unit_multiplier
                elif inde_exe_dr == '2':  # Applied to items not billable
                    dte_amount_tag = dte_xml.findtext('.//ns0:MontoNF', namespaces=XML_NAMESPACES)
                    dte_amount = dte_amount_tag is not None and int(dte_amount_tag) or 0
                    values['price_unit'] = round(
                        dte_amount - (int(dte_amount) / (1 - amount_dr / 100))) * price_unit_multiplier
                elif inde_exe_dr == '1':  # Applied to items without taxes
                    dte_amount_tag = (dte_xml.findtext('.//ns0:MntExeOtrMnda', namespaces=XML_NAMESPACES) or
                                      dte_xml.findtext('.//ns0:MntExe', namespaces=XML_NAMESPACES))
                    dte_amount = dte_amount_tag is not None and int(dte_amount_tag) or 0
                    values['price_unit'] = round(
                        dte_amount - (int(dte_amount) / (1 - amount_dr / 100))) * price_unit_multiplier
            else:
                values['price_unit'] = amount_dr * -1 * price_unit_multiplier
                if not desc_rcg_global.findtext('.//ns0:IndExeDR', namespaces=XML_NAMESPACES) == '1':
                    values['default_tax'] = self._use_default_tax(dte_xml)
            invoice_lines.append(values)
        return invoice_lines

    def _is_valid_reference_doc_type(self, reference_doc_type):
        reference_codes = [item[0] for item in self.env['l10n_cl.account.invoice.reference']._fields[
            'l10n_cl_reference_doc_type_selection'].selection]
        return reference_doc_type in reference_codes

    def _get_invoice_references(self, dte_xml):
        invoice_reference_ids = []
        for reference in dte_xml.findall('.//ns0:Referencia', namespaces=XML_NAMESPACES):
            invoice_reference_ids.append({
                'origin_doc_number': reference.findtext('.//ns0:FolioRef', namespaces=XML_NAMESPACES),
                'reference_doc_code': reference.findtext('.//ns0:CodRef', namespaces=XML_NAMESPACES),
                'l10n_cl_reference_doc_type_selection': reference.findtext('.//ns0:TpoDocRef',
                                                                           namespaces=XML_NAMESPACES),
                'reason': reference.findtext('.//ns0:RazonRef', namespaces=XML_NAMESPACES),
                'date': reference.findtext('.//ns0:FchRef', namespaces=XML_NAMESPACES),
            })
        return invoice_reference_ids
