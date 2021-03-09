# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from math import copysign

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo import release

from datetime import datetime


class IntrastatReport(models.AbstractModel):
    _inherit = 'account.intrastat.report'

    def _get_reports_buttons(self):
        res = super(IntrastatReport, self)._get_reports_buttons()
        if self.env.company.country_id == self.env.ref('base.nl'):
            res += [{'name': _('Export (CBS)'), 'sequence': 3, 'action': 'print_csv', 'file_export_type': _('CBS')}]
        return res

    def print_csv(self, options):
        action = self.print_xml(options)
        action['data']['output_format'] = 'csv'
        return action

    @api.model
    def get_csv(self, options):
        ''' Export the Centraal Bureau voor de Statistiek (CBS) file.

        Documentation found in:
        https://www.cbs.nl/en-gb/deelnemers%20enquetes/overzicht/bedrijven/onderzoek/lopend/international-trade-in-goods/idep-code-lists

        :param options: The report options.
        :return:        The content of the file as str.
        '''
        # Fetch data.
        self.env['account.move.line'].check_access_rights('read')

        company = self.env.company
        date_from, date_to, journal_ids, incl_arrivals, incl_dispatches, extended, with_vat = self._decode_options(options)

        invoice_types = []
        if incl_arrivals:
            invoice_types += ['in_invoice', 'out_refund']
        if incl_dispatches:
            invoice_types += ['out_invoice', 'in_refund']

        query, params = self._prepare_query(date_from, date_to, journal_ids, invoice_types=invoice_types, with_vat=with_vat)

        self._cr.execute(query, params)
        query_res = self._cr.dictfetchall()
        line_map = dict((l.id, l) for l in self.env['account.move.line'].browse(res['id'] for res in query_res))

        # Create csv file content.
        vat = company.vat
        now = datetime.now()
        registration_number = company.l10n_nl_cbs_reg_number or ''
        software_version = release.version

        # The software_version looks like saas~11.1+e but we have maximum 5 characters allowed
        software_version = software_version.replace('saas~', '').replace('+e', '').replace('alpha', '')

        # HEADER LINE
        file_content = ''.join([
            '9801',                                                             # Record type           length=4
            vat and vat[2:].replace(' ', '').ljust(12) or ''.ljust(12),         # VAT number            length=12
            date_from[:4] + date_from[5:7],                                     # Review perior         length=6
            (company.name or '').ljust(40),                                     # Company name          length=40
            registration_number.ljust(6),                                       # Registration number   length=6
            software_version.ljust(5),                                          # Version number        length=5
            now.strftime('%Y%m%d'),                                             # Creation date         length=8
            now.strftime('%H%M%S'),                                             # Creation time         length=6
            company.phone and \
            company.phone.replace(' ', '')[:15].ljust(15) or ''.ljust(15),      # Telephone number      length=15
            ''.ljust(13),                                                       # Reserve               length=13
        ]) + '\n'

        # CONTENT LINES
        i = 1
        for res in query_res:
            line = line_map[res['id']]
            inv = line.move_id
            country_dest_code = inv.partner_id.country_id and inv.partner_id.country_id.code or ''
            country_origin_code = inv.intrastat_country_id and inv.intrastat_country_id.code or ''
            country = country_origin_code if res['type'] == 'Arrival' else country_dest_code

            # From the Manual for Statistical Declarations International Trade in Goods:
            #
            # For commodities where no supplementary unit is given, the weight has te be reported,
            # rounded off in kilograms.
            # [...]
            # Weights below 1 kilogram should be rounded off above.
            #
            # Therefore:
            #  5.2 => 5; -5.2 => -5; 0.2 => 1; -0.2 => -1
            # If the mass is zero, we leave it like this: it means the user forgot to set the weight
            # of the products, so it should be corrected.
            mass = line.product_id and line.quantity * (line.product_id.weight or line.product_id.product_tmpl_id.weight) or 0
            if mass:
                mass = copysign(round(mass) or 1.0, mass)

            # In the case of the value:
            # If the invoice value does not reconcile with the actual value of the goods, deviating
            # provisions apply. This applies, for instance, in the event of free delivery...
            # [...]
            # The actual value of the goods must be given
            value = line.price_subtotal or line.product_id.lst_price
            transaction_period = str(inv.invoice_date.year) + str(inv.invoice_date.month).rjust(2, '0')
            file_content += ''.join([
                transaction_period,                                             # Transaction period    length=6
                '6' if res['type'] == 'Arrival' else '7',                       # Commodity flow        length=1
                vat and vat[2:].replace(' ', '').ljust(12) or ''.ljust(12),     # VAT number            length=12
                str(i).zfill(5),                                                # Line number           length=5
                '000',                                                          # Country of origin     length=3
                country.ljust(3),                                               # Count. of cons./dest. length=3
                res['invoice_transport'] or '3',                                # Mode of transport     length=1
                '0',                                                            # Container             length=1
                '00',                                                           # Traffic region/port   length=2
                '00',                                                           # Statistical procedure length=2
                res['transaction_code'] or '1',                                 # Transaction           length=1
                (res['commodity_code'] or '')[:8].ljust(8),                     # Commodity code        length=8
                '00',                                                           # Taric                 length=2
                mass >= 0 and '+' or '-',                                       # Mass sign             length=1
                str(int(abs(mass))).zfill(10),                                  # Mass                  length=10
                '+',                                                            # Supplementary sign    length=1
                '0000000000',                                                   # Supplementary unit    length=10
                inv.amount_total_signed >= 0 and '+' or '-',                    # Invoice sign          length=1
                str(int(value)).zfill(10),                                      # Invoice value         length=10
                '+',                                                            # Statistical sign      length=1
                '0000000000',                                                   # Statistical value     length=10
                (inv.number or '')[-10:].ljust(10),                             # Administration number length=10
                ''.ljust(3),                                                    # Reserve               length=3
                ' ',                                                            # Correction items      length=1
                '000',                                                          # Preference            length=3
                ''.ljust(7),                                                    # Reserve               length=7
            ]) + '\n'
            i += 1

        # FOOTER LINE
        file_content += ''.join([
            '9899',                                                             # Record type           length=4
            ''.ljust(111)                                                       # Reserve               length=111
        ])

        return file_content
