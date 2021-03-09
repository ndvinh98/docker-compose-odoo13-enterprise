# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import requests
import logging
import datetime
from re import match
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

class HmrcVatObligation(models.Model):
    """ VAT obligations retrieved from HMRC """

    _name = 'l10n_uk.vat.obligation'
    _description = 'HMRC VAT Obligation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'date_due'
    _order = 'date_due'

    # fields retrieved from HMRC
    date_start = fields.Date('Period Start', readonly=True)
    date_end = fields.Date('Period End', readonly=True)
    date_due = fields.Date('Period Due', readonly=True)
    status = fields.Selection([('open', 'Open'), ('fulfilled', 'Fulfilled')], string='Period Status', readonly=True)
    period_key = fields.Char('Period Key', readonly=True)
    date_received = fields.Date('Received Submission date', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', required=True,
        default=lambda self: self.env.company)

    def name_get(self):
        return [(o.id, "%s (%s - %s)" % (o.date_due, o.date_start, o.date_end)) for o in self]

    @api.model
    def _get_auth_headers(self, bearer):
        headers = {
            'Accept': 'application/vnd.hmrc.1.0+json',
            'Content-Type': 'application/json',
        }
        headers.update({
            'Authorization': 'Bearer %s' % bearer ,
        })
        headers.update(self.env['hmrc.service']._get_fraud_prevention_info())
        return headers

    @api.model
    def retrieve_vat_obligations(self, vat, from_date, to_date, status=''):
        """ Retrieve vat obligations

        The User should be logged in before doing this
        :param vat:
        :param from_date:
        :param to_date:
        :param status:
        :return: list of obligations of the status type for the requested period
        """
        if not match(r'^[0-9]{9}$', vat or ''):
            raise UserError(_("VAT numbers of UK companies should have exactly 9 figures. Please check the settings of the current company."))

        user = self.env.user
        bearer = user.l10n_uk_hmrc_vat_token
        headers = self._get_auth_headers(bearer)

        url = self.env['hmrc.service']._get_endpoint_url('/organisations/vat/%s/obligations' % vat)
        params = {
            'from': from_date,
            'to': to_date,
        }
        if status:
            status = 'O' if status == 'open' else 'F'
            params.update({'status': status})
        resp = requests.get(url, headers=headers, params=params)
        response = json.loads(resp.content.decode())
        if resp.status_code == 200:
            # Create obligations
            return response.get('obligations')

        # Show a nice error when something goes wrong
        error_code = response.get('code')
        if error_code == 'VRN_INVALID':
            error_message = _('Invalid Company VAT number. Please fill in the correct VAT on the company form. ')
        elif error_code in ('INVALID_DATE_FROM', 'INVALID_DATE_TO', 'INVALID_DATE_RANGE'):
            error_message = _('Issue with the selected dates.')
        elif error_code == 'INVALID_STATUS':
            error_message = _('Invalid Status.')
        elif error_code == 'NOT_FOUND':
            error_message = _('No open obligations were found for the moment.')
        else:
            error_message = response.get('message', error_code)
        raise UserError(error_message)

    def import_vat_obligations(self):
        today = datetime.date.today()
        res = self.env['hmrc.service']._login()
        if res: # If you can not login, return url for re-login
            return res

        # look for open obligations in the -6 months +6 months range
        obligations = self.retrieve_vat_obligations(
            self.env.company.vat,
            (today + relativedelta(months=-6)).strftime('%Y-%m-%d'),
            (today + relativedelta(months=6,leapdays=-1)).strftime('%Y-%m-%d'))

        for new_obligation in obligations:
            obligation = self.env['l10n_uk.vat.obligation'].search([('period_key', '=', new_obligation.get('periodKey')),
                                                                 ('company_id', '=', self.env.company.id)])
            status = 'open' if new_obligation['status'] == 'O' else 'fulfilled'
            if not obligation:
                self.sudo().create({'date_start': new_obligation['start'],
                                    'date_end': new_obligation['end'],
                                    'date_received': new_obligation.get('received_date'),
                                    'date_due': new_obligation['due'],
                                    'status': status,
                                    'period_key': new_obligation['periodKey'],
                                    'company_id': self.env.company.id,
                                    })
            elif obligation.status != status or obligation.date_received != new_obligation.get('received_date'):
                obligation.sudo().write({'status': status,
                                         'date_received': new_obligation.get('received_date')})

    def _fetch_values_from_report(self, lines):
        translation_table = {
            'vatDueSales': 'account_tax_report_line_vat_box1',
            'vatDueAcquisitions': 'account_tax_report_line_vat_box2',
            'totalVatDue': 'account_tax_report_line_vat_box3',
            'vatReclaimedCurrPeriod': 'account_tax_report_line_vat_box4',
            'netVatDue': 'account_tax_report_line_vat_box5',
            'totalValueSalesExVAT': 'account_tax_report_line_exd_vat_box6',
            'totalValuePurchasesExVAT': 'account_tax_report_line_exd_vat_box7',
            'totalValueGoodsSuppliedExVAT': 'account_tax_report_line_exd_vat_box8',
            'totalAcquisitionsExVAT': 'account_tax_report_line_exd_vat_box9',
        }
        reverse_table = {}
        for line_xml_id in translation_table:
            uk_report_id = self.env.ref('l10n_uk.' + translation_table[line_xml_id])
            if line_xml_id in ('netVatDue', 'totalVatDue'): #Ids of totals are "total_" + id
                reverse_table['total_' + str(uk_report_id.id)] = line_xml_id
            else:
                reverse_table[uk_report_id.id] = line_xml_id

        values = {}
        for line in lines:
            if reverse_table.get(line['id']):
                # Do a get for the no_format_name as for the totals you have twice the line, without and with amount
                # We cannot pass a negative netVatDue to the API and the amounts of sales/purchases/goodssupplied/ ... must be rounded
                if reverse_table[line['id']] == 'netVatDue':
                    values[reverse_table[line['id']]] = abs(round(line['columns'][0].get('balance', 0.0), 2))
                elif reverse_table[line['id']] in ('totalValueSalesExVAT', 'totalValuePurchasesExVAT', 'totalValueGoodsSuppliedExVAT', 'totalAcquisitionsExVAT'):
                    values[reverse_table[line['id']]] = round(line['columns'][0].get('balance', 0.0))
                else:
                    values[reverse_table[line['id']]] = round(line['columns'][0].get('balance', 0.0), 2)
        return values

    def action_submit_vat_return(self):
        self.ensure_one()
        report = self.env['account.generic.tax.report']
        options = report._get_options()
        options['date'].update({'date_from': fields.Date.to_string(self.date_start),
                        'date_to': fields.Date.to_string(self.date_end),
                        'filter': 'custom',
                        'mode': 'range'})
        if self.env.context.get('hmrc_cash_basis', False):
            options.update({'cash_basis': True})
        ctx = report._set_context(options)
        report_values = report.with_context(ctx)._get_lines(options)
        values = self._fetch_values_from_report(report_values)
        vat = self.env.company.vat
        res = self.env['hmrc.service']._login()
        if res: # If you can not login, return url for re-login
            return res
        headers = self._get_auth_headers(self.env.user.l10n_uk_hmrc_vat_token)
        url = self.env['hmrc.service']._get_endpoint_url('/organisations/vat/%s/returns' % vat)
        data = values.copy()
        data.update({
         'periodKey': self.period_key,
         'finalised': True
        })

        # Need to check with which credentials it needs to be done
        r = requests.post(url, headers=headers, data=json.dumps(data))
        # Need to do something with the result?
        if r.status_code == 201: #Successful post
            response = json.loads(r.content.decode())
            msg = _('Tax return successfully posted:') + ' <br/>'
            msg += '<b>' + _('Date Processed') + ': </b>' + response['processingDate'] + '<br/>'
            if response.get('paymentIndicator'):
                msg += '<b>' + _('Payment Indicator') + ': </b>' + response['paymentIndicator'] + '<br/>'
            msg += '<b>' + _('Form Bundle Number') + ': </b>' + response['formBundleNumber'] + '<br/>'
            if response.get('chargeRefNumber'):
                msg += '<b>' + _('Charge Ref Number') + ': </b>' + response['chargeRefNumber'] + '<br/>'
            msg += '<br/>' + _('Sent Values:') + '<br/>'
            for sent_key in data:
                if sent_key != 'periodKey':
                    msg += '<b>' + sent_key + '</b>: ' + str(data[sent_key]) + '<br/>'
            self.sudo().message_post(body=msg)
            self.sudo().write({'status': "fulfilled"})
        elif r.status_code == 401:  # auth issue
            _logger.exception(_("HMRC auth issue : %s"), r.content)
            raise UserError(_(
             "Sorry, your credentials were refused by HMRC or your permission grant has expired. You may try to authenticate again."))
        else:  # other issues
            _logger.exception(_("HMRC other issue : %s") % r.content)
            # even 'normal' hmrc errors have a json body. Otherwise will also raise.
            response = json.loads(r.content.decode())
            # Recuperate error message
            if response.get('errors'):
                msgs = ""
                for err in response['errors']:
                    msgs += err.get('message', '')
            else:
                msgs = response.get('message') or response
            raise UserError(_("Sorry, something went wrong: %s") %  msgs)
