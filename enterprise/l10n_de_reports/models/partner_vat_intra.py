# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _
from odoo.tools.misc import formatLang


class ReportL10nDePartnerVatIntra(models.AbstractModel):
    _name = "l10n.de.report.partner.vat.intra"
    _description = "Deutschland Partner VAT Intra"
    _inherit = 'account.report'

    filter_date = {'mode': 'range', 'filter': 'this_month'}

    @api.model
    def _get_lines(self, options, line_id=None):
        lines = []
        context = self.env.context
        if not context.get('company_ids'):
            return lines
        tag_ids = [self.env['ir.model.data'].xmlid_to_res_id(k) for k in [
            'l10n_de.tag_de_intracom_community_delivery',
            'l10n_de.tag_de_intracom_community_supplies',
            'l10n_de.tag_de_intracom_ABC']]
        query = """
            SELECT p.name As partner_name, l.partner_id AS partner_id, p.vat AS vat,
                      at.account_account_tag_id AS intra_code, SUM(-l.balance) AS amount,
                      c.code AS partner_country
                      FROM account_move_line l
                      LEFT JOIN account_move m ON m.id = l.move_id
                      LEFT JOIN res_partner p ON l.partner_id = p.id
                      LEFT JOIN account_account_tag_account_move_line_rel at on l.id = at.account_move_line_id
                      LEFT JOIN res_country c ON p.country_id = c.id
                      WHERE at.account_account_tag_id IN %s
                       AND l.date >= %s
                       AND l.date <= %s
                       AND l.company_id IN %s
                       AND m.state = 'posted'
                      GROUP BY p.name, l.partner_id, p.vat, intra_code, partner_country
        """
        params = (tuple(tag_ids), context.get('date_from'),
                  context.get('date_to'), tuple(context.get('company_ids')))
        self.env.cr.execute(query, params)

        for row in self.env.cr.dictfetchall():
            if not row['vat']:
                row['vat'] = ''

            amt = row['amount'] or 0.0
            if amt:
                if row['intra_code'] == tag_ids[0]:
                    code = ''
                elif row['intra_code'] == tag_ids[1]:
                    code = 1
                else:
                    code = 2
                columns = [row['partner_country'], row['vat'].replace(' ', '').upper(), amt, code]
                if not context.get('no_format', False):
                    currency_id = self.env.company.currency_id
                    columns[2] = formatLang(self.env, columns[2], currency_obj=currency_id)

                lines.append({
                    'id': row['partner_id'],
                    'caret_options': 'res.partner',
                    'model': 'res.partner',
                    'name': row['partner_name'],
                    'columns': [{'name': v} for v in columns],
                    'unfoldable': False,
                    'unfolded': False,
                })
        return lines

    def _get_report_name(self):
        return _('Zusammenfassende Meldung')

    def _get_columns_name(self, options):
        return [{}, {'name': _('Länderkennzeichen')}, {'name': _('Ust-IdNr.')}, {'name': _('Summe der Bemessungsgrundlagen'), 'class': 'number'}, {'name': _('Sonstige Leistungen (1) <br/>/ Dreiecksgeschäfte (2)')}]
