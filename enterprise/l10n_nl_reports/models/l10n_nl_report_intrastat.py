# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _


class ReportL10nNLIntrastat(models.AbstractModel):
    _name = 'l10n.nl.report.intrastat'
    _description = 'Intrastat Report (ICP)'
    _inherit = 'account.report'

    filter_date = {'mode': 'range', 'filter': 'this_year'}

    def _get_columns_name(self, options):
        return [
            {'name': _('Partner')},
            {'name': _('Country Code')},
            {'name': _('VAT')},
            {'name': _('Amount Product'), 'class': 'number'},
            {'name': _('Amount Service'), 'class': 'number'},
            {'name': _('Total'), 'class': 'number'},
        ]

    def _get_report_name(self):
        return _('Intrastat (ICP)')

    @api.model
    def _get_lines(self, options, line_id=None):
        lines = []
        company_id = self.env.company

        country_ids = (self.env.ref('base.europe').country_ids - company_id.country_id).ids

        query = """
            SELECT l.partner_id, p.name, p.vat, c.code,
                   ROUND(SUM(CASE WHEN product_t.type != 'service' THEN l.credit - l.debit ELSE 0 END)) as amount_product,
                   ROUND(SUM(CASE WHEN product_t.type = 'service' THEN l.credit - l.debit ELSE 0 END)) as amount_service
            FROM account_move_line l
            LEFT JOIN res_partner p ON l.partner_id = p.id
            LEFT JOIN res_country c ON p.country_id = c.id
            LEFT JOIN account_move_line_account_tax_rel amlt ON l.id = amlt.account_move_line_id
            LEFT JOIN account_account_tag_account_move_line_rel line_tag on line_tag.account_move_line_id = l.id
            LEFT JOIN product_product product on product.id = l.product_id
            LEFT JOIN product_template product_t on product.product_tmpl_id = product_t.id
            WHERE line_tag.account_account_tag_id IN %(product_service_tags)s
            AND c.id IN %(country_ids)s
            AND l.parent_state = 'posted'
            AND l.date >= %(date_from)s
            AND l.date <= %(date_to)s
            AND l.company_id IN %(company_ids)s
            GROUP BY l.partner_id, p.name, p.vat, c.code
            HAVING ROUND(SUM(CASE WHEN product_t.type != 'service' THEN l.credit - l.debit ELSE 0 END)) != 0
            OR ROUND(SUM(CASE WHEN product_t.type = 'service' THEN l.credit - l.debit ELSE 0 END)) != 0
            ORDER BY p.name
        """

        params = {
            'product_service_tags': tuple(self.env.ref('l10n_nl.tax_report_rub_3b').tag_ids.ids),
            'country_ids': tuple(country_ids),
            'date_from': self._context['date_from'],
            'date_to': self._context['date_to'],
            'company_ids': tuple(self._context.get('company_ids')),
        }
        self.env.cr.execute(query, params)

        # Add lines
        total = 0
        for result in self.env.cr.dictfetchall():
            amount_product = result['amount_product']
            amount_service = result['amount_service']
            line_total = amount_product + amount_service
            total += line_total

            lines.append({
                'id': result['partner_id'],
                'caret_options': 'res.partner',
                'model': 'res.partner',
                'name': result['name'],
                'level': 2,
                'columns': [
                    {'name': v} for v in [
                        result['code'],
                        self._format_vat(result['vat'], result['code']),
                        # A balance of 0 should display nothing, not even 0
                        amount_product and self.format_value(amount_product) or None,
                        amount_service and self.format_value(amount_service) or None,
                        line_total and self.format_value(line_total) or None,
                    ]
                ],
                'unfoldable': False,
                'unfolded': False,
            })

        if lines:
            lines.append({
                'id': 'total_line',
                'class': 'total',
                'name': _('Total'),
                'level': 2,
                'columns': [
                    {'name': v}
                    for v in ['', '', '', '(product + service)', self.format_value(total)]
                ],
                'unfoldable': False,
                'unfolded': False,
            })

        return lines

    @api.model
    def _format_vat(self, vat, country_code):
        """ VAT numbers must be reported without country code, and grouped by 4
        characters, with a space between each pair of groups.
        """
        if vat:
            if vat[:2].lower() == country_code.lower():
                vat = vat[2:]
            return ' '.join(vat[i:i+4] for i in range(0, len(vat), 4))
        return None
