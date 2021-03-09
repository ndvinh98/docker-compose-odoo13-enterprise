# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
from datetime import datetime

from odoo import models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class CertificationReport(models.AbstractModel):
    _name = 'report.l10n_co_reports.report_certification'
    _description = "Colombian Certification Report"

    def _get_report_values(self, docids, data=None):
        docs = []
        partner_doc = {}

        for line in data.get('lines', []):
            if 'partner_' in line['id']:
                partner_doc = {
                    'partner_id': self.env['res.partner'].browse(line['partner_id']),
                    'lines': [],
                }

                # add totals
                for column in line['columns']:
                    if column['name']:
                        partner_doc[column['field_name']] = column['name']
                docs.append(partner_doc)
            else:
                line_dict = {}
                for column in line['columns']:
                    line_dict[column['field_name']] = column['name']
                partner_doc['lines'].append(line_dict)

        # get rid of partners without expanded lines
        docs = [doc for doc in docs if doc['lines']]
        if not docs:
            raise UserError(_('You have to expand at least one partner.'))

        return {
            'docs': docs,
            'options': data['wizard_values'],
            'report_name': data['report_name'],
            'company': self.env.company,
            'current_year': self.env.company.compute_fiscalyear_dates(datetime.now())['date_from'].year,
        }


class ReportCertificationReport(models.AbstractModel):
    _name = 'l10n_co_reports.certification_report'
    _description = 'Colombian certification report'
    _inherit = 'account.report'

    filter_unfold_all = False
    filter_partner_id = False
    filter_date = {'mode': 'range', 'filter': 'this_year'}

    def _get_bimonth_for_aml(self, aml):
        bimonth = aml.date.month
        # month:   1   2   3   4   5   6   7   8   9   10  11   12
        # bimonth: \ 1 /   \ 2 /   \ 3 /   \ 4 /   \ 5 /    \ 6 /
        bimonth = (bimonth + 1) // 2
        return bimonth

    def _get_bimonth_name(self, bimonth_index):
        bimonth_names = {
            1: 'Enero - Febrero',
            2: 'Marzo - Abril',
            3: 'Mayo - Junio',
            4: 'Julio - Agosto',
            5: 'Septiembre - Octubre',
            6: 'Noviembre - Diciembre',
        }
        return bimonth_names[bimonth_index]

    def _get_domain(self, options):
        common_domain = [('partner_id', '!=', False)]
        if options.get('partner_id'):
            common_domain += [('partner_id.id', '=', options.get('partner_id'))]
        if options.get('date'):
            common_domain += [('date', '>=', options['date'].get('date_from')),
                              ('date', '<=', options['date'].get('date_to'))]
        return common_domain

    def _handle_aml(self, aml, lines_per_bimonth):
        raise NotImplementedError()

    def _get_values_for_columns(self, values):
        raise NotImplementedError()

    def _add_to_partner_total(self, totals, new_values):
        for column, value in new_values.items():
            if isinstance(value, str):
                totals[column] = ''
            else:
                totals[column] = totals.get(column, 0) + value

    def _generate_lines_for_partner(self, partner_id, lines_per_group, options):
        lines = []
        if lines_per_group:
            partner_line = {
                'id': 'partner_%s' % (partner_id.id),
                'partner_id': partner_id.id,
                'name': partner_id.name,
                'level': 2,
                'unfoldable': True,
                'unfolded': 'partner_%s' % (partner_id.id) in options.get('unfolded_lines'),
            }
            lines.append(partner_line)

            partner_totals = {}
            for group, values in lines_per_group.items():
                self._add_to_partner_total(partner_totals, values)
                if 'partner_%s' % (partner_id.id) in options.get('unfolded_lines'):
                    lines.append({
                        'id': 'line_%s_%s' % (partner_id.id, group),
                        'name': '',
                        'unfoldable': False,
                        'columns': self._get_values_for_columns(values),
                        'level': 1,
                        'parent_id': 'partner_%s' % (partner_id.id),
                    })
            partner_line['columns'] = self._get_values_for_columns(partner_totals)

        return lines

    def _get_lines(self, options, line_id=None):
        lines = []
        domain = []

        domain += self._get_domain(options)

        if line_id:
            partner_id = re.search('partner_(.+)', line_id).group(1)
            if partner_id:
                domain += [('partner_id.id', '=', partner_id)]

        amls = self.env['account.move.line'].search(domain, order='partner_id, id')
        previous_partner_id = self.env['res.partner']
        lines_per_group = {}

        for aml in amls:
            if previous_partner_id != aml.partner_id:
                partner_lines = self._generate_lines_for_partner(previous_partner_id, lines_per_group, options)
                if partner_lines:
                    lines += partner_lines
                    lines_per_group = {}
                previous_partner_id = aml.partner_id

            self._handle_aml(aml, lines_per_group)

        lines += self._generate_lines_for_partner(previous_partner_id, lines_per_group, options)

        return lines

    def print_pdf(self, options):
        lines = self._get_lines(options)

        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'l10n_co_reports.retention_report.wizard',
            'views': [(self.env.ref('l10n_co_reports.retention_report_wizard_form').id, 'form')],
            'view_id': self.env.ref('l10n_co_reports.retention_report_wizard_form').id,
            'target': 'new',
            'context': {'lines': lines, 'report_name': self._name},
        }


class ReportCertificationReportIca(models.AbstractModel):
    _name = 'l10n_co_reports.certification_report.ica'
    _description = 'Colombian ICA certification report'
    _inherit = 'l10n_co_reports.certification_report'

    def _get_report_name(self):
        return u'Retención en ICA'

    def _get_columns_name(self, options):
        return [
            {'name': 'Nombre'},
            {'name': 'Bimestre'},
            {'name': u'Monto del pago sujeto a retención', 'class': 'number'},
            {'name': 'Retenido y consignado', 'class': 'number'},
        ]

    def _get_values_for_columns(self, values):
        return [{'name': values['name'], 'field_name': 'name'},
                {'name': self.format_value(values['tax_base_amount']), 'field_name': 'tax_base_amount'},
                {'name': self.format_value(values['balance']), 'field_name': 'balance'}]

    def _get_domain(self, options):
        res = super(ReportCertificationReportIca, self)._get_domain(options)
        res += [('account_id.code', '=like', '2368%')]
        return res

    def _handle_aml(self, aml, lines_per_bimonth):
        bimonth = self._get_bimonth_for_aml(aml)
        if bimonth not in lines_per_bimonth:
            lines_per_bimonth[bimonth] = {
                'name': self._get_bimonth_name(bimonth),
                'tax_base_amount': 0,
                'balance': 0,
            }

        lines_per_bimonth[bimonth]['balance'] += aml.credit - aml.debit
        if aml.credit:
            lines_per_bimonth[bimonth]['tax_base_amount'] += aml.tax_base_amount
        else:
            lines_per_bimonth[bimonth]['tax_base_amount'] -= aml.tax_base_amount


class ReportCertificationReportIva(models.AbstractModel):
    _name = 'l10n_co_reports.certification_report.iva'
    _description = 'Colombian IVA certification report'
    _inherit = 'l10n_co_reports.certification_report'

    def _get_report_name(self):
        return u'Retención en IVA'

    def _get_columns_name(self, options):
        return [
            {'name': 'Nombre'},
            {'name': 'Bimestre'},
            {'name': u'Monto Total Operación', 'class': 'number'},
            {'name': u'Monto del Pago Sujeto Retención', 'class': 'number'},
            {'name': 'Retenido Consignado', 'class': 'number'},
            {'name': '%', 'class': 'number'},
        ]

    def _get_values_for_columns(self, values):
        return [{'name': values['name'], 'field_name': 'name'},
                {'name': self.format_value(values['tax_base_amount']), 'field_name': 'tax_base_amount'},
                {'name': self.format_value(values['balance_15_over_19']), 'field_name': 'balance_15_over_19'},
                {'name': self.format_value(values['balance']), 'field_name': 'balance'},
                {'name': 0.15 if values['balance'] else 0, 'field_name': 'percentage'}]

    def _get_domain(self, options):
        res = super(ReportCertificationReportIva, self)._get_domain(options)
        res += ['|', ('account_id.code', '=', '236705'), ('account_id.code', '=like', '240810%')]
        return res

    def _handle_aml(self, aml, lines_per_bimonth):
        bimonth = self._get_bimonth_for_aml(aml)
        if bimonth not in lines_per_bimonth:
            lines_per_bimonth[bimonth] = {
                'name': self._get_bimonth_name(bimonth),
                'tax_base_amount': 0,
                'balance': 0,
                'balance_15_over_19': 0,
            }

        if aml.account_id.code.startswith('240810'):
            lines_per_bimonth[bimonth]['balance_15_over_19'] += aml.credit - aml.debit
        else:
            lines_per_bimonth[bimonth]['balance'] += aml.credit - aml.debit
            if aml.credit:
                lines_per_bimonth[bimonth]['tax_base_amount'] += aml.tax_base_amount
            else:
                lines_per_bimonth[bimonth]['tax_base_amount'] -= aml.tax_base_amount


class ReportCertificationReportFuente(models.AbstractModel):
    _name = 'l10n_co_reports.certification_report.fuente'
    _description = 'Colombian Fuente certification report'
    _inherit = 'l10n_co_reports.certification_report'

    def _get_report_name(self):
        return u'Retención por Terceros'

    def _get_columns_name(self, options):
        return [
            {'name': u'Nombre'},
            {'name': u'Concepto de retención'},
            {'name': u'Monto del Pago Sujeto Retención', 'class': 'number'},
            {'name': u'Retenido Consignado', 'class': 'number'},
        ]

    def _get_values_for_columns(self, values):
        return [{'name': values['name'], 'field_name': 'name'},
                {'name': self.format_value(values['tax_base_amount']), 'field_name': 'tax_base_amount'},
                {'name': self.format_value(values['balance']), 'field_name': 'balance'}]

    def _get_domain(self, options):
        res = super(ReportCertificationReportFuente, self)._get_domain(options)
        res += [('account_id.code', '=like', '2365%'), ('account_id.code', '!=', '236505')]
        return res

    def _handle_aml(self, aml, lines_per_account):
        account_code = aml.account_id.code
        if account_code not in lines_per_account:
            lines_per_account[account_code] = {
                'name': aml.account_id.display_name,
                'tax_base_amount': 0,
                'balance': 0,
            }

        lines_per_account[account_code]['balance'] += aml.credit - aml.debit
        if aml.credit:
            lines_per_account[account_code]['tax_base_amount'] += aml.tax_base_amount
        else:
            lines_per_account[account_code]['tax_base_amount'] -= aml.tax_base_amount
