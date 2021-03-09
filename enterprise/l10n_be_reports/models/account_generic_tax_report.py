from odoo import models, api, fields, _
from odoo.exceptions import UserError
from odoo.addons.web.controllers.main import clean_action
import calendar


class AccountTaxReportActivity(models.Model):
    _inherit = "mail.activity"

    def _get_vat_report_action_to_open(self, company_id):
        if company_id.country_id.code == 'BE':
            return self.env.ref('l10n_be_reports.action_account_report_be_vat').read()[0]
        else:
            return super(AccountTaxReportActivity, self)._get_vat_report_action_to_open(company_id)


class AccountGenericTaxReport(models.AbstractModel):
    _inherit = 'account.generic.tax.report'

    def _get_reports_buttons(self):
        buttons = super(AccountGenericTaxReport, self)._get_reports_buttons()
        if self.env.company.country_id.code == 'BE':
            buttons += [{'name': _('Export (XML)'), 'sequence': 3, 'action': 'l10n_be_print_xml', 'file_export_type': _('XML')}]
        return buttons

    def l10n_be_print_xml(self, options):
        # add options to context and return action to open transient model
        ctx = self.env.context.copy()
        ctx['l10n_be_reports_generation_options'] = options
        new_wizard = self.env['l10n_be_reports.periodic.vat.xml.export'].create({})
        view_id = self.env.ref('l10n_be_reports.view_account_financial_report_export').id
        return {
            'name': _('XML Export Options'),
            'view_mode': 'form',
            'views': [[view_id, 'form']],
            'res_model': 'l10n_be_reports.periodic.vat.xml.export',
            'type': 'ir.actions.act_window',
            'res_id': new_wizard.id,
            'target': 'new',
            'context': ctx,
            }

    def get_xml(self, options):
        # Check
        if self.env.company.country_id.code != 'BE':
            return super(AccountGenericTaxReport, self).get_xml(options)
        company = self.env.company
        if not company.partner_id.vat:
            raise UserError(_('No VAT number associated with your company.'))
        vat_no, country_from_vat = self._check_vat_number(company.partner_id.vat)

        default_address = company.partner_id.address_get()
        address = self.env['res.partner'].browse(default_address.get("default")) or company.partner_id
        if not address.email:
            raise UserError(_('No email address associated with the company.'))
        if not address.phone:
            raise UserError(_('No phone associated with the company.'))

        # Compute xml

        default_address = company.partner_id.address_get()
        address = self.env['res.partner'].browse(default_address.get("default", company.partner_id.id))

        issued_by = vat_no
        dt_from = options['date'].get('date_from')
        dt_to = options['date'].get('date_to')
        send_ref = str(company.partner_id.id) + str(dt_from[5:7]) + str(dt_to[:4])
        starting_month = dt_from[5:7]
        ending_month = dt_to[5:7]
        quarter = str(((int(starting_month) - 1) // 3) + 1)

        date_from = dt_from[0:7] + '-01'
        date_to = dt_to[0:7] + '-' + str(calendar.monthrange(int(dt_to[0:4]), int(ending_month))[1])

        data = {'client_nihil': options.get('client_nihil'), 'ask_restitution': options.get('ask_restitution', False), 'ask_payment': options.get('ask_payment', False)}

        complete_vat = (country_from_vat or (address.country_id and address.country_id.code or "")) + vat_no
        file_data = {
                        'issued_by': issued_by,
                        'vat_no': complete_vat,
                        'only_vat': vat_no,
                        'cmpny_name': company.name,
                        'address': "%s %s" % (address.street or "", address.street2 or ""),
                        'post_code': address.zip or "",
                        'city': address.city or "",
                        'country_code': address.country_id and address.country_id.code or "",
                        'email': address.email or "",
                        'phone': address.phone.replace('.', '').replace('/', '').replace('(', '').replace(')', '').replace(' ', ''),
                        'send_ref': send_ref,
                        'quarter': quarter,
                        'month': starting_month,
                        'year': str(dt_to[:4]),
                        'client_nihil': (data['client_nihil'] and 'YES' or 'NO'),
                        'ask_restitution': (data['ask_restitution'] and 'YES' or 'NO'),
                        'ask_payment': (data['ask_payment'] and 'YES' or 'NO'),
                        'comments': self._get_report_manager(options).summary or '',
                     }

        rslt = """<?xml version="1.0"?>
<ns2:VATConsignment xmlns="http://www.minfin.fgov.be/InputCommon" xmlns:ns2="http://www.minfin.fgov.be/VATConsignment" VATDeclarationsNbr="1">
    <ns2:VATDeclaration SequenceNumber="1" DeclarantReference="%(send_ref)s">
        <ns2:Declarant>
            <VATNumber xmlns="http://www.minfin.fgov.be/InputCommon">%(only_vat)s</VATNumber>
            <Name>%(cmpny_name)s</Name>
            <Street>%(address)s</Street>
            <PostCode>%(post_code)s</PostCode>
            <City>%(city)s</City>
            <CountryCode>%(country_code)s</CountryCode>
            <EmailAddress>%(email)s</EmailAddress>
            <Phone>%(phone)s</Phone>
        </ns2:Declarant>
        <ns2:Period>
    """ % (file_data)

        if starting_month != ending_month:
            # starting month and ending month of selected period are not the same
            # it means that the accounting isn't based on periods of 1 month but on quarters
            rslt += '\t\t<ns2:Quarter>%(quarter)s</ns2:Quarter>\n\t\t' % (file_data)
        else:
            rslt += '\t\t<ns2:Month>%(month)s</ns2:Month>\n\t\t' % (file_data)
        rslt += '\t<ns2:Year>%(year)s</ns2:Year>' % (file_data)
        rslt += '\n\t\t</ns2:Period>\n'
        rslt += '\t\t<ns2:Data>\t'

        grids_list = []
        currency_id = self.env.company.currency_id

        ctx = self._set_context(options)
        ctx.update({'no_format': True, 'date_from': date_from, 'date_to': date_to})
        lines = self.with_context(ctx)._get_lines(options)

        # Create a mapping between report line ids and actual grid names
        non_compound_rep_lines = self.env['account.tax.report.line'].search([('tag_name', 'not in', ('48s44', '48s46L', '48s46T', '46L', '46T')), ('country_id.code', '=', 'BE')])
        lines_grids_map = {line.id: line.tag_name for line in non_compound_rep_lines}
        lines_grids_map['section_' + str(self.env.ref('l10n_be.tax_report_title_operations_sortie_46').id)] = '46'
        lines_grids_map['section_' + str(self.env.ref('l10n_be.tax_report_title_operations_sortie_48').id)] = '48'
        lines_grids_map['total_' + str(self.env.ref('l10n_be.tax_report_line_71').id)] = '71'
        lines_grids_map['total_' + str(self.env.ref('l10n_be.tax_report_line_72').id)] = '72'

        # Iterate on the report lines, using this mapping
        for line in lines:
            if line['id'] in lines_grids_map and not currency_id.is_zero(line['columns'][0]['name']):
                grids_list.append((lines_grids_map[line['id']], line['columns'][0]['name']))

        if options.get('grid91') and not currency_id.is_zero(options['grid91']):
            grids_list.append(('91', options['grid91']))

        grids_list = sorted(grids_list, key=lambda a: a[0])
        for item in grids_list:
            grid_amount_data = {
                    'code': item[0],
                    'amount': '%.2f' % abs(item[1]),
                    }
            rslt += '\n\t\t\t<ns2:Amount GridNumber="%(code)s">%(amount)s</ns2:Amount''>' % (grid_amount_data)

        rslt += '\n\t\t</ns2:Data>'
        rslt += '\n\t\t<ns2:ClientListingNihil>%(client_nihil)s</ns2:ClientListingNihil>' % (file_data)
        rslt += '\n\t\t<ns2:Ask Restitution="%(ask_restitution)s" Payment="%(ask_payment)s"/>' % (file_data)
        rslt += '\n\t\t<ns2:Comment>%(comments)s</ns2:Comment>' % (file_data)
        rslt += '\n\t</ns2:VATDeclaration> \n</ns2:VATConsignment>'

        return rslt.encode()

    def _check_vat_number(self, vat_number):
        """
        Even with base_vat, the vat number doesn't necessarily starts
        with the country code
        We should make sure the vat is set with the country code
        to avoid submitting this declaration with a wrong vat number
        """
        vat_number = vat_number.replace(' ', '').upper()
        try:
            int(vat_number[:2])
            country_code = None
        except ValueError:
            country_code = vat_number[:2]
            vat_number = vat_number[2:]

        return vat_number, country_code

    # https://eservices.minfin.fgov.be/intervat/static/help/FR/regles_de_validation_d_une_declaration.htm
    # The numerotation in the comments is extended here if it wasn't done in the
    # source document: ... X, Y, Z, AA, AB, AC, ...
    def get_checks_to_perform(self, d):
        if self.env.company.country_id.code == 'BE':
            return [
                # code 13
                ('No negative number',
                    not all(v >= 0 for v in d.values())),
                # Code C
                ('[55] > 0 if [86] > 0 or [88] > 0',
                    min(0.0, d['c55']) if d['c86'] > 0 or d['c88'] > 0 else False),
                # Code D
                ('[56] + [57] > 0 if [87] > 0',
                    min(0.0, d['c55']) if d['c86'] > 0 or d['c88'] > 0 else False),
                # Code O
                ('[01] * 6% + [02] * 12% + [03] * 21% = [54]',
                    d['c01'] * 0.06 + d['c02'] * 0.12 + d['c03'] * 0.21 - d['c54'] if abs(d['c01'] * 0.06 + d['c02'] * 0.12 + d['c03'] * 0.21 - d['c54']) > 62 else False),
                # Code P
                ('([84] + [86] + [88]) * 21% >= [55]',
                    min(0.0, (d['c84'] + d['c86'] + d['c88']) * 0.21 - d['c55']) if min(0.0, (d['c84'] + d['c86'] + d['c88']) * 0.21 - d['c55']) < -62 else False),
                # Code Q
                ('([85] + [87]) * 21% >= ([56] + [57])',
                    min(0.0, (d['c85'] + d['c87']) * 0.21 - (d['c56'] + d['c57'])) if min(0.0, (d['c85'] + d['c87']) * 0.21 - (d['c56'] + d['c57'])) < -62 else False),
                # Code S
                ('([81] + [82] + [83] + [84] + [85]) * 50% >= [59]',
                    min(0.0, (d['c81'] + d['c82'] + d['c83'] + d['c84'] + d['c85']) * 0.5 - d['c59'])),
                # Code T
                ('[85] * 21% >= [63]',
                    min(0.0, d['c85'] * 0.21 - d['c63']) if min(0.0, d['c85'] * 0.21 - d['c63']) < -62 else False),
                # Code U
                ('[49] * 21% >= [64]',
                    min(0.0, d['c49'] * 0.21 - d['c64']) if min(0.0, d['c49'] * 0.21 - d['c64']) < -62 else False),
                # Code AC
                ('[88] < ([81] + [82] + [83] + [84]) * 100 if [88] > 99.999',
                    max(0.0, d['c88'] - (d['c81'] + d['c82'] + d['c83'] + d['c84']) * 100) if d['c88'] > 99999 else False),
                # Code AD
                ('[44] < ([00] + [01] + [02] + [03] + [45] + [46] + [47] + [48] + [49]) * 200 if [88] > 99.999',
                    max(0.0, d['c44'] - (d['c00'] + d['c01'] + d['c02'] + d['c03'] + d['c45'] + d['c46'] + d['c47'] + d['c48'] + d['c49']) * 200) if d['c44'] > 99999 else False),
            ]
        return super(AccountGenericTaxReport, self).get_checks_to_perform(d)
