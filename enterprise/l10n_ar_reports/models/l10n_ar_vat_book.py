# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, models
from odoo.exceptions import UserError
from collections import OrderedDict
from odoo.tools.misc import format_date
import re
import json


class L10nARVatBook(models.AbstractModel):

    _name = "l10n_ar.vat.book"
    _inherit = "account.report"
    _description = "Argentinian VAT Book"

    filter_date = {'date_from': '', 'date_to': '', 'filter': 'this_month'}
    filter_all_entries = False

    def print_pdf(self, options):
        options.update({
            'journal_type': self.env.context.get('journal_type')
        })
        return super(L10nARVatBook, self).print_pdf(options)

    def print_xlsx(self, options):
        options.update({
            'journal_type': self.env.context.get('journal_type')
        })
        return super(L10nARVatBook, self).print_xlsx(options)

    @api.model
    def _get_dynamic_columns(self, options):
        """ Show or not the VAT 2.5% and VAT 5% columns if this ones are active/inactive """
        res = []
        if self.env['account.tax'].search([('type_tax_use', '=', options.get('journal_type')), ('tax_group_id.l10n_ar_vat_afip_code', '=', '9')]):
            res.append({'sql_var': 'vat_25', 'name': _('VAT 2,5%')})
        if self.env['account.tax'].search([('type_tax_use', '=', options.get('journal_type')), ('tax_group_id.l10n_ar_vat_afip_code', '=', '8')]):
            res.append({'sql_var': 'vat_5', 'name': _('VAT 5%')})
        return res

    def _get_columns_name(self, options):
        dynamic_columns = [item.get('name') for item in self._get_dynamic_columns(options)]
        return [
            {'name': _("Date"), 'class': 'date'},
            {'name': _("Document"), 'class': 'text-left'},
            {'name': _("Name"), 'class': 'text-left'},
            {'name': _("Vat Cond."), 'class': 'text-left'},
            {'name': _("VAT"), 'class': 'text-left'},
            {'name': _('Taxed'), 'class': 'number'},
            {'name': _('Not Taxed'), 'class': 'number'},
        ] + [{'name': item, 'class': 'number'} for item in dynamic_columns] + [
            {'name': _('VAT 10,5%'), 'class': 'number'},
            {'name': _('VAT 21%'), 'class': 'number'},
            {'name': _('VAT 27%'), 'class': 'number'},
            {'name': _('VAT Perc'), 'class': 'number'},
            {'name': _('Other Taxes'), 'class': 'number'},
            {'name': _('Total'), 'class': 'number'},
        ]

    @api.model
    def _get_lines(self, options, line_id=None):
        journal_type = options.get('journal_type')
        if not journal_type:
            journal_type = self.env.context.get('journal_type', 'sale')
            options.update({'journal_type': journal_type})
        lines = []
        line_id = 0
        sign = 1.0 if journal_type == 'purchase' else -1.0
        domain = self._get_lines_domain(options)

        dynamic_columns = [item.get('sql_var') for item in self._get_dynamic_columns(options)]
        totals = {}.fromkeys(['taxed', 'not_taxed'] + dynamic_columns + ['vat_10', 'vat_21', 'vat_27', 'vat_per', 'other_taxes', 'total'], 0)
        for rec in self.env['account.ar.vat.line'].search_read(domain):
            taxed = rec['base_25'] + rec['base_5'] + rec['base_10'] + rec['base_21'] + rec['base_27']
            other_taxes = rec['other_taxes']
            totals['taxed'] += taxed
            totals['not_taxed'] += rec['not_taxed']
            for item in dynamic_columns:
                totals[item] += rec[item]
            totals['vat_10'] += rec['vat_10']
            totals['vat_21'] += rec['vat_21']
            totals['vat_27'] += rec['vat_27']
            totals['vat_per'] += rec['vat_per']
            totals['other_taxes'] += other_taxes
            totals['total'] += rec['total']

            if rec['type'] in ['in_invoice', 'in_refund']:
                caret_type = 'account.invoice.in'
            elif rec['type'] in ['out_invoice', 'out_refund']:
                caret_type = 'account.invoice.out'
            else:
                caret_type = 'account.move'
            lines.append({
                'id': rec['id'],
                'name': format_date(self.env, rec['invoice_date']),
                'class': 'date' + (' text-muted' if rec['state'] != 'posted' else ''),
                'level': 2,
                'model': 'account.ar.vat.line',
                'caret_options': caret_type,
                'columns': [
                    {'name': rec['move_name']},
                    {'name': rec['partner_name']},
                    {'name': rec['afip_responsibility_type_name']},
                    {'name': rec['cuit']},
                    {'name': self.format_value(sign * taxed)},
                    {'name': self.format_value(sign * rec['not_taxed'])},
                    ] + [
                        {'name': self.format_value(sign * rec[item])} for item in dynamic_columns] + [
                    {'name': self.format_value(sign * rec['vat_10'])},
                    {'name': self.format_value(sign * rec['vat_21'])},
                    {'name': self.format_value(sign * rec['vat_27'])},
                    {'name': self.format_value(sign * rec['vat_per'])},
                    {'name': self.format_value(sign * other_taxes)},
                    {'name': self.format_value(sign * rec['total'])},
                ],
            })
            line_id += 1

        lines.append({
            'id': 'total',
            'name': _('Total'),
            'class': 'o_account_reports_domain_total',
            'level': 0,
            'columns': [
                {'name': ''},
                {'name': ''},
                {'name': ''},
                {'name': ''},
                {'name': self.format_value(sign * totals['taxed'])},
                {'name': self.format_value(sign * totals['not_taxed'])},
                ] + [
                    {'name': self.format_value(sign * totals[item])} for item in dynamic_columns] + [
                {'name': self.format_value(sign * totals['vat_10'])},
                {'name': self.format_value(sign * totals['vat_21'])},
                {'name': self.format_value(sign * totals['vat_27'])},
                {'name': self.format_value(sign * totals['vat_per'])},
                {'name': self.format_value(sign * totals['other_taxes'])},
                {'name': self.format_value(sign * totals['total'])},
            ],
        })

        return lines

    def get_report_filename(self, options):
        """ Return the name that will be used for the file when downloading pdf, xlsx, txt_file, etc """
        res = super().get_report_filename(options)
        journal_type = options.get('journal_type', '')

        # set filename for txt file
        txt_file = options.get('txt_type')
        if txt_file:
            filenames = {'import_aliquots': _('Importation_Aliquots'), 'aliquots': _('Aliquots'),
                         'vouchers': _('Vouchers')}
            filename = filenames.get(txt_file)
            if filename:
                return filename + '_%s_%s' % (journal_type, options.get('date', {}).get('date_to'))

        # set filename for regular vat book
        filenames = {'sale': _('Sales VAT book'), 'purchase': _('Purchases VAT book')}
        filename = filenames.get(journal_type, _('VAT book'))
        if filename:
            return filename

        return res

    def _get_reports_buttons(self):
        """ Add buttons to print the txt files used for AFIP to report the vat books """
        buttons = super(L10nARVatBook, self)._get_reports_buttons()
        buttons += [{'name': _('Vouchers (TXT)'), 'sequence': 3, 'action': 'print_vouchers', 'file_export_type': _('VOUCHER TXT')}]
        buttons += [{'name': _('Aliquots (TXT)'), 'sequence': 4, 'action': 'print_aliquots', 'file_export_type': _('ALIQUOTS TXT')}]
        if self.env.context.get('journal_type') == 'purchase':
            buttons += [{'name': _('Importation Aliquots (TXT)'), 'sequence': 5, 'action': 'print_aliquots_import', 'file_export_type': _('IMPORTATION ALIQUOTS TXT')}]
        return buttons

    def _l10n_ar_print_txt_file(self, options):
        """ Print the txt file depending on the options given """
        journal_type = self.env.context.get('journal_type', 'sale')
        options.update({'journal_type': journal_type})
        return {
            'type': 'ir_actions_account_report_download',
            'data': {'model': self.env.context.get('model'), 'options': json.dumps(options), 'output_format': 'txt',
                     'financial_id': self.env.context.get('id')}}

    def print_aliquots(self, options):
        """ Button that lets us print the Aliquotes TXT file that we upload to AFIP for both purchase/sale book"""
        options.update({'txt_type': 'aliquots'})
        return self._l10n_ar_print_txt_file(options)

    def print_aliquots_import(self, options):
        """ Button that lets us print the Importation Aliquotes TXT file that we upload to AFIP for Purchase VAT Book """
        options.update({'txt_type': 'import_aliquots'})
        return self._l10n_ar_print_txt_file(options)

    def print_vouchers(self, options):
        """ Button that lets us print Vouchers TXT file that we upload to AFIP to report Sale/Purchase VAT Book """
        options.update({'txt_type': 'vouchers'})
        return self._l10n_ar_print_txt_file(options)

    def get_txt(self, options):
        """ Compute the date to be printed in the txt files"""
        # We always compute the aliquots because we use it for the vouchers files
        txt_type = options.get('txt_type')
        lines = []
        aliquots = self._get_REGINFO_CV_ALICUOTAS(options)
        for k, v in aliquots.items():
            lines += v
        res = '\r\n'.join(lines)

        if txt_type == 'vouchers':
            if options.get('journal_type') == 'purchase':
                new_options = options.copy()
                new_options['txt_type'] = 'import_aliquots'
                impo_aliquots = self._get_REGINFO_CV_ALICUOTAS(new_options)
                aliquots.update(impo_aliquots)

            res = self._get_REGINFO_CV_CBTE(options, aliquots)
        return res.encode('ISO-8859-1')

    @api.model
    def _get_lines_domain(self, options):
        company_ids = self.env.company.ids
        domain = [('journal_id.type', '=', options.get('journal_type')),
                  ('journal_id.l10n_latam_use_documents', '=', True), ('company_id', 'in', company_ids)]
        state = options.get('all_entries') and 'all' or 'posted'
        if state and state.lower() != 'all':
            domain += [('state', '=', state)]
        if options.get('date').get('date_to'):
            domain += [('date', '<=', options['date']['date_to'])]
        if options.get('date').get('date_from'):
            domain += [('date', '>=', options['date']['date_from'])]
        return domain

    @api.model
    def _format_amount(self, amount, padding=15, decimals=2):
        """ We need to represent float numbers as  integers, with certain padding and taking into account certain
        decimals to ba take into account. For example:

            amount -2.1589 with default padding and decimales
            should return -00000000000215 which is:
               * a integer with padding 15 that includes the sign of the amount if negative
               * the integer part of the amount concatenate with 2 digits of the decimal part of the amount """
        template = "{:0" + str(padding) + "d}"
        return template.format(round(amount * 10**decimals))

    @api.model
    def _get_partner_document_code_and_number(self, partner):
        """ For a given partner turn the identification coda and identification number in the expected format for the
        txt files """
        # CUIT is mandatory for all except for final consummer
        if partner.l10n_ar_afip_responsibility_type_id.code == '5':
            doc_code = "{:0>2d}".format(int(partner.l10n_latam_identification_type_id.l10n_ar_afip_code))
            doc_number = partner.vat or ''
            # we clean the letters that are not supported
            doc_number = re.sub("[^0-9]", "", doc_number)
        elif partner.l10n_ar_afip_responsibility_type_id.code == '9':
            commercial_partner = partner.commercial_partner_id
            doc_number = partner.l10n_ar_vat or commercial_partner.country_id.l10n_ar_legal_entity_vat \
                if commercial_partner.is_company else commercial_partner.country_id.l10n_ar_natural_vat
            doc_code = '80'
        else:
            doc_number = partner.ensure_vat()
            doc_code = '80'
        return doc_code, doc_number.rjust(20, '0')

    @api.model
    def _get_pos_and_invoice_invoice_number(self, invoice):
        res = invoice._l10n_ar_get_document_number_parts(
            invoice.l10n_latam_document_number, invoice.l10n_latam_document_type_id.code)
        return "{:0>20d}".format(res['invoice_number']), "{:0>5d}".format(res['point_of_sale'])

    def _get_txt_invoices(self, options):
        state = options.get('all_entries') and 'all' or 'posted'
        if state != 'posted':
            raise UserError(_('Can only generate TXT files using posted entries.'
                              ' Please remove Include unposted entries filter and try again'))

        domain = [('l10n_latam_document_type_id.code', '!=', False)] + self._get_lines_domain(options)
        if options.get('txt_type') != 'vouchers':
            impo = options.get('txt_type') == 'import_aliquots'
            domain += [('l10n_latam_document_type_id.code', '=' if impo else '!=', 66)]
        return self.env['account.move'].search(domain, order='invoice_date asc, name asc, id asc')

    def _get_tax_row(self, invoice, base, code, tax_amount, options):
        inv = invoice
        journal_type = options.get('journal_type')
        impo = options.get('txt_type') == 'import_aliquots'

        invoice_number, pos_number = self._get_pos_and_invoice_invoice_number(inv)
        doc_code, doc_number = self._get_partner_document_code_and_number(inv.commercial_partner_id)
        if journal_type == 'sale':
            row = [
                "{:0>3d}".format(int(inv.l10n_latam_document_type_id.code)),  # Field 1: Tipo de Comprobante
                pos_number,  # Field 2: Punto de Venta
                invoice_number,  # Field 3: Número de Comprobante
                self._format_amount(base),  # Field 4: Importe Neto Gravado
                str(code).rjust(4, '0'),  # Field 5: Alícuota de IVA.
                self._format_amount(tax_amount),  # Field 6: Impuesto Liquidado.
            ]
        elif impo:
            row = [
                (inv.l10n_latam_document_number or inv.name or '').rjust(16, '0'),  # Field 1: Despacho de importación.
                self._format_amount(base),  # Field 2: Importe Neto Gravado
                str(code).rjust(4, '0'),  # Field 3: Alícuota de IVA
                self._format_amount(tax_amount),  # Field 4: Impuesto Liquidado.
            ]
        else:
            row = [
                "{:0>3d}".format(int(inv.l10n_latam_document_type_id.code)),  # Field 1: Tipo de Comprobante
                pos_number,  # Field 2: Punto de Venta
                invoice_number,  # Field 3: Número de Comprobante
                doc_code,  # Field 4: Código de documento del vendedor
                doc_number,  # Field 5: Número de identificación del vendedor
                self._format_amount(base),  # Field 6: Importe Neto Gravado
                str(code).rjust(4, '0'),  # Field 7: Alícuota de IVA.
                self._format_amount(tax_amount),  # Field 8: Impuesto Liquidado.
            ]
        return row

    def _get_REGINFO_CV_CBTE(self, options, aliquots):
        res = []
        journal_type = options.get('journal_type')
        invoices = self._get_txt_invoices(options)

        for inv in invoices:
            aliquots_count = len(aliquots.get(inv))

            currency_rate = inv.l10n_ar_currency_rate
            currency_code = inv.currency_id.l10n_ar_afip_code

            invoice_number, pos_number = self._get_pos_and_invoice_invoice_number(inv)
            doc_code, doc_number = self._get_partner_document_code_and_number(inv.partner_id)

            amounts = inv._l10n_ar_get_amounts(company_currency=True)
            amount_total = (1 if inv.is_inbound() else -1) * inv.amount_total_signed
            vat_amount = amounts['vat_amount']
            vat_exempt_base_amount = amounts['vat_exempt_base_amount']
            vat_untaxed_base_amount = amounts['vat_untaxed_base_amount']
            other_taxes_amount = amounts['other_taxes_amount']
            vat_perc_amount = amounts['vat_perc_amount']
            iibb_perc_amount = amounts['iibb_perc_amount']
            mun_perc_amount = amounts['mun_perc_amount']
            intern_tax_amount = amounts['intern_tax_amount']
            perc_imp_nacionales_amount = amounts['profits_perc_amount'] + amounts['other_perc_amount']

            if vat_exempt_base_amount:
                if inv.partner_id.l10n_ar_afip_responsibility_type_id.code == '10':  # free zone operation
                    operation_code = 'Z'
                elif inv.l10n_latam_document_type_id.l10n_ar_letter == 'E':          # exportation operation
                    operation_code = 'X'
                else:                                                                # exempt operation
                    operation_code = 'E'
            elif inv.l10n_latam_document_type_id.code == '66':                       # import clearance
                operation_code = 'E'
            elif vat_untaxed_base_amount:                                            # not taxed operation
                operation_code = 'N'
            else:
                operation_code = ' '

            row = [
                inv.invoice_date.strftime('%Y%m%d'),  # Field 1: Fecha de comprobante
                "{:0>3d}".format(int(inv.l10n_latam_document_type_id.code)),  # Field 2: Tipo de Comprobante.
                pos_number,  # Field 3: Punto de Venta
                invoice_number,  # Field 4: Número de Comprobante
                # If it is a multiple-sheet receipt, the document number of the first sheet must be reported, taking into account the provisions of article 23, paragraph a), point 6. of General Resolution No. 1,415, the related resolutions that modify and complement this one.
                # In the case of registering grouped by daily totals, the first voucher number of the range to be considered must be entered.
            ]

            if journal_type == 'sale':
                # Field 5: Número de Comprobante Hasta: En el resto de los casos se consignará el dato registrado en el campo 4
                row.append(invoice_number)
            else:
                # Field 5: Despacho de importación
                if inv.l10n_latam_document_type_id.code == '66':
                    row.append((inv.l10n_latam_document_number).rjust(16, '0'))
                else:
                    row.append(''.rjust(16, ' '))

            row += [
                doc_code,  # Field 6: Código de documento del comprador.
                doc_number,  # Field 7: Número de Identificación del comprador
                inv.commercial_partner_id.name.ljust(30, ' ')[:30],  # Field 8: Apellido y Nombre del comprador.
                self._format_amount(amount_total),  # Field 9: Importe Total de la Operación.
                self._format_amount(vat_untaxed_base_amount),  # Field 10: Importe total de conceptos que no integran el precio neto gravado
            ]

            if journal_type == 'sale':
                row += [
                    self._format_amount(0.0),  # Field 11: Percepción a no categorizados
                    # the "uncategorized / responsible not registered" figure is not used anymore
                    self._format_amount(vat_exempt_base_amount),  # Field 12: Importe de operaciones exentas
                    self._format_amount(perc_imp_nacionales_amount + vat_perc_amount),  # Field 13: Importe de percepciones o pagos a cuenta de impuestos Nacionales
                ]
            else:
                row += [
                    self._format_amount(vat_exempt_base_amount),  # Field 11: Importe de operaciones exentas
                    self._format_amount(vat_perc_amount),  # Field 12: Importe de percepciones o pagos a cuenta del Impuesto al Valor Agregado
                    self._format_amount(perc_imp_nacionales_amount),  # Field 13: Importe de percepciones o pagos a cuenta otros impuestos nacionales
                ]

            row += [
                self._format_amount(iibb_perc_amount),  # Field 14: Importe de percepciones de ingresos brutos
                self._format_amount(mun_perc_amount),  # Field 15: Importe de percepciones de impuestos municipales
                self._format_amount(intern_tax_amount),  # Field 16: Importe de impuestos internos
                str(currency_code),  # Field 17: Código de Moneda

                self._format_amount(currency_rate, padding=10, decimals=6),  # Field 18: Tipo de Cambio
                # new modality of currency_rate

                str(aliquots_count),  # Field 19: Cantidad de alícuotas de IVA
                operation_code,  # Field 20: Código de operación.
            ]

            if journal_type == 'sale':
                row += [
                    # Field 21: Otros Tributos
                    self._format_amount(other_taxes_amount),

                    # Field 22: vencimiento comprobante
                    # NOTE: it does not appear in instructions but it does in application. for ticket and export invoice is not reported, also for some others but that we do not have implemented
                    (inv.l10n_latam_document_type_id.code in [
                        '19', '20', '21', '16', '55', '81', '82', '83', '110', '111', '112', '113', '114', '115', '116',
                        '117', '118', '119', '120', '201', '202', '203', '206', '207', '208', '211', '212', '213'] and
                        '00000000' or inv.invoice_date_due.strftime('%Y%m%d')),
                ]
            else:
                row.append(self._format_amount(vat_amount))  # Field 21: Crédito Fiscal Computable

                liquido_type = inv.l10n_latam_document_type_id.code in ['033', '058', '059', '060', '063']
                row += [
                    self._format_amount(other_taxes_amount),  # Field 22: Otros Tributos

                    # NOTE: still not implemented on this three fields for use case with third pary commisioner

                    # Field 23: CUIT Emisor / Corredor
                    # It will be reported only if the field 'Tipo de Comprobante' contains '033', '058', '059', '060' or '063'. if there is no intervention of third party in the operation then the informant VAT number will be reported. For the rest of the vouchers it will be completed with zeros
                    self._format_amount(liquido_type and inv.company_id.partner_id.ensure_vat() or 0, padding=11),

                    (liquido_type and inv.company_id.name or '').ljust(30, ' ')[:30],  # Field 24: Denominación Emisor / Corredor

                    # Field 25: IVA Comisión
                    # If field 23 is different from zero, then we will add the VAT tax base amount of thecommission
                    self._format_amount(0),
                ]
            res.append(''.join(row))
        return '\r\n'.join(res)

    def _get_REGINFO_CV_ALICUOTAS(self, options):
        """ We return a dict to calculate the number of aliquots when we make the vouchers """
        res = OrderedDict()
        # only vat taxes with codes 3, 4, 5, 6, 8, 9. this follows what is mentioned in http://contadoresenred.com/regimen-de-informacion-de-compras-y-ventas-rg-3685-como-cargar-la-informacion/. We start counting codes 1 (not taxed) and 2 (exempt) if there are no aliquots, we add one of this with 0, 0, 0 in details. we also use mapped in case there are duplicate afip codes (eg manual and auto)
        invoices = self._get_txt_invoices(options)

        for inv in invoices:
            lines = []
            vat_taxes = inv._get_vat(company_currency=True)

            # tipically this is for invoices with zero amount
            if not vat_taxes and inv.l10n_latam_document_type_id.purchase_aliquots == 'not_zero':
                lines.append(''.join(self._get_tax_row(inv, 0.0, 3, 0.0, options)))

            # we group by afip_code
            for vat_tax in vat_taxes:
                lines.append(''.join(self._get_tax_row(inv, vat_tax['BaseImp'], vat_tax['Id'], vat_tax['Importe'], options)))

            res[inv] = lines

        return res
