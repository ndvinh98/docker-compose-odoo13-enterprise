# -*- coding: utf-8 -*-

from odoo.addons.iap import jsonrpc
from odoo import api, exceptions, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import Form
from odoo.tools.misc import clean_context
import logging
import re
import json

_logger = logging.getLogger(__name__)

PARTNER_AUTOCOMPLETE_ENDPOINT = 'https://partner-autocomplete.odoo.com'
EXTRACT_ENDPOINT = 'https://iap-extract.odoo.com'
CLIENT_OCR_VERSION = 120

# list of result id that can be sent by iap-extract
SUCCESS = 0
NOT_READY = 1
ERROR_INTERNAL = 2
ERROR_NOT_ENOUGH_CREDIT = 3
ERROR_DOCUMENT_NOT_FOUND = 4
ERROR_NO_DOCUMENT_NAME = 5
ERROR_UNSUPPORTED_IMAGE_FORMAT = 6
ERROR_FILE_NAMES_NOT_MATCHING = 7
ERROR_NO_CONNECTION = 8
ERROR_SERVER_IN_MAINTENANCE = 9
ERROR_PASSWORD_PROTECTED = 10
ERROR_TOO_MANY_PAGES = 11

# codes 100-199 are reserved for warnings
WARNING_DUPLICATE_VENDOR_REFERENCE = 100

ERROR_MESSAGES = {
    ERROR_INTERNAL: _("An error occurred"),
    ERROR_DOCUMENT_NOT_FOUND: _("The document could not be found"),
    ERROR_NO_DOCUMENT_NAME: _("No document name provided"),
    ERROR_UNSUPPORTED_IMAGE_FORMAT: _("Unsupported image format"),
    ERROR_FILE_NAMES_NOT_MATCHING: _("You must send the same quantity of documents and file names"),
    ERROR_NO_CONNECTION: _("Server not available. Please retry later"),
    ERROR_SERVER_IN_MAINTENANCE: _("Server is currently under maintenance. Please retry later"),
    ERROR_PASSWORD_PROTECTED: _("Your PDF file is protected by a password. The OCR can't extract data from it"),
    ERROR_TOO_MANY_PAGES: _("Your invoice is too heavy to be processed by the OCR. Try to reduce the number of pages and avoid pages with too many text"),
    WARNING_DUPLICATE_VENDOR_REFERENCE: _("Warning: there is already a vendor bill with this reference (%s)")
}


class AccountInvoiceExtractionWords(models.Model):
    _name = "account.invoice_extract.words"
    _description = "Extracted words from invoice scan"

    invoice_id = fields.Many2one("account.move", help="Invoice id")
    field = fields.Char()
    selected_status = fields.Integer("Invoice extract selected status.",
                                     help="0 for 'not selected', 1 for 'ocr selected with no user selection' and 2 for 'ocr selected with user selection (user may have selected the same box)")
    user_selected = fields.Boolean()
    word_text = fields.Char()
    word_page = fields.Integer()
    word_box_midX = fields.Float()
    word_box_midY = fields.Float()
    word_box_width = fields.Float()
    word_box_height = fields.Float()
    word_box_angle = fields.Float()


class AccountMove(models.Model):
    _inherit = ['account.move']
    duplicated_vendor_ref = fields.Char(string='Duplicated vendor reference')

    @api.depends('extract_status_code')
    def _compute_error_message(self):
        for record in self:
            if record.extract_status_code not in (SUCCESS, NOT_READY):
                record.extract_error_message = ERROR_MESSAGES.get(record.extract_status_code, ERROR_MESSAGES[ERROR_INTERNAL])
                if record.extract_status_code == WARNING_DUPLICATE_VENDOR_REFERENCE:
                    record.extract_error_message = record.extract_error_message % record.duplicated_vendor_ref
            else:
                record.extract_error_message = ''

    def _compute_can_show_send_resend(self, record):
        can_show = True
        if record.company_id.extract_show_ocr_option_selection == 'no_send':
            can_show = False
        if record.state != 'draft':
            can_show = False
        if record.type in ('out_invoice', 'out_refund'):
            can_show = False
        if record.message_main_attachment_id is None or len(record.message_main_attachment_id) == 0:
            can_show = False
        return can_show

    @api.depends('state', 'extract_state', 'message_main_attachment_id')
    def _compute_show_resend_button(self):
        for record in self:
            record.extract_can_show_resend_button = self._compute_can_show_send_resend(record)
            if record.extract_state not in ['error_status', 'not_enough_credit', 'module_not_up_to_date']:
                record.extract_can_show_resend_button = False

    @api.depends('state', 'extract_state', 'message_main_attachment_id')
    def _compute_show_send_button(self):
        for record in self:
            record.extract_can_show_send_button = self._compute_can_show_send_resend(record)
            if record.extract_state not in ['no_extract_requested']:
                record.extract_can_show_send_button = False

    extract_state = fields.Selection([('no_extract_requested', 'No extract requested'),
                                      ('not_enough_credit', 'Not enough credit'),
                                      ('error_status', 'An error occurred'),
                                      ('waiting_extraction', 'Waiting extraction'),
                                      ('extract_not_ready', 'waiting extraction, but it is not ready'),
                                      ('waiting_validation', 'Waiting validation'),
                                      ('done', 'Completed flow')],
                                     'Extract state', default='no_extract_requested', required=True, copy=False)
    extract_status_code = fields.Integer("Status code", copy=False)
    extract_error_message = fields.Text("Error message", compute=_compute_error_message)
    extract_remote_id = fields.Integer("Id of the request to IAP-OCR", default="-1", help="Invoice extract id", copy=False, readonly=True)
    extract_word_ids = fields.One2many("account.invoice_extract.words", inverse_name="invoice_id", copy=False)

    extract_can_show_resend_button = fields.Boolean("Can show the ocr resend button", compute=_compute_show_resend_button)
    extract_can_show_send_button = fields.Boolean("Can show the ocr send button", compute=_compute_show_send_button)

    @api.model
    def _contact_iap_extract(self, local_endpoint, params):
        params['version'] = CLIENT_OCR_VERSION
        endpoint = self.env['ir.config_parameter'].sudo().get_param('account_invoice_extract_endpoint', EXTRACT_ENDPOINT)
        return jsonrpc(endpoint + local_endpoint, params=params)

    @api.model
    def _contact_iap_partner_autocomplete(self, local_endpoint, params):
        return jsonrpc(PARTNER_AUTOCOMPLETE_ENDPOINT + local_endpoint, params=params)

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        """When a message is posted on an account.move, send the attachment to iap-ocr if
        the res_config is on "auto_send" and if this is the first attachment."""
        message = super(AccountMove, self).message_post(**kwargs)
        if self.company_id.extract_show_ocr_option_selection == 'auto_send':
            for record in self:
                if record.type in ['in_invoice', 'in_refund'] and record.extract_state == "no_extract_requested":
                    record.retry_ocr()
        return message

    def retry_ocr(self):
        """Retry to contact iap to submit the first attachment in the chatter"""
        if self.company_id.extract_show_ocr_option_selection == 'no_send':
            return False
        attachments = self.message_main_attachment_id
        if attachments and attachments.exists() and self.type in ['in_invoice', 'in_refund'] and self.extract_state in ['no_extract_requested', 'not_enough_credit', 'error_status', 'module_not_up_to_date']:
            account_token = self.env['iap.account'].get('invoice_ocr')
            user_infos = {
                'user_company_VAT': self.company_id.vat,
                'user_company_name': self.company_id.name,
                'user_company_country_code': self.company_id.country_id.code,
                'user_lang': self.env.user.lang,
                'user_email': self.env.user.email,
            }
            #this line contact iap to create account if this is the first request. This allow iap to give free credits if the database is elligible
            self.env['iap.account'].get_credits('invoice_ocr')
            params = {
                'account_token': account_token.account_token,
                'dbuuid': self.env['ir.config_parameter'].sudo().get_param('database.uuid'),
                'documents': [x.datas.decode('utf-8') for x in attachments],
                'file_names': [x.name for x in attachments],
                'user_infos': user_infos,
            }
            try:
                result = self._contact_iap_extract('/iap/invoice_extract/parse', params)
                self.extract_status_code = result['status_code']
                if result['status_code'] == SUCCESS:
                    if self.env['ir.config_parameter'].sudo().get_param("account_invoice_extract.already_notified", True):
                        self.env['ir.config_parameter'].sudo().set_param("account_invoice_extract.already_notified", False)
                    self.extract_state = 'waiting_extraction'
                    self.extract_remote_id = result['document_id']
                elif result['status_code'] == ERROR_NOT_ENOUGH_CREDIT:
                    self.send_no_credit_notification()
                    self.extract_state = 'not_enough_credit'
                else:
                    self.extract_state = 'error_status'
                    _logger.warning('There was an issue while doing the OCR operation on this file. Error: -1')

            except AccessError:
                self.extract_state = 'error_status'
                self.extract_status_code = ERROR_NO_CONNECTION

    def send_no_credit_notification(self):
        """
        Notify about the number of credit.
        In order to avoid to spam people each hour, an ir.config_parameter is set
        """
        #If we don't find the config parameter, we consider it True, because we don't want to notify if no credits has been bought earlier.
        already_notified = self.env['ir.config_parameter'].sudo().get_param("account_invoice_extract.already_notified", True)
        if already_notified:
            return
        try:
            mail_template = self.env.ref('account_invoice_extract.account_invoice_extract_no_credit')
        except ValueError:
            #if the mail template has not been created by an upgrade of the module
            return
        iap_account = self.env['iap.account'].search([('service_name', '=', "invoice_ocr")], limit=1)
        if iap_account:
            # Get the email address of the creators of the records
            res = self.env['res.users'].search_read([('id', '=', 2)], ['email'])
            if res:
                email_values = {
                    'email_to': res[0]['email']
                }
                mail_template.send_mail(iap_account.id, force_send=True, email_values=email_values)
                self.env['ir.config_parameter'].sudo().set_param("account_invoice_extract.already_notified", True)

    def get_validation(self, field):
        """
        return the text or box corresponding to the choice of the user.
        If the user selected a box on the document, we return this box,
        but if he entered the text of the field manually, we return only the text, as we
        don't know which box is the right one (if it exists)
        """
        selected = self.env["account.invoice_extract.words"].search([("invoice_id", "=", self.id), ("field", "=", field), ("user_selected", "=", True)])
        if not selected.exists():
            selected = self.env["account.invoice_extract.words"].search([("invoice_id", "=", self.id), ("field", "=", field), ("selected_status", "=", 1)], limit=1)
        return_box = {}
        if selected.exists():
            return_box["box"] = [selected.word_text, selected.word_page, selected.word_box_midX,
                                 selected.word_box_midY, selected.word_box_width, selected.word_box_height, selected.word_box_angle]
        # now we have the user or ocr selection, check if there was manual changes

        text_to_send = {}
        if field == "total":
            text_to_send["content"] = self.amount_total
        elif field == "subtotal":
            text_to_send["content"] = self.amount_untaxed
        elif field == "global_taxes_amount":
            text_to_send["content"] = self.amount_tax
        elif field == "global_taxes":
            text_to_send["content"] = [{
                'amount': line.debit,
                'tax_amount': line.tax_line_id.amount,
                'tax_amount_type': line.tax_line_id.amount_type,
                'tax_price_include': line.tax_line_id.price_include} for line in self.line_ids.filtered('tax_repartition_line_id')]
        elif field == "date":
            text_to_send["content"] = str(self.invoice_date)
        elif field == "due_date":
            text_to_send["content"] = str(self.invoice_date_due)
        elif field == "invoice_id":
            text_to_send["content"] = self.ref
        elif field == "supplier":
            text_to_send["content"] = self.partner_id.name
        elif field == "VAT_Number":
            text_to_send["content"] = self.partner_id.vat
        elif field == "currency":
            text_to_send["content"] = self.currency_id.name
        elif field == "payment_ref":
            text_to_send["content"] = self.invoice_payment_ref
        elif field == "iban":
            text_to_send["content"] = self.invoice_partner_bank_id.acc_number if self.invoice_partner_bank_id else False
        elif field == "SWIFT_code":
            text_to_send["content"] = self.invoice_partner_bank_id.bank_bic if self.invoice_partner_bank_id else False
        elif field == "invoice_lines":
            text_to_send = {'lines': []}
            for il in self.invoice_line_ids:
                line = {
                    "description": il.name,
                    "quantity": il.quantity,
                    "unit_price": il.price_unit,
                    "product": il.product_id.id,
                    "taxes_amount": round(il.price_total - il.price_subtotal, 2),
                    "taxes": [{
                        'amount': tax.amount,
                        'type': tax.amount_type,
                        'price_include': tax.price_include} for tax in il.tax_ids],
                    "subtotal": il.price_subtotal,
                    "total": il.price_total
                }
                text_to_send['lines'].append(line)
        else:
            return None

        return_box.update(text_to_send)
        return return_box

    def post(self):
        # OVERRIDE
        # On the validation of an invoice, send the different corrected fields to iap to improve the ocr algorithm.
        res = super(AccountMove, self).post()
        for record in self.filtered(lambda move: move.type in ['in_invoice', 'in_refund']):
            if record.extract_state == 'waiting_validation':
                values = {
                    'total': record.get_validation('total'),
                    'subtotal': record.get_validation('subtotal'),
                    'global_taxes': record.get_validation('global_taxes'),
                    'global_taxes_amount': record.get_validation('global_taxes_amount'),
                    'date': record.get_validation('date'),
                    'due_date': record.get_validation('due_date'),
                    'invoice_id': record.get_validation('invoice_id'),
                    'partner': record.get_validation('supplier'),
                    'VAT_Number': record.get_validation('VAT_Number'),
                    'currency': record.get_validation('currency'),
                    'payment_ref': record.get_validation('payment_ref'),
                    'iban': record.get_validation('iban'),
                    'SWIFT_code': record.get_validation('SWIFT_code'),
                    'merged_lines': self.env.company.extract_single_line_per_tax,
                    'invoice_lines': record.get_validation('invoice_lines')
                }
                params = {
                    'document_id': record.extract_remote_id,
                    'values': values
                }
                try:
                    self._contact_iap_extract('/iap/invoice_extract/validate', params=params)
                    record.extract_state = 'done'
                except AccessError:
                    pass
        # we don't need word data anymore, we can delete them
        self.mapped('extract_word_ids').unlink()
        return res

    def get_boxes(self):
        return [{
            "id": data.id,
            "feature": data.field,
            "text": data.word_text,
            "selected_status": data.selected_status,
            "user_selected": data.user_selected,
            "page": data.word_page,
            "box_midX": data.word_box_midX,
            "box_midY": data.word_box_midY,
            "box_width": data.word_box_width,
            "box_height": data.word_box_height,
            "box_angle": data.word_box_angle} for data in self.extract_word_ids]

    def remove_user_selected_box(self, id):
        """Set the selected box for a feature. The id of the box indicates the concerned feature.
        The method returns the text that can be set in the view (possibly different of the text in the file)"""
        self.ensure_one()
        word = self.env["account.invoice_extract.words"].browse(int(id))
        to_unselect = self.env["account.invoice_extract.words"].search([("invoice_id", "=", self.id), ("field", "=", word.field), '|', ("user_selected", "=", True), ("selected_status", "!=", 0)])
        user_selected_found = False
        for box in to_unselect:
            if box.user_selected:
                user_selected_found = True
                box.user_selected = False
        ocr_new_value = 0
        new_word = None
        if user_selected_found:
            ocr_new_value = 1
        for box in to_unselect:
            if box.selected_status != 0:
                box.selected_status = ocr_new_value
                if ocr_new_value != 0:
                    new_word = box
        word.user_selected = False
        if new_word is None:
            if word.field in ["VAT_Number", "supplier", "currency"]:
                return 0
            return ""
        if new_word.field == "VAT_Number":
            partner_vat = self.env["res.partner"].search([("vat", "=", new_word.word_text)], limit=1)
            if partner_vat.exists():
                return partner_vat.id
            return 0
        if new_word.field == "supplier":
            partner_names = self.env["res.partner"].search([("name", "ilike", new_word.word_text)])
            if partner_names.exists():
                partner = min(partner_names, key=len)
                return partner.id
            else:
                partners = {}
                for single_word in new_word.word_text.split(" "):
                    partner_names = self.env["res.partner"].search([("name", "ilike", single_word)], limit=30)
                    for partner in partner_names:
                        partners[partner.id] = partners[partner.id] + 1 if partner.id in partners else 1
                if len(partners) > 0:
                    key_max = max(partners.keys(), key=(lambda k: partners[k]))
                    return key_max
            return 0
        return new_word.word_text

    def set_user_selected_box(self, id):
        """Set the selected box for a feature. The id of the box indicates the concerned feature.
        The method returns the text that can be set in the view (possibly different of the text in the file)"""
        self.ensure_one()
        word = self.env["account.invoice_extract.words"].browse(int(id))
        to_unselect = self.env["account.invoice_extract.words"].search([("invoice_id", "=", self.id), ("field", "=", word.field), ("user_selected", "=", True)])
        for box in to_unselect:
            box.user_selected = False
        ocr_boxes = self.env["account.invoice_extract.words"].search([("invoice_id", "=", self.id), ("field", "=", word.field), ("selected_status", "=", 1)])
        for box in ocr_boxes:
            if box.selected_status != 0:
                box.selected_status = 2
        word.user_selected = True
        if word.field == "currency":
            text = word.word_text
            currency = None
            currencies = self.env["res.currency"].search([])
            for curr in currencies:
                if text == curr.currency_unit_label:
                    currency = curr
                if text == curr.name or text == curr.symbol:
                    currency = curr
            if currency:
                return currency.id
            return self.currency_id.id
        if word.field == "VAT_Number":
            partner_vat = False
            if word.word_text != "":
                partner_vat = self.env["res.partner"].search([("vat", "=", word.word_text)], limit=1)
            if partner_vat:
                return partner_vat.id
            else:
                vat = word.word_text
                partner = self._create_supplier_from_vat(vat)
                return partner.id if partner else False

        if word.field == "supplier":
            return self.find_partner_id_with_name(word.word_text)
        return word.word_text

    def _create_supplier_from_vat(self, vat_number_ocr):
        params = {
            'db_uuid': self.env['ir.config_parameter'].sudo().get_param('database.uuid'),
            'account_token': self.env['iap.account'].get('partner_autocomplete').account_token,
            'country_code': self.company_id.country_id.code,
            'vat': vat_number_ocr,
        }
        try:
            response = self._contact_iap_partner_autocomplete('/iap/partner_autocomplete/enrich', params)
        except Exception as exception:
            _logger.error('Check VAT error: %s' % str(exception))
            return False

        if response and response.get('company_data'):
            country_id = self.env['res.country'].search([('code', '=', response.get('company_data').get('country_code',''))])
            state_id = self.env['res.country.state'].search([('name', '=', response.get('company_data').get('state_name',''))])
            resp_values = response.get('company_data')
            if 'bank_ids' in resp_values:
                resp_values['bank_ids'] = [(0, 0, vals) for vals in resp_values['bank_ids']]
            values = {
                'name': resp_values.get('name', ''),
                'vat': resp_values.get('vat', ''),
                'bank_ids': resp_values.get('bank_ids', ''),
                'street': resp_values.get('street', ''),
                'city': resp_values.get('city', ''),
                'zip': resp_values.get('zip', ''),
                'state_id': state_id and state_id.id,
                'country_id': country_id and country_id.id,
                'phone': resp_values.get('phone', ''),
                'email': resp_values.get('email', ''),
                'is_company': True,
            }
            # partner_gid is defined in partner_autocomplete, which is not a dependency of
            # account_invoice_extract
            if 'partner_gid' in self.env['res.partner']._fields:
                values['partner_gid'] = resp_values.get('partner_gid', '')
            new_partner = self.env["res.partner"].with_context(clean_context(self.env.context)).create(values)
            return new_partner
        return False

    def find_partner_id_with_name(self, partner_name):
        if not partner_name:
            return 0
        partner_names = self.env["res.partner"].search([("name", "ilike", partner_name)])
        if partner_names.exists():
            partner = min(partner_names, key=len)
            return partner.id
        else:
            partners = {}
            for single_word in [word for word in re.findall(r"[\w]+", partner_name) if len(word) >= 4]:
                partner_names = self.env["res.partner"].search([("name", "ilike", single_word)], limit=30)
                for partner in partner_names:
                    partners[partner.id] = partners[partner.id] + 1 if partner.id in partners else 1
            if len(partners) > 0:
                key_max = max(partners.keys(), key=(lambda k: partners[k]))
                return key_max
        return 0

    def _get_taxes_record(self, taxes_ocr, taxes_type_ocr):
        """
        Find taxes records to use from the taxes detected for an invoice line.
        """
        taxes_found = self.env['account.tax']
        for (taxes, taxes_type) in zip(taxes_ocr, taxes_type_ocr):
            if taxes != 0.0:
                related_documents = self.env['account.move'].search([('state', '!=', 'draft'), ('type', '=', self.type), ('partner_id', '=', self.partner_id.id)])
                lines = related_documents.mapped('invoice_line_ids')
                taxes_ids = related_documents.mapped('invoice_line_ids.tax_ids')
                taxes_ids.filtered(lambda tax: tax.amount == taxes and tax.amount_type == taxes_type and tax.type_tax_use == 'purchase')
                taxes_by_document = []
                for tax in taxes_ids:
                    taxes_by_document.append((tax, lines.filtered(lambda line: tax in line.tax_ids)))
                if len(taxes_by_document) != 0:
                    taxes_found |= max(taxes_by_document, key=lambda tax: len(tax[1]))[0]
                else:
                    taxes_records = self.env['account.tax'].search([('amount', '=', taxes), ('amount_type', '=', taxes_type), ('type_tax_use', '=', 'purchase'), ('company_id', '=', self.company_id.id)])
                    if taxes_records:
                        # prioritize taxes that are not included in the price
                        taxes_records_not_included = taxes_records.filtered(lambda r: not r.price_include)
                        if taxes_records_not_included:
                            taxes_record = taxes_records_not_included[0]
                        else:
                            taxes_record = taxes_records[0]
                        taxes_found |= taxes_record
        return taxes_found

    def _get_invoice_lines(self, invoice_lines, subtotal_ocr):
        """
        Get write values for invoice lines.
        """
        self.ensure_one()
        invoice_lines_to_create = []
        if self.env.company.extract_single_line_per_tax:
            merged_lines = {}
            for il in invoice_lines:
                description = il['description']['selected_value']['content'] if 'description' in il else None
                total = il['total']['selected_value']['content'] if 'total' in il else 0.0
                subtotal = il['subtotal']['selected_value']['content'] if 'subtotal' in il else total
                taxes_ocr = [value['content'] for value in il['taxes']['selected_values']] if 'taxes' in il else []
                taxes_type_ocr = [value['amount_type'] if 'amount_type' in value else 'percent' for value in il['taxes']['selected_values']] if 'taxes' in il else []
                taxes_records = self._get_taxes_record(taxes_ocr, taxes_type_ocr)

                taxes_ids = tuple(sorted(taxes_records.ids))
                if taxes_ids not in merged_lines:
                    merged_lines[taxes_ids] = {'subtotal': subtotal, 'description': [description] if description is not None else []}
                else:
                    merged_lines[taxes_ids]['subtotal'] += subtotal
                    if description is not None:
                        merged_lines[taxes_ids]['description'].append(description)
                merged_lines[taxes_ids]['taxes_records'] = taxes_records

            # if there is only one line after aggregating the lines, use the total found by the ocr as it is less error-prone
            if len(merged_lines) == 1:
                merged_lines[list(merged_lines.keys())[0]]['subtotal'] = subtotal_ocr

            for taxes_ids, il in merged_lines.items():
                vals = {
                    'name': "\n".join(il['description']) if len(il['description']) > 0 else "/",
                    'price_unit': il['subtotal'],
                    'quantity': 1.0,
                    'tax_ids': il['taxes_records']
                }

                invoice_lines_to_create.append(vals)
        else:
            for il in invoice_lines:
                description = il['description']['selected_value']['content'] if 'description' in il else "/"
                total = il['total']['selected_value']['content'] if 'total' in il else 0.0
                subtotal = il['subtotal']['selected_value']['content'] if 'subtotal' in il else total
                unit_price = il['unit_price']['selected_value']['content'] if 'unit_price' in il else subtotal
                quantity = il['quantity']['selected_value']['content'] if 'quantity' in il else 1.0
                taxes_ocr = [value['content'] for value in il['taxes']['selected_values']] if 'taxes' in il else []
                taxes_type_ocr = [value['amount_type'] if 'amount_type' in value else 'percent' for value in il['taxes']['selected_values']] if 'taxes' in il else []

                vals = {
                    'name': description,
                    'price_unit': unit_price,
                    'quantity': quantity,
                    'tax_ids': self._get_taxes_record(taxes_ocr, taxes_type_ocr)
                }

                invoice_lines_to_create.append(vals)

        return invoice_lines_to_create

    @api.model
    def check_all_status(self):
        for record in self.search([('state', '=', 'draft'), ('extract_state', 'in', ['waiting_extraction', 'extract_not_ready'])]):
            try:
                with self.env.cr.savepoint():
                    record._check_status()
            except Exception as e:
                _logger.error("Couldn't check status of account.move with id %d: %s", record.id, str(e))

    def check_status(self):
        """contact iap to get the actual status of the ocr requests"""
        records_to_update = self.filtered(lambda inv: inv.extract_state in ['waiting_extraction', 'extract_not_ready'] and inv.state == 'draft')

        for record in records_to_update:
            record._check_status()

        limit = max(0, 20 - len(records_to_update))
        if limit > 0:
            records_to_preupdate = self.search([('extract_state', 'in', ['waiting_extraction', 'extract_not_ready']), ('id', 'not in', records_to_update.ids), ('state', '=', 'draft')], limit=limit)
            for record in records_to_preupdate:
                try:
                    with self.env.cr.savepoint():
                        record._check_status()
                except Exception as e:
                    _logger.error("Couldn't check status of account.move with id %d: %s", record.id, str(e))

    def _check_status(self):
        self.ensure_one()
        if self.state == 'draft':
            params = {
                'document_id': self.extract_remote_id
            }
            result = self._contact_iap_extract('/iap/invoice_extract/get_result', params=params)
            self.extract_status_code = result['status_code']
            if result['status_code'] == SUCCESS:
                self.extract_state = "waiting_validation"
                ocr_results = result['results'][0]
                self.extract_word_ids.unlink()

                # We still want to save all other fields when there is a duplicate vendor reference
                try:
                    # Savepoint so the transactions don't go through if the save raises an exception
                    with self.env.cr.savepoint():
                        self._save_form(ocr_results)
                # Retry saving without the ref, then set the error status to show the user a warning
                except ValidationError as e:
                    self._save_form(ocr_results, no_ref=True)
                    self.extract_status_code = WARNING_DUPLICATE_VENDOR_REFERENCE
                    self.duplicated_vendor_ref = ocr_results['invoice_id']['selected_value']['content'] if 'invoice_id' in ocr_results else ""

                fields_with_boxes = ['supplier', 'date', 'due_date', 'invoice_id', 'currency', 'VAT_Number']
                for field in fields_with_boxes:
                    if field in ocr_results:
                        value = ocr_results[field]
                        data = []
                        for word in value["words"]:
                            data.append((0, 0, {
                                "field": field,
                                "selected_status": 1 if value["selected_value"] == word else 0,
                                "word_text": word['content'],
                                "word_page": word['page'],
                                "word_box_midX": word['coords'][0],
                                "word_box_midY": word['coords'][1],
                                "word_box_width": word['coords'][2],
                                "word_box_height": word['coords'][3],
                                "word_box_angle": word['coords'][4],
                            }))
                        self.write({'extract_word_ids': data})
            elif result['status_code'] == NOT_READY:
                self.extract_state = 'extract_not_ready'
            else:
                self.extract_state = 'error_status'

    def _save_form(self, ocr_results, no_ref=False):
        supplier_ocr = ocr_results['supplier']['selected_value']['content'] if 'supplier' in ocr_results else ""
        date_ocr = ocr_results['date']['selected_value']['content'] if 'date' in ocr_results else ""
        due_date_ocr = ocr_results['due_date']['selected_value']['content'] if 'due_date' in ocr_results else ""
        total_ocr = ocr_results['total']['selected_value']['content'] if 'total' in ocr_results else ""
        subtotal_ocr = ocr_results['subtotal']['selected_value']['content'] if 'subtotal' in ocr_results else ""
        invoice_id_ocr = ocr_results['invoice_id']['selected_value']['content'] if 'invoice_id' in ocr_results else ""
        currency_ocr = ocr_results['currency']['selected_value']['content'] if 'currency' in ocr_results else ""
        vat_number_ocr = ocr_results['VAT_Number']['selected_value']['content'] if 'VAT_Number' in ocr_results else ""
        payment_ref_ocr = ocr_results['payment_ref']['selected_value']['content'] if 'payment_ref' in ocr_results else ""
        iban_ocr = ocr_results['iban']['selected_value']['content'] if 'iban' in ocr_results else ""
        SWIFT_code_ocr = json.loads(ocr_results['SWIFT_code']['selected_value']['content']) if 'SWIFT_code' in ocr_results else None
        invoice_lines = ocr_results['invoice_lines'] if 'invoice_lines' in ocr_results else []

        vals_invoice_lines = self._get_invoice_lines(invoice_lines, subtotal_ocr)

        if 'default_journal_id' in self._context:
            self_ctx = self
        else:
            # we need to make sure the type is in the context as _get_default_journal uses it
            self_ctx = self.with_context(default_type=self.type) if 'default_type' not in self._context else self
            self_ctx = self_ctx.with_context(force_company=self.company_id.id)
            self_ctx = self_ctx.with_context(default_journal_id=self_ctx._get_default_journal().id)
        with Form(self_ctx) as move_form:
            if not move_form.partner_id:
                if vat_number_ocr:
                    partner_vat = self.env["res.partner"].search([("vat", "=ilike", vat_number_ocr)], limit=1)
                    if partner_vat.exists():
                        move_form.partner_id = partner_vat
                if not move_form.partner_id:
                    partner_id = self.find_partner_id_with_name(supplier_ocr)
                    if partner_id != 0:
                        move_form.partner_id = self.env["res.partner"].browse(partner_id)
                if not move_form.partner_id and vat_number_ocr:
                    created_supplier = self._create_supplier_from_vat(vat_number_ocr)
                    if created_supplier:
                        move_form.partner_id = created_supplier
                        if iban_ocr and not move_form.invoice_partner_bank_id:
                            bank_account = self.env['res.partner.bank'].search([('acc_number', '=ilike', iban_ocr)])
                            if bank_account.exists():
                                if bank_account.partner_id == move_form.partner_id.id:
                                    move_form.invoice_partner_bank_id = bank_account
                            else:
                                vals = {
                                        'partner_id': move_form.partner_id.id,
                                        'acc_number': iban_ocr
                                       }
                                if SWIFT_code_ocr:
                                    bank_id = self.env['res.bank'].search([('bic', '=', SWIFT_code_ocr['bic'])], limit=1)
                                    if bank_id.exists():
                                        vals['bank_id'] = bank_id.id
                                    if not bank_id.exists() and SWIFT_code_ocr['verified_bic']:
                                        country_id = self.env['res.country'].search([('code', '=', SWIFT_code_ocr['country_code'])], limit=1)
                                        if country_id.exists():
                                            vals['bank_id'] = self.env['res.bank'].create({'name': SWIFT_code_ocr['name'], 'country': country_id.id, 'city': SWIFT_code_ocr['city'], 'bic': SWIFT_code_ocr['bic']}).id
                                move_form.invoice_partner_bank_id = self.with_context(clean_context(self.env.context)).env['res.partner.bank'].create(vals)

            due_date_move_form = move_form.invoice_date_due  # remember the due_date, as it could be modified by the onchange() of invoice_date
            if date_ocr and (not move_form.invoice_date or move_form.invoice_date == str(self._get_default_invoice_date())):
                move_form.invoice_date = date_ocr
            if due_date_ocr and (not move_form.invoice_date_due or due_date_move_form == str(self._get_default_invoice_date())):
                move_form.invoice_date_due = due_date_ocr
            if not move_form.ref and not no_ref:
                move_form.ref = invoice_id_ocr

            if self.user_has_groups('base.group_multi_currency') and (not move_form.currency_id or move_form.currency_id == self._get_default_currency()):
                currency = self.env["res.currency"].search([
                        '|', '|', ('currency_unit_label', 'ilike', currency_ocr),
                        ('name', 'ilike', currency_ocr), ('symbol', 'ilike', currency_ocr)], limit=1)
                if currency:
                    move_form.currency_id = currency

            if payment_ref_ocr and not move_form.invoice_payment_ref:
                move_form.invoice_payment_ref = payment_ref_ocr

            if not move_form.invoice_line_ids:
                for line_val in vals_invoice_lines:
                    with move_form.invoice_line_ids.new() as line:
                        line.name = line_val['name']
                        line.price_unit = line_val['price_unit']
                        line.quantity = line_val['quantity']
                        line.tax_ids.clear()
                        for taxes_record in line_val['tax_ids']:
                            line.tax_ids.add(taxes_record)
                        if not line.account_id:
                            raise ValidationError(_("The OCR module is not able to generate the invoice lines because the default accounts are not correctly set on the %s journal.") % move_form.journal_id.name_get()[0][1])

                # if the total on the invoice doesn't match the total computed by Odoo, adjust the taxes so that it matches
                for i in range(len(move_form.line_ids)):
                    with move_form.line_ids.edit(i) as line:
                        if line.tax_repartition_line_id and total_ocr:
                            rounding_error = move_form.amount_total - total_ocr
                            threshold = len(vals_invoice_lines) * 0.01
                            if rounding_error != 0.0 and abs(rounding_error) < threshold:
                                line.debit -= rounding_error
                            break

    def buy_credits(self):
        url = self.env['iap.account'].get_credits_url(base_url='', service_name='invoice_ocr')
        return {
            'type': 'ir.actions.act_url',
            'url': url,
        }
