# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.addons.account_reports.models.account_financial_report import FormulaLine
from odoo.exceptions import UserError
import odoo.release
from odoo.tools.float_utils import float_split_str
from odoo.tools.safe_eval import safe_eval

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
import re
import unicodedata


SPANISH_PROVINCES_REPORT_CODES = {
        'VI': '01',
        'AB': '02',
        'A': '03',
        'AL': '04',
        'AV': '05',
        'BA': '06',
        'PM': '07',
        'B': '08',
        'BU': '09',
        'CC': '10',
        'CA': '11',
        'CS': '12',
        'CR': '13',
        'CO': '14',
        'C': '15',
        'CU': '16',
        'GI': '17',
        'GR': '18',
        'GU': '19',
        'SS': '20',
        'H': '21',
        'HU': '22',
        'J': '23',
        'LE': '24',
        'L': '25',
        'LO': '26',
        'LU': '27',
        'M': '28',
        'MA': '29',
        'MU': '30',
        'NA': '31',
        'OR': '32',
        'O': '33',
        'P': '34',
        'GC': '35',
        'PO': '36',
        'SA': '37',
        'TF': '38',
        'S': '39',
        'SG': '40',
        'SE': '41',
        'SO': '42',
        'T': '43',
        'TE': '44',
        'TO': '45',
        'V': '46',
        'VA': '47',
        'BI': '48',
        'ZA': '49',
        'Z': '50',
        'CE': '51',
        'ME': '52',
    }


class AEATAccountFinancialReport(models.Model):
    _inherit = 'account.financial.html.report'

    CASILLA_FIELD_PREFIX = 'casilla_'

    l10n_es_reports_modelo_number = fields.Char(string="Spanish Modelo Number", help="The modelo number of this report. Non-Spanish (or non-modelo) reports must leave this field to None.")

    @api.model
    def _get_options(self, previous_options=None):
        """ Overridden in order to add the 'financial_report_line_values' attribute
        to the context before calling super() in case some AEAT wizard was used
        to generate this report. This allows transmitting the values manually
        entered in the wizard to the report options.
        """

        if self. l10n_es_reports_modelo_number:
            aeat_wizard_id = self.env.context.get('aeat_wizard_id')
            aeat_modelo = self.env.context.get('aeat_modelo')
            if aeat_wizard_id and aeat_modelo: # If we do have these, it means an AEAT wizard was used to generate this report
                aeat_wizard = self.env['l10n_es_reports.mod' + aeat_modelo + '.wizard'].browse(aeat_wizard_id)
                casilla_prefix = self.CASILLA_FIELD_PREFIX

                # We consider all the casilla fields from the wizard, as they each correspond to a report line.
                casilla_fields = [x for x in dir(aeat_wizard) if x.startswith(casilla_prefix)]
                context_line_values = {}
                for attr in casilla_fields:
                    line_code = 'aeat_mod_' + aeat_wizard._modelo + '_' + attr.replace(self.CASILLA_FIELD_PREFIX, '')
                    context_line_values[line_code] = getattr(aeat_wizard, attr)

                self = self.with_context(financial_report_line_values= context_line_values)

        rslt = super(AEATAccountFinancialReport, self._with_correct_filters())._get_options(previous_options)

        if self.l10n_es_reports_modelo_number == '347':
            # We totally disable cash basis on mod 347, so that it does not conflict with groupby thresholds
            rslt['cash_basis'] = None
        return rslt

    @api.model
    def _set_context(self, options):
        ctx = super(AEATAccountFinancialReport, self)._set_context(options)
        if self.l10n_es_reports_modelo_number:
            # For ease of use, we pass through the context the date whose exchange rates must be applied
            # in case company currency is not €. This value is used in function
            # _boe_format_number and to compute the metalico threshold in mod 347.
            ctx['l10n_es_reports_boe_conversion_date'] = options['date']['date_to']
        return ctx

    def _get_reports_buttons(self):
        """ Overridden to add the BOE export button to mod reports.
        """
        rslt = super(AEATAccountFinancialReport, self)._get_reports_buttons()
        if self.l10n_es_reports_modelo_number:
            rslt.append({'name': _('Export (BOE)'), 'sequence': 0, 'action': 'print_boe', 'file_export_type': _('BOE')})
        return rslt

    def print_boe(self, options):
        """ Triggers the generation of the BOE file for the current mod report.
        In case this BOE file needs some more data to be entered manually by
        the user, it show instead a wizard prompting for them, which will, once
        validated and closed, trigger the generation of the BOE itself.
        """
        boe_wizard_model = self._get_boe_wizard_model()

        if boe_wizard_model != None:
            boe_wizard = boe_wizard_model.create({})

            view_id = self.env.ref('l10n_es_reports.mod' + self.l10n_es_reports_modelo_number + '_boe_wizard').id
            context = self.env.context.copy()
            context.update({'l10n_es_reports_report_options': {**options, 'l10n_es_generation_context': self.env.context}})
            return {
                'name': _('Print BOE'),
                'view_mode': 'form',
                'views': [[view_id, 'form']],
                'res_model': 'l10n_es_reports.aeat.boe.mod' + self.l10n_es_reports_modelo_number + '.export.wizard',
                'type': 'ir.actions.act_window',
                'res_id': boe_wizard.id,
                'target': 'new',
                'context': context,
            }

        # No wizard for manual values, so we directly generate the BOE
        return {
            'type': 'ir_actions_account_report_download',
            'data': {'model': self.env.context.get('model'),
                     'options': json.dumps(options),
                     'output_format': 'txt',
                     'financial_id': self.env.context.get('id'),
            },
        }

    def _get_boe_wizard_model(self):
       return self.env.get('l10n_es_reports.aeat.boe.mod' + self.l10n_es_reports_modelo_number + '.export.wizard')

    def _get_mod_period_and_year(self, options):
        """ Returns the period and year (in terms of AEAT modulo reports regulation)
        corresponding to the report options given in parameters, in the form
        of a tuple (period, year). Period will be None if the dates do not fit
        any.

        A UserError will be raised if the start and end date of given in the
        options do not corresond to the first and last day of their respective
        month, or belong to two different years.
        """
        date_from = datetime.strptime(options['date']['date_from'], "%Y-%m-%d")
        date_to = datetime.strptime(options['date']['date_to'], "%Y-%m-%d")

        if not date_from.year == date_to.year:
            raise UserError(_("Cannot generate a BOE file for two different years"))

        if date_from.day != 1 or date_to.day != (date_to + relativedelta(day=31)).day:
            raise UserError(_("Your date range does not cover entire months, please use a start and end date matching respectively the first and last day of a month."))

        rslt_period = None
        rslt_year = str(date_from.year) # Identical to date_to.year thanks to the previous conditions
        if date_from.month == date_to.month:
            rslt_period = '%02d' % (date_from.month)
        elif date_from.month == date_to.month - 2 and self._retrieve_period_and_year(date_from, trimester=True)[0] == self._retrieve_period_and_year(date_to, trimester=True)[0]:
            rslt_period = '%01dT' % (date_to.month / 3)
        # Period stays None otherwize, so we can use rslt_period == None to check if a trimester or year is selected

        return rslt_period, rslt_year

    def _retrieve_period_and_year(self, date, trimester=False):
        """ Retrieves the period and year (in the form of a tuple) corresponding
        to a given date.

        :param trimester: whether or not we use trimesters as periods.
        """
        if trimester:
            return '%01dT' % (1 + ((date.month - 1) // 3)), str(date.year)
        else:
            return '%02d' % date.month, str(date.year)

    def _convert_period_to_dates(self, period, year):
        """ Converts a period and a year to a tuple of two dates, respectively its
        start and end date.
        """
        if period[-1] == 'T':
            quarter = int(period[:-1])
            return datetime(day=1, month= 1 + (quarter - 1) * 3, year=int(year)), (datetime(day=1, month= quarter * 3, year=int(year)) + relativedelta(day=31)) # relativedelta used to force last day of the month without triggering ValueError for months with less than 31 days
        else:
            return datetime(day=1, month=int(period), year=int(year)), datetime(day=1, month=int(period), year=int(year)) + relativedelta(day=31)

    def get_txt(self, options):
        if not self.l10n_es_reports_modelo_number:
            return super(AEATAccountFinancialReport, self).get_txt(options)

        selected_company_ids = [data['id'] for data in options.get('multi_company', []) if data['selected']]
        if len(selected_company_ids) > 1:
            raise UserError(_("Cannot generate a BOE file for multiple companies at once. Please select only one."))

        if selected_company_ids:
            current_company = self.env['res.company'].browse(selected_company_ids)
        else:
            current_company = self.env.company

        period, year = self._get_mod_period_and_year(options)

        if not current_company.vat:
            raise UserError(_("Please first set the TIN of your company."))

        self = self.with_context(self._set_context(options))

        return getattr(self, '_boe_export_mod' + self.l10n_es_reports_modelo_number)(options, current_company, period, year)

    def _boe_format_string(self, string, length=-1, align='left', fill_char=b' '):
        """ Formats a string so that it is BOE-compatible.

        :param string: the string to format
        :param length: the desired length of the resulting string, or -1 if there is not
        :param align: 'left' or 'right', depending on the side of the result string where string must placed (no effect if no length is given)
        :param fill_char: the character that will be used to bring the result string to a size of length (no effect if length is not specified)
        """
        string = string.upper()

        rslt = b''
        for char in unicodedata.normalize('NFKC', string): # We use a normalized version of the string here so that we are sure accentuated charcaters are each time encoded with only one character (and not a regular character followed by a combining one)
            if not char in ('Ñ', 'Ç'):
                normalized_char = unicodedata.normalize('NFD', char) # Not NFKD, as the NFKC normalization in the loop already ensures good treatment of compatibility characters. NFD splits accentuated characters in two parts: the original character, and the accent to combine it with
                rslt += normalized_char.encode('ISO-8859-1', 'ignore') # Combinable accentuation characters are not supported by this encoding, and disappear when transcoding.
            else:
                rslt += char.encode('ISO-8859-1')

        if length > -1:
            rslt = rslt[:length]
            if align == 'left':
                rslt = rslt.ljust(length, fill_char)
            elif align =='right':
                rslt = rslt.rjust(length, fill_char)

        return rslt

    def _boe_format_number(self, number, length=-1, decimal_places=0, signed=False, sign_neg='N', sign_pos='', in_currency=False):
        """ Formats a number to a BOE-compatible string.

        :param number: the number to format
        :param length: the desired length for the resulting string, or -1, to just use the number of characters of the number.
        :param decimal_places: the number of decimal places to use (these characters are part of the length limit)
        :param signed: whether or not the number must be signed in the resulting string
        :param sign_neg: the character to use as the first character of the resulting string if signed is True and
                         the number was negative (the resulting string will contain no additional - sign)
        :param sign_pos: same as sign_neg, but if number is positive
        :param in_currency: True iff number is expressed in company currency (and thus needs to be converted in €)
        """
        company = self.env.company

        if in_currency:
            # If number is an amount expressed in company currency, we ensure that it
            # is written in € in BOE file
            conversion_date = self.env.context['l10n_es_reports_boe_conversion_date'] # This context key is set in _set_context
            number = company.currency_id._convert(number, self.env.ref('base.EUR'), company, conversion_date)

        if isinstance(number, float):
            split_number = float_split_str(abs(number), decimal_places)
            str_number = split_number[0] + split_number[1]
        else:
            str_number = str(abs(number))

        negative_amount = in_currency and company.currency_id.compare_amounts(number, 0.0)==-1 or number<0
        sign_str = signed and (negative_amount and sign_neg or sign_pos) or ''
        # Done in two parts, so that sign str is always in front of the filling characters
        return self._boe_format_string(sign_str) + self._boe_format_string(str_number, length=length - len(sign_str), align='right', fill_char=b'0')

    def _retrieve_casilla_lines(self, report_lines):
        """ Retrieves the values of the casillas contained in report_lines, using
        the fact that these lines' names are prefixed by their number between [] to
        identify them. Returns a dictionnary, with casillas as keys and their values
        as values.
        """
        casilla_pattern = re.compile(r'\[(?P<casilla>..).*\]')
        rslt = {}
        for line in report_lines:
            matcher = casilla_pattern.match(line['name'])
            if matcher:
                rslt[matcher.group('casilla')] = line['columns'][0]['no_format_name'] # Element [0] is the current period, in case we are comparing
        return rslt

    def _retrieve_report_line(self, options, xmlid):
        """ Retrieves the data of the report line denoted by xmlid, with respect
        to the given options.
        """
        line_id = self.env.ref(xmlid).id
        line_data = self._get_lines(options, line_id=line_id)[0]
        return line_data['columns'][0]['no_format_name']

    def get_bic_and_iban(self, res_partner_bank):
        """ Convenience method returning (bic,iban) of the given account if
        this account exists, or a tuple of empty strings otherwize.
        """
        if res_partner_bank:
            return res_partner_bank.bank_bic or "", res_partner_bank.sanitized_acc_number

        return '', ''

    def _retrieve_boe_manual_wizard(self, options):
        """ Retrieves a BOE manual wizard object from its id, contained within the
        options dict.
        """
        return self.env['l10n_es_reports.aeat.boe.mod' + self.l10n_es_reports_modelo_number + '.export.wizard'].browse(options['l10n_es_reports_boe_wizard_id'])

    def _call_on_sublines(self, report_options, line_xml_id, fun_to_call, required_ids_set=set()):
        """ Calls a function on the data of all the sublines generated by a
        groupby parameter for a report line (except the one giving the total).

        :param report_options: the options to use to generate line data
        :param line_xml_id: the xml id of the report line whose children we want to call our function on
        :param fun_to_call: the function to call on sublines. It must take only one argument, the data dictionary of the subline.
        :param required_ids_set: a set containing ids on which we want fun_to_call to be called.
                                 This is used to generate data for models that are not present
                                 in the grouped line displayed on the report. (this can for example
                                 happen if they have no operation in this year; but
                                 some data to be added into BOE make in necessary to still include
                                 them in the file). This set will be modified by the function.
        """
        rslt = self._boe_format_string('')
        report_line = self.env.ref(line_xml_id)
        for generated_line in self._get_lines(report_options, line_id=report_line.id):
            # We only treat sublines (excluding the 'total' line)
            if generated_line['id'] != 'total_'+str(report_line.id) and generated_line['level'] >= report_line.level and generated_line.get('caret_options') == 'partner_id':
                rslt += fun_to_call({'line_data': generated_line, 'line_xml_id': line_xml_id, 'report_options': report_options})
                if generated_line['id'] in required_ids_set:
                    required_ids_set.remove(generated_line['id'])

        for element in required_ids_set: # These elements are the ones for wich no line was generated, but that were into the original required ids set. So, we still treat them.
            rslt += fun_to_call({'line_data': {'id':element}, 'line_xml_id': line_xml_id, 'report_options': report_options})

        return rslt

    def _get_subline_data(self, report_options, line_xml_id, sub_line_id):
        """ Returns the data of a subline generated by a groupby parameter, if its
        'id' (i.e. the actual id of the model denote by groupby represented by the
        line) is equal to a given value.

        :param report_options: the options to use to generate data
        :param line_xml_id: the xml id of the parent line
        :param sub_line_id: the id of the "grouped by" model corresponding to the subline we want to retrieve
        """
        report_line = self.env.ref(line_xml_id)
        for generated_line in self._get_lines(report_options, line_id=report_line.id):
            if generated_line['id'] != 'total_'+str(report_line.id) and generated_line['level'] >= report_line.level and generated_line.get('caret_options') == 'partner_id' and generated_line['id'] == sub_line_id:
                return generated_line

    def _extract_tin(self, partner, error_if_no_tin=True):
        if not partner.vat:
            if error_if_no_tin:
                raise UserError(_("No TIN set for partner %s (id %d). Please define one.") % (partner.name, partner.id))
            else:
                return ''

        country_code, number = partner._split_vat(partner.vat)
        return country_code.upper() + number

    def _extract_spanish_tin(self, partner, except_if_foreign=False):
        formatted_tin = self._extract_tin(partner, error_if_no_tin=True)
        if formatted_tin[:2] != 'ES':
            if except_if_foreign:
                raise UserError(_("Reading a non-Spanish TIN as a Spanish TIN."))
            else:
                return ''
        return formatted_tin[2:]

    def _generate_111_115_common_header(self, options, current_company, period, year):
        rslt = b''

        # Wizard with manually-entered data
        boe_wizard = self._retrieve_boe_manual_wizard(options)

        # Header
        rslt += self._boe_format_string('<T' + self.l10n_es_reports_modelo_number + '0' + year + period + '0000>')
        rslt += self._boe_format_string('<AUX>')
        rslt += self._boe_format_string(' ' * 70) # Reserved for AEAT
        odoo_version = odoo.release.version.split('.')
        rslt += self._boe_format_string(str(odoo_version[0]) + str(odoo_version[1]), length=4)
        rslt += self._boe_format_string(' ' * 4) # Reserved for AEAT
        rslt += self._boe_format_string(self._extract_spanish_tin(current_company.partner_id), length=9)
        rslt += self._boe_format_string(' ' * 213) # Reserved for AEAT
        rslt += self._boe_format_string('</AUX>')

        # Fills in the common fields between mod 111 and 115
        rslt += self._boe_format_string('<T' + self.l10n_es_reports_modelo_number + '01000>')
        rslt += self._boe_format_string(' ')
        rslt += self._boe_format_string(boe_wizard.declaration_type)
        rslt += self._boe_format_string(self._extract_spanish_tin(current_company.partner_id), length=9)
        rslt += self._boe_format_string(current_company.name, length=60)
        rslt += self._boe_format_string(' ' * 20) # We keep the name of the declaring party blank here, as it is a company
        rslt += self._boe_format_string(year)
        rslt += self._boe_format_string(period)

        return rslt

    def _boe_export_mod111(self, options, current_company, period, year):
        if not period:
            raise UserError(_("Wrong report dates for BOE generation : please select a range of one month or a trimester."))

        rslt = self._generate_111_115_common_header(options, current_company, period, year)
        casilla_lines_map = self._retrieve_casilla_lines(self._get_lines(options))

        # Wizard with manually-entered data
        boe_wizard = self._retrieve_boe_manual_wizard(options)

        # Content of the report
        rslt += self._boe_format_number(casilla_lines_map['01'], length=8, signed=True)
        rslt += self._boe_format_number(casilla_lines_map['02'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['03'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['04'], length=8, signed=True)
        rslt += self._boe_format_number(casilla_lines_map['05'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['06'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['07'], length=8, signed=True)
        rslt += self._boe_format_number(casilla_lines_map['08'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['09'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['10'], length=8, signed=True)
        rslt += self._boe_format_number(casilla_lines_map['11'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['12'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['13'], length=8, signed=True)
        rslt += self._boe_format_number(casilla_lines_map['14'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['15'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['16'], length=8, signed=True)
        rslt += self._boe_format_number(casilla_lines_map['17'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['18'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['19'], length=8, signed=True)
        rslt += self._boe_format_number(casilla_lines_map['20'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['21'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['22'], length=8, signed=True)
        rslt += self._boe_format_number(casilla_lines_map['23'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['24'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['25'], length=8, signed=True)
        rslt += self._boe_format_number(casilla_lines_map['26'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['27'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['28'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['29'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['30'], length=17, decimal_places=2, signed=True, in_currency=True)

        rslt += self._boe_format_string(boe_wizard.complementary_declaration and 'X' or ' ')
        rslt += self._boe_format_string(boe_wizard.complementary_declaration and boe_wizard.previous_report_number or '', length=13)
        rslt += self._boe_format_string(' ') # Reserved for AEAT
        bic, iban = self.get_bic_and_iban(boe_wizard.partner_bank_id)
        rslt += self._boe_format_string(iban, length=34)
        rslt += self._boe_format_string(' ' * 389) # Reserved for AEAT
        rslt += self._boe_format_string(' ' * 13) # Reserved for AEAT

        # We close the tags... (They have been opened by _generate_111_115_common_header)
        rslt += self._boe_format_string('</T11101000>')
        rslt += self._boe_format_string('</T1110' + year + period + '0000>')

        return rslt

    def _boe_export_mod115(self, options, current_company, period, year):
        if not period:
            raise UserError(_("Wrong report dates for BOE generation : please select a range of one month or a trimester."))

        rslt = self._generate_111_115_common_header(options, current_company, period, year)
        casilla_lines_map = self._retrieve_casilla_lines(self._get_lines(options))

        # Wizard with manually-entered data
        boe_wizard = self._retrieve_boe_manual_wizard(options)

        # Content of the report
        rslt += self._boe_format_number(casilla_lines_map['01'], length=15, signed=True)
        rslt += self._boe_format_number(casilla_lines_map['02'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['03'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['04'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['05'], length=17, decimal_places=2, signed=True, in_currency=True)

        rslt += self._boe_format_string(boe_wizard.complementary_declaration and 'X' or ' ')
        rslt += self._boe_format_string(boe_wizard.complementary_declaration and boe_wizard.previous_report_number or '', length=13)
        bic, iban = self.get_bic_and_iban(boe_wizard.partner_bank_id)
        rslt += self._boe_format_string(iban, length=34)
        rslt += self._boe_format_string(' ' * 236) # Reserved for AEAT
        rslt += self._boe_format_string(' ' * 13) # Reserved for AEAT

        # We close the tags... (They have been opened by _generate_111_115_common_header)
        rslt += self._boe_format_string('</T11501000>')
        rslt += self._boe_format_string('</T1150' + year + period + '0000>')

        return rslt

    def _boe_export_mod303(self, options, current_company, period, year):
        if not period:
            raise UserError(_("Wrong report dates for BOE generation : please select a range of one month or a trimester."))

        casilla_lines_map = self._retrieve_casilla_lines(self._get_lines(options))
        # Header
        rslt = self._boe_format_string('<T3030' + year + period + '0000>')
        rslt += self._boe_format_string('<AUX>')
        rslt += self._boe_format_string(' ' * 70)
        odoo_version = odoo.release.version.split('.')
        rslt += self._boe_format_string(str(odoo_version[0]) + str(odoo_version[1]), length=4)
        rslt += self._boe_format_string(' ' * 4)
        rslt += self._boe_format_string(self._extract_spanish_tin(current_company.partner_id), length=9)
        rslt += self._boe_format_string(' ' * 213)
        rslt += self._boe_format_string('</AUX>')

        rslt += self._generate_mod_303_page1(options, current_company, period, year, casilla_lines_map)
        rslt += self._generate_mod_303_page3(options, current_company, period, year, casilla_lines_map)
        # We don't need page 2 and 4 (specified in AEAT doc)

        # We close the tags...
        rslt += self._boe_format_string('</T3030' + year + period + '0000>')

        return rslt

    def _generate_mod_303_page1(self, options, current_company, period, year, casilla_lines_map):
        # Wizard with manually-entered data
        boe_wizard = self._retrieve_boe_manual_wizard(options)

        rslt = self._boe_format_string('<T30301000>')
        rslt += self._boe_format_string(' ')
        rslt += self._boe_format_string(boe_wizard.declaration_type)
        rslt += self._boe_format_string(self._extract_spanish_tin(current_company.partner_id), length=9)
        rslt += self._boe_format_string(current_company.name, length=60)
        rslt += self._boe_format_string(' ' * 20) # We keep the name of the declaring party blank here, as it is a company
        rslt += self._boe_format_string(year)
        rslt += self._boe_format_string(period)
        rslt += self._boe_format_number(boe_wizard.monthly_return and 1 or 2)

        # Identification (everything is constant in our case)
        rslt += self._boe_format_number(3)
        rslt += self._boe_format_number(2)
        rslt += self._boe_format_number(2)
        rslt += self._boe_format_string(' ' * 8)
        rslt += self._boe_format_string(' ')
        rslt += self._boe_format_number(2)
        rslt += self._boe_format_number(2)
        rslt += self._boe_format_number(2)
        rslt += self._boe_format_number(2)

        # Casillas
        rslt += self._boe_format_number(casilla_lines_map['01'], length=17, decimal_places=2, in_currency=True)
        rslt += self._boe_format_number(400, length=5) # Casilla 02 is constant
        rslt += self._boe_format_number(casilla_lines_map['03'], length=17, decimal_places=2, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['04'], length=17, decimal_places=2, in_currency=True)
        rslt += self._boe_format_number(1000, length=5) # Casilla 05 is constant
        rslt += self._boe_format_number(casilla_lines_map['06'], length=17, decimal_places=2, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['07'], length=17, decimal_places=2, in_currency=True)
        rslt += self._boe_format_number(2100, length=5) # Casilla 08 is constant
        rslt += self._boe_format_number(casilla_lines_map['09'], length=17, decimal_places=2, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['10'], length=17, decimal_places=2, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['11'], length=17, decimal_places=2, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['12'], length=17, decimal_places=2, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['13'], length=17, decimal_places=2, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['14'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['15'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['16'], length=17, decimal_places=2, in_currency=True)
        rslt += self._boe_format_number(50, length=5) # Casilla 17 is constant
        rslt += self._boe_format_number(casilla_lines_map['18'], length=17, decimal_places=2, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['19'], length=17, decimal_places=2, in_currency=True)
        rslt += self._boe_format_number(140, length=5) # Casilla 20 is constant
        rslt += self._boe_format_number(casilla_lines_map['21'], length=17, decimal_places=2, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['22'], length=17, decimal_places=2, in_currency=True)
        rslt += self._boe_format_number(520, length=5) # Casilla 23 is constant
        rslt += self._boe_format_number(casilla_lines_map['24'], length=17, decimal_places=2, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['25'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['26'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['27'], length=17, decimal_places=2, signed=True, in_currency=True)

        for casilla in range(28, 39):
            rslt += self._boe_format_number(casilla_lines_map[str(casilla)], length=17, decimal_places=2, in_currency=True)

        for casilla in range(40, 46):
            rslt += self._boe_format_number(casilla_lines_map[str(casilla)], length=17, decimal_places=2, signed=True, in_currency=True)

        # Footer of page 1
        rslt += self._boe_format_string(' ' * 582) # Reserved for AEAT
        rslt += self._boe_format_string(' ' * 13) # Reserved for AEAT
        rslt += self._boe_format_string('</T30301000>')

        return rslt

    def _generate_mod_303_page3(self, options, current_company, period, year, casilla_lines_map):
        rslt = self._boe_format_string('<T30303000>')

        # Wizard with manually-entered data
        boe_wizard = self._retrieve_boe_manual_wizard(options)

        # Casillas
        for casilla in range(59, 63):
            rslt += self._boe_format_number(casilla_lines_map[str(casilla)], length=17, decimal_places=2, signed=True, in_currency=True)

        rslt += self._boe_format_number(casilla_lines_map['74'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['75'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(0, length=17)
        rslt += self._boe_format_number(casilla_lines_map['46'], length=17, decimal_places=2, signed=True, in_currency=True) # Should normally be casilla 64 (= sum of casillas 46, 58 and 76), but only casilla 46 is in our version of the report
        rslt += self._boe_format_number(casilla_lines_map['65'], length=9, decimal_places=6)
        rslt += self._boe_format_number(casilla_lines_map['66'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['77'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['67'], length=17, decimal_places=2, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['68'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['69'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['70'], length=17, decimal_places=2, signed=True, in_currency=True)
        rslt += self._boe_format_number(casilla_lines_map['71'], length=17, decimal_places=2, signed=True, in_currency=True)

        # Information about declaration
        rslt += self._boe_format_string(boe_wizard.complementary_declaration and 'X' or ' ')
        rslt += self._boe_format_string(boe_wizard.complementary_declaration and boe_wizard.previous_report_number or '', length=13)
        rslt += self._boe_format_string(casilla_lines_map['71'] == 0 and 'X' or ' ')
        bic, iban = self.get_bic_and_iban(boe_wizard.partner_bank_id)
        rslt += self._boe_format_string(bic, length=11)
        rslt += self._boe_format_string(iban, length=34)

        # "Información adicional" (everything is empty)
        rslt += self._boe_format_number(0)
        rslt += self._boe_format_string(' ' * 4)
        rslt += self._boe_format_number(0)
        rslt += self._boe_format_string(' ' * 4)
        rslt += self._boe_format_number(0)
        rslt += self._boe_format_string(' ' * 4)
        rslt += self._boe_format_number(0)
        rslt += self._boe_format_string(' ' * 4)
        rslt += self._boe_format_number(0)
        rslt += self._boe_format_string(' ' * 4)
        rslt += self._boe_format_number(0)
        rslt += self._boe_format_string(' ' * 4)
        rslt += self._boe_format_string(' ')
        rslt += self._boe_format_number(0, length=17)
        rslt += self._boe_format_number(0, length=17)
        rslt += self._boe_format_number(0, length=17)
        rslt += self._boe_format_number(0, length=17)
        rslt += self._boe_format_number(0, length=17)
        rslt += self._boe_format_number(0, length=17)
        rslt += self._boe_format_number(0, length=17)
        rslt += self._boe_format_number(0, length=17)
        rslt += self._boe_format_number(0, length=17)
        rslt += self._boe_format_number(0)

        # Footer of page 3
        rslt += self._boe_format_string(' ' * 590) # Reserved for AEAT
        rslt += self._boe_format_string('</T30303000>')

        return rslt

    def _boe_export_mod347(self, options, current_company, period, year):
        # Report options to use to retrieve data for the BOE
        boe_report_options = self._mod347_build_boe_report_options(options, year)

        # Wizard with manually-entered data
        boe_wizard = self._retrieve_boe_manual_wizard(options)

        manual_params = boe_wizard.get_partners_manual_parameters_map()

        # Header
        self = self.with_context(self._set_context(boe_report_options))

        rslt = self._mod347_write_type2_header_record(current_company, boe_wizard, boe_report_options)

        seguros_required_b = self._mod347_get_required_partner_ids_for_boe('insurance', year+'-01-01', year+'-12-31', boe_wizard, 'B', 'seguros')
        rslt += self._call_on_sublines(boe_report_options, 'l10n_es_reports.mod_347_operations_insurance_bought', lambda report_data: self._mod347_write_type2_partner_record(report_data, year, current_company, 'B', manual_parameters_map=manual_params, insurance=True), required_ids_set=seguros_required_b)

        otras_required_a = self._mod347_get_required_partner_ids_for_boe('regular', year+'-01-01', year+'-12-31', boe_wizard, 'A', 'otras')
        rslt += self._call_on_sublines(boe_report_options, 'l10n_es_reports.mod_347_operations_regular_sold', lambda report_data: self._mod347_write_type2_partner_record(report_data, year, current_company, 'A', manual_parameters_map=manual_params), required_ids_set=otras_required_a)

        otras_required_b = self._mod347_get_required_partner_ids_for_boe('regular', year+'-01-01', year+'-12-31', boe_wizard, 'B', 'otras')
        rslt += self._call_on_sublines(boe_report_options, 'l10n_es_reports.mod_347_operations_regular_bought', lambda report_data: self._mod347_write_type2_partner_record(report_data, year, current_company, 'B', manual_parameters_map=manual_params), required_ids_set=otras_required_b)

        return rslt

    def _mod347_build_boe_report_options(self, options, year):
        boe_report_options = options.copy()
        boe_report_options['date'] = {'filter': 'this_quarter', 'string': 'Q4 '+year, 'date_from': year+'-10-01', 'date_to': year+'-12-31'}
        boe_report_options['comparison'] = {'date_to': year+'-09-30',
                                 'periods': [{'date_to': year+'-09-30', 'date_from': year+'-07-01', 'string': 'Q3 '+year},
                                             {'date_to': year+'-06-30', 'date_from': year+'-04-01', 'string': 'Q2 '+year},
                                             {'date_to': year+'-03-31', 'date_from': year+'-01-01', 'string': 'Q1 '+year}],
                                 'number_period': 3, 'string': 'Q3 '+year, 'filter': 'previous_period', 'date_from': year+'-07-01'}
        return boe_report_options

    def _mod347_get_required_partner_ids_for_boe(self, mod_invoice_type, date_from, date_to, boe_wizard, operation_key, operation_class):
        cash_basis_manual_data = boe_wizard.cash_basis_mod347_data.filtered(lambda x: x.operation_key == operation_key and x.operation_class == operation_class)
        all_partners = cash_basis_manual_data.mapped('partner_id')

        if operation_key == 'A': # Only for perceived amounts
            # If invoice is not in the current period but cash payment is,
            # we need to inject the partner into BOE so that this cash amount is reported
            cash_payments_aml = self.env['account.partial.reconcile'].search([('credit_move_id.date', '<=' ,date_to),
                                                                              ('credit_move_id.date', '>=', date_from),
                                                                              ('credit_move_id.journal_id.type', '=', 'cash'),
                                                                              ('debit_move_id.move_id.l10n_es_reports_mod347_invoice_type', '=', mod_invoice_type),
                                                                              ('credit_move_id.account_id.user_type_id', '=', self.env.ref('account.data_account_type_receivable').id),
                                                                            ])
            all_partners += cash_payments_aml.mapped('credit_move_id.partner_id')

        return set(all_partners.ids)

    def _mod347_write_type2_header_record(self, current_company, boe_wizard, boe_report_options):
        rslt = self._boe_format_number(1)
        rslt += self._boe_format_number(347)
        rslt += self._boe_format_string(self._extract_spanish_tin(current_company.partner_id), length=9)
        rslt += self._boe_format_string(current_company.name, length=40)
        rslt += self._boe_format_string('T')
        rslt += self._boe_format_string(boe_wizard.get_formatted_contact_phone(), length=9)
        rslt += self._boe_format_string(boe_wizard.contact_person_name, length= 40)
        mod_347_boe_sequence = self.env['ir.sequence'].search([('company_id','=',current_company.id), ('code','=','l10n_es.boe.mod_347')])
        rslt += self._boe_format_string(mod_347_boe_sequence.next_by_id(), length=13)
        rslt += self._boe_format_string(boe_wizard.complementary_declaration and 'X' or ' ')
        rslt += self._boe_format_string(boe_wizard.substitutive_declaration and 'X' or ' ')
        rslt += self._boe_format_string(boe_wizard.previous_report_number or '', length=13)

        declarados_count_line_data = self._get_lines(boe_report_options, line_id=self.env.ref('l10n_es_reports.mod_347_statistics_operations_count').id)[0]
        rslt += self._boe_format_number(sum(i['no_format_name'] for i in declarados_count_line_data['columns']), length=9)

        declarados_total_line_data = self._get_lines(boe_report_options, line_id=self.env.ref('l10n_es_reports.mod_347_operations_title').id)[-1] #Index -1 to get the line containing the total
        declarados_total = sum(i['no_format_name'] for i in declarados_total_line_data['columns'])
        rslt += self._boe_format_number(declarados_total, length=16, decimal_places=2, signed=True, sign_pos=' ', in_currency=True)

        real_estates_data = self._mod347_get_real_estates_data(boe_report_options, current_company.currency_id)
        rslt += self._boe_format_number(real_estates_data['count'], length=9)

        rslt += self._boe_format_number(real_estates_data['total'], length=15, decimal_places=2, signed=True, sign_pos=' ', in_currency=True)

        rslt += self._boe_format_string(' ' * 205)
        rslt += self._boe_format_string(' ' * 9) # TIN of the legal representant; blank if 14 years or older
        rslt += self._boe_format_string(' ' * 88)
        rslt += self._boe_format_string(' ' * 13) # "Sello Electronico" => for administration

        return rslt

    def _mod347_get_real_estates_data(self, boe_report_options, currency_id):
        """ Real estates are not directly supported by l10n_es_reports, but by the
        submodule l10n_es_real_estates. This function is used as a hook, so that we
        don't have to access the result of _mod347_write_type2_header_record by indexes
        in order to write the real estates data at the right place in the BOE
        (which is better in case the code of the header function needs to be extended).
        """
        return {'count': 0, 'total': 0}


    def _mod347_write_type2_partner_record(self, report_data, year, current_company, operation_key, manual_parameters_map, insurance=False, local_negocio=False):
        currency_id = current_company.currency_id
        line_partner = self.env['res.partner'].browse(report_data['line_data']['id'])

        rslt = self._boe_format_number(2)
        rslt += self._boe_format_number(347)
        rslt += self._boe_format_string(year, length=4)
        rslt += self._boe_format_string(self._extract_spanish_tin(current_company.partner_id), length=9)
        rslt += self._boe_format_string(line_partner.country_id.code == 'ES' and self._extract_spanish_tin(line_partner) or '', length=9)
        rslt += self._boe_format_string(line_partner.display_name, length=40)
        rslt += self._boe_format_string('D') # 'Tipo de hoja', constant

        province_code = line_partner.state_id and SPANISH_PROVINCES_REPORT_CODES.get(line_partner.state_id.code) or '99'
        rslt += self._boe_format_string(province_code, length=2)
        # The country code is only mandatory if there is no province code (hence: no head office in Spain)
        if province_code == '99' and (not line_partner.country_id or not line_partner.country_id.code):
            raise UserError(_("Partner with %s (id %d) is not associated to any Spanish province, and should hence have a country code. For this, fill in its 'country' field.") % (line_partner.name, line_partner.id))

        rslt += self._boe_format_string(line_partner.country_id.code, length=2)
        rslt += self._boe_format_string(' ') # Constant
        rslt += self._boe_format_string(operation_key, length=1)

        # Total amount of operations over the year
        year_operations_sum = currency_id.round(sum(i['no_format_name'] for i in report_data['line_data'].get('columns', [])))
        rslt += self._boe_format_number(year_operations_sum, length=16, decimal_places=2, signed=True, sign_pos=' ', in_currency=True)

        rslt += self._boe_format_string(insurance and 'X' or ' ')
        rslt += self._boe_format_string(local_negocio and 'X' or ' ')

        # En metálico
        report_line = self.env.ref(report_data['line_xml_id'])
        evaluated_domain = safe_eval(report_line.domain)

        # We search for current invoice type in the parent line's domain
        current_invoice_type = None
        for domain_tuple in evaluated_domain:
            if domain_tuple[0] == 'move_id.l10n_es_reports_mod347_invoice_type' and domain_tuple[1] == '=':
                current_invoice_type = domain_tuple[2]
                break

        user_type_id = operation_key == 'A' and self.env.ref('account.data_account_type_receivable').id or self.env.ref('account.data_account_type_payable').id
        matching_field = operation_key == 'A' and 'debit' or 'credit'
        cash_payments_lines_in_period = self.env['account.move.line'].search([('date','<=',year+'-12-31'), ('date','>=',year+'-01-01'), ('journal_id.type','=','cash'), ('payment_id','!=',False), ('partner_id','=',line_partner.id), ('account_id.user_type_id','=',user_type_id), ('company_id','=',current_company.id)])
        metalico_amount = 0
        for cash_payment_aml in cash_payments_lines_in_period:
                partial_reconcile_ids = getattr(cash_payment_aml, 'matched_' + matching_field + '_ids')
                partial_rec_on_inv_type = partial_reconcile_ids.filtered(lambda x: getattr(x, matching_field + '_move_id').move_id.l10n_es_reports_mod347_invoice_type == current_invoice_type)
                for partial_rec in partial_rec_on_inv_type:
                    metalico_amount += partial_rec.amount

        # Context key used for conversion date is set in get_txt.
        threshold = self.env.ref('base.EUR')._convert(6000, currency_id, current_company, self.env.context['l10n_es_reports_boe_conversion_date'])
        if currency_id.compare_amounts(metalico_amount, threshold) == 1: # We only must report this amount if it is above 6000 €
            rslt += self._boe_format_number(metalico_amount, length=15, decimal_places=2, in_currency=True)
        else:
            rslt += self._boe_format_number(0, length=15)

        # Inmuebles sujetas a la IVA
        operation_class = insurance and 'seguros' or local_negocio and 'local_negocio' or 'otras'
        real_estates_vat_year_total = 0
        real_estates_vat_by_trimester = []
        for trimester in range(1, 5):
            # This module does not support real estates on its own, but we give the possibility
            # to add a real_estates_vat key to the manual parameters map with the needed data,
            # through anoter module (l10n_es_real_estates does that)
            real_estates_vat_partner_dict = manual_parameters_map.get('real_estates_vat', {}).get(line_partner.id)
            real_estates_vat_amount = real_estates_vat_partner_dict and real_estates_vat_partner_dict[str(trimester)][operation_class][operation_key] or 0
            real_estates_vat_year_total += real_estates_vat_amount
            real_estates_vat_by_trimester.append(real_estates_vat_amount)

        real_estates_vat_year_total = currency_id.round(real_estates_vat_year_total)
        rslt += self._boe_format_number(real_estates_vat_year_total, length=16, decimal_places=2, signed=True, sign_pos=' ', in_currency=True)

        rslt += self._boe_format_string(year, length=4)

        for trimester in range(1, 4):
            trimester_total = report_data['line_data'].get('columns', [{} for i in range(1,4)])[-trimester].get('no_format_name',0)
            rslt += self._boe_format_number(trimester_total, length=16, decimal_places=2, signed=True, sign_pos=' ', in_currency=True)
            rslt += self._boe_format_number(real_estates_vat_by_trimester[trimester], length=16, decimal_places=2, signed=True, sign_pos=' ', in_currency=True)

        # 'NIF Operador Comunitario'
        europe_countries = self.env.ref('base.europe').country_ids
        intracom_tin = ''
        if line_partner.country_id in europe_countries:
            partner_tin = self._extract_tin(line_partner, error_if_no_tin=False)
            intracom_tin = (partner_tin[:2]!='es') and partner_tin or ''# We write an empty string if the partner has a Spanish TIN (because it then has already been written previously)
        rslt += self._boe_format_string(intracom_tin.upper(), length=17)

        # Cash Basis (Regimen Especial de Caja)
        cash_basis_partner = manual_parameters_map['cash_basis'].get(line_partner.id)
        cash_basis_data = cash_basis_partner and cash_basis_partner[operation_class][operation_key] or None
        rslt += self._boe_format_string(cash_basis_data != None and 'X' or ' ')

        rslt += self._boe_format_string(line_partner == current_company.partner_id and 'X' or ' ')

        rslt += self._boe_format_string(' ') # Not supported by Odoo; according to the partners, too few people need this option

        rslt += self._boe_format_number(cash_basis_data or 0, length=16, decimal_places=2, signed=True, sign_pos=' ', in_currency=True)

        rslt += self._boe_format_string(' ' * 201)

        return rslt

    def _boe_export_mod349(self, options, current_company, period, year):
        if not period:
            raise UserError(_("Wrong report dates for BOE generation : please select a range of one month or a trimester."))

        # Wizard with manually-entered data
        boe_wizard = self._retrieve_boe_manual_wizard(options)

        rslt = self._boe_format_string('')

        if boe_wizard.trimester_2months_report:
            if period[-1] == 'T':
                options = options.copy()
                end_date = datetime.strptime(options['date']['date_to'], '%Y-%m-%d')
                options['date']['date_to'] = (end_date + relativedelta(day=31, months=-1)).strftime('%Y-%m-%d')
            else:
                raise UserError(_("You cannot generate a BOE file for the first two months of a trimester if only one month is selected!"))

        # Header
        rslt = self._mod_349_write_type1_header_record(options, period, year, current_company, boe_wizard)

        # Invoices lines
        rslt += self._call_on_sublines(options, 'l10n_es_reports.mod_349_supplies', lambda report_data: self._mod_349_write_type2_invoice_record(report_data, year, 'E', current_company))
        rslt += self._call_on_sublines(options, 'l10n_es_reports.mod_349_acquisitions', lambda report_data: self._mod_349_write_type2_invoice_record(report_data, year, 'A', current_company))
        rslt += self._call_on_sublines(options, 'l10n_es_reports.mod_349_triangular', lambda report_data: self._mod_349_write_type2_invoice_record(report_data, year, 'T', current_company))
        rslt += self._call_on_sublines(options, 'l10n_es_reports.mod_349_services_sold', lambda report_data: self._mod_349_write_type2_invoice_record(report_data, year, 'S', current_company))
        rslt += self._call_on_sublines(options, 'l10n_es_reports.mod_349_services_acquired', lambda report_data: self._mod_349_write_type2_invoice_record(report_data, year, 'I', current_company))
        rslt += self._call_on_sublines(options, 'l10n_es_reports.mod_349_supplies_without_taxes', lambda report_data: self._mod_349_write_type2_invoice_record(report_data, year, 'M', current_company))
        rslt += self._call_on_sublines(options, 'l10n_es_reports.mod_349_supplies_without_taxes_legal_representative', lambda report_data: self._mod_349_write_type2_invoice_record(report_data, year, 'H', current_company))

        # Refunds lines
        rslt += self._call_on_sublines(options, 'l10n_es_reports.mod_349_supplies_refunds', lambda report_data: self._mod_349_write_type2_refund_records(options, report_data, current_company, 'E', 'l10n_es_reports.mod_349_supplies'))
        rslt += self._call_on_sublines(options, 'l10n_es_reports.mod_349_acquisitions_refunds', lambda report_data: self._mod_349_write_type2_refund_records(options, report_data, current_company, 'A', 'l10n_es_reports.mod_349_acquisitions'))
        rslt += self._call_on_sublines(options, 'l10n_es_reports.mod_349_triangular_refunds', lambda report_data: self._mod_349_write_type2_refund_records(options, report_data, current_company, 'T', 'l10n_es_reports.mod_349_triangular'))
        rslt += self._call_on_sublines(options, 'l10n_es_reports.mod_349_services_sold_refunds', lambda report_data: self._mod_349_write_type2_refund_records(options, report_data, current_company, 'S', 'l10n_es_reports.mod_349_services_sold'))
        rslt += self._call_on_sublines(options, 'l10n_es_reports.mod_349_services_acquired_refunds', lambda report_data: self._mod_349_write_type2_refund_records(options, report_data, current_company, 'I', 'l10n_es_reports.mod_349_services_acquired'))
        rslt += self._call_on_sublines(options, 'l10n_es_reports.mod_349_supplies_without_taxes_refunds', lambda report_data: self._mod_349_write_type2_refund_records(options, report_data, current_company, 'M', 'l10n_es_reports.mod_349_supplies_without_taxes'))
        rslt += self._call_on_sublines(options, 'l10n_es_reports.mod_349_supplies_without_taxes_legal_representative_refunds', lambda report_data: self._mod_349_write_type2_refund_records(options, report_data, current_company, 'H', 'l10n_es_reports.mod_349_supplies_without_taxes_legal_representative'))

        return rslt

    def _mod_349_write_type1_header_record(self, options, period, year, current_company, boe_wizard):
        rslt = self._boe_format_string('1349')
        rslt += self._boe_format_string(year, length=4)
        rslt += self._boe_format_string(self._extract_spanish_tin(current_company.partner_id), length=9)
        rslt += self._boe_format_string(current_company.name, length=40)
        rslt += self._boe_format_string('T')
        rslt += self._boe_format_string(boe_wizard.get_formatted_contact_phone(), length=9)
        rslt += self._boe_format_string(boe_wizard.contact_person_name, length=40)
        mod_349_boe_sequence = self.env['ir.sequence'].search([('company_id','=',current_company.id), ('code','=','l10n_es.boe.mod_349')])
        rslt += self._boe_format_string(mod_349_boe_sequence.next_by_id(), length=13)
        rslt += self._boe_format_string(boe_wizard.complementary_declaration and 'X' or ' ')
        rslt += self._boe_format_string(boe_wizard.substitutive_declaration and 'X' or ' ')
        rslt += self._boe_format_string(boe_wizard.previous_report_number or '', length=13)
        rslt += self._boe_format_string(period, length=2)
        rslt += self._boe_format_number(self._retrieve_report_line(options, 'l10n_es_reports.mod_349_statistics_invoices_partners_count'), length=9)
        rslt += self._boe_format_number(self._retrieve_report_line(options, 'l10n_es_reports.mod_349_statistics_invoices_total_amount'), length=15, in_currency=True, decimal_places=2)
        rslt += self._boe_format_number(self._retrieve_report_line(options, 'l10n_es_reports.mod_349_statistics_refunds_partners_count'), length=9)
        rslt += self._boe_format_number(self._retrieve_report_line(options, 'l10n_es_reports.mod_349_statistics_refunds_total_amount'), length=15, in_currency=True, decimal_places=2)
        rslt += self._boe_format_string(boe_wizard.trimester_2months_report and 'X' or ' ')
        rslt += self._boe_format_string(' ' * 204)
        rslt += self._boe_format_string(' ' * 9) # TIN of the legal representative, if under 14 years old
        rslt += self._boe_format_string(' ' * 101) # Constant

        return rslt

    def _mod_349_write_type2_invoice_record(self, report_data, year, key, current_company):
        line_partner = self.env['res.partner'].browse(report_data['line_data']['id'])
        rslt = self._boe_format_string('2349')
        rslt += self._boe_format_string(year, length=4)
        rslt += self._boe_format_string(self._extract_spanish_tin(current_company.partner_id), length=9)
        rslt += self._boe_format_string(' ' * 58)
        rslt += self._boe_format_string(self._extract_tin(line_partner), length=17)
        rslt += self._boe_format_string(line_partner.name, length=40)
        rslt += self._boe_format_string(key, length=1)
        rslt += self._boe_format_number(report_data['line_data']['columns'][0]['no_format_name'], length=13, decimal_places=2, in_currency=True)
        rslt += self._boe_format_string(' ' * 354)

        return rslt

    def _mod_349_write_type2_refund_records(self, options, report_data, current_company, mod_349_type, invoice_report_line_xml_id):
        line_partner = self.env['res.partner'].browse(report_data['line_data']['id'])
        report_date_from = options['date']['date_from']
        report_date_to = options['date']['date_to']
        report_period, report_year = self._get_mod_period_and_year(options)

        rslt = self._boe_format_string('')
        for refund_invoice in self.env['account.move'].search([('date', '<=', report_date_to), ('date', '>=', report_date_from), ('type', 'in', ['in_refund', 'out_refund']), ('l10n_es_reports_mod349_invoice_type', '=', mod_349_type), ('partner_id', '=', line_partner.id)]):
            original_invoice = refund_invoice.reversed_entry_id
            invoice_period, invoice_year = self._retrieve_period_and_year(original_invoice.date, trimester=report_period[-1] == 'T')
            group_key = (invoice_period, invoice_year, refund_invoice.l10n_es_reports_mod349_invoice_type)

            # We compute the total refund for this invoice until the current period
            all_previous_refunds = self.env['account.move'].search([('reversed_entry_id', '=', original_invoice.id), ('date', '<=', report_date_to)])
            total_refund = sum(all_previous_refunds.mapped('amount_total'))

            # Compute invoice report line at the time of the original invoice
            line_options = options.copy()
            line_date_from, line_date_to = self._convert_period_to_dates(invoice_period, invoice_year)
            line_options['date']['date_from'] =  datetime.strftime(line_date_from, '%Y-%m-%d')
            line_options['date']['date_to'] =  datetime.strftime(line_date_to, '%Y-%m-%d')

            invoice_line_data = self._get_subline_data(line_options, invoice_report_line_xml_id, line_partner.id)
            previous_report_amount = invoice_line_data['columns'][0]['no_format_name']

            # Now, we can report the record !
            rslt += self._boe_format_string('2349')
            rslt += self._boe_format_string(report_year, length=4)
            rslt += self._boe_format_string(self._extract_spanish_tin(current_company.partner_id), length=9)
            rslt += self._boe_format_string(' ' * 58)
            rslt += self._boe_format_string(self._extract_tin(line_partner), length=17)
            rslt += self._boe_format_string(line_partner.name, length=40)
            rslt += self._boe_format_string(mod_349_type, length=1)
            rslt += self._boe_format_string(' ' * 13) # Constant
            rslt += self._boe_format_string(invoice_year, length=4)
            rslt += self._boe_format_string(invoice_period, length=2)
            rslt += self._boe_format_number(current_company.currency_id.round(previous_report_amount - total_refund), length=13, decimal_places=2, in_currency=True)
            rslt += self._boe_format_number(previous_report_amount, length=13, decimal_places=2, in_currency=True)
            rslt += self._boe_format_string(' ' * 322)

        return rslt
