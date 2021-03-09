# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
from odoo import models, fields, api
from odoo.tools.misc import formatLang, format_date, get_lang
from odoo.tools.translate import _
from odoo.tools import append_content_to_html, DEFAULT_SERVER_DATE_FORMAT, html2plaintext
from odoo.exceptions import UserError


class AccountReportFollowupManager(models.Model):
    _inherit = 'account.report.manager'

    partner_id = fields.Many2one('res.partner')


class AccountFollowupReport(models.AbstractModel):
    _name = "account.followup.report"
    _description = "Follow-up Report"
    _inherit = 'account.report'

    filter_partner_id = False

    def _get_options(self, previous_options=None):
        options = super()._get_options(previous_options)
        # It doesn't make sense to allow multicompany for these kind of reports
        # 1. Followup mails need to have the right headers from the right company
        # 2. Separation of business seems natural: a customer wouldn't know or care that the two companies are related
        if 'multi_company' in options:
            del options['multi_company']
        return options

    def _get_columns_name(self, options):
        """
        Override
        Return the name of the columns of the follow-ups report
        """
        headers = [{},
                   {'name': _('Date'), 'class': 'date', 'style': 'text-align:center; white-space:nowrap;'},
                   {'name': _('Due Date'), 'class': 'date', 'style': 'text-align:center; white-space:nowrap;'},
                   {'name': _('Source Document'), 'style': 'text-align:center; white-space:nowrap;'},
                   {'name': _('Communication'), 'style': 'text-align:right; white-space:nowrap;'},
                   {'name': _('Expected Date'), 'class': 'date', 'style': 'white-space:nowrap;'},
                   {'name': _('Excluded'), 'class': 'date', 'style': 'white-space:nowrap;'},
                   {'name': _('Total Due'), 'class': 'number o_price_total', 'style': 'text-align:right; white-space:nowrap;'}
                  ]
        if self.env.context.get('print_mode'):
            headers = headers[:5] + headers[7:]  # Remove the 'Expected Date' and 'Excluded' columns
        return headers

    def _get_lines(self, options, line_id=None):
        """
        Override
        Compute and return the lines of the columns of the follow-ups report.
        """
        # Get date format for the lang
        partner = options.get('partner_id') and self.env['res.partner'].browse(options['partner_id']) or False
        if not partner:
            return []

        lang_code = partner.lang if self._context.get('print_mode') else self.env.user.lang or get_lang(self.env).code
        lines = []
        res = {}
        today = fields.Date.today()
        line_num = 0
        for l in partner.unreconciled_aml_ids.filtered(lambda l: l.company_id == self.env.company):
            if l.company_id == self.env.company:
                if self.env.context.get('print_mode') and l.blocked:
                    continue
                currency = l.currency_id or l.company_id.currency_id
                if currency not in res:
                    res[currency] = []
                res[currency].append(l)
        for currency, aml_recs in res.items():
            total = 0
            total_issued = 0
            for aml in aml_recs:
                amount = aml.amount_residual_currency if aml.currency_id else aml.amount_residual
                date_due = format_date(self.env, aml.date_maturity or aml.date, lang_code=lang_code)
                total += not aml.blocked and amount or 0
                is_overdue = today > aml.date_maturity if aml.date_maturity else today > aml.date
                is_payment = aml.payment_id
                if is_overdue or is_payment:
                    total_issued += not aml.blocked and amount or 0
                if is_overdue:
                    date_due = {'name': date_due, 'class': 'color-red date', 'style': 'white-space:nowrap;text-align:center;color: red;'}
                if is_payment:
                    date_due = ''
                move_line_name = self._format_aml_name(aml.name, aml.move_id.ref, aml.move_id.name)
                if self.env.context.get('print_mode'):
                    move_line_name = {'name': move_line_name, 'style': 'text-align:right; white-space:normal;'}
                amount = formatLang(self.env, amount, currency_obj=currency)
                line_num += 1
                expected_pay_date = format_date(self.env, aml.expected_pay_date, lang_code=lang_code) if aml.expected_pay_date else ''
                columns = [
                    format_date(self.env, aml.date, lang_code=lang_code),
                    date_due,
                    aml.move_id.invoice_origin or '',
                    move_line_name,
                    (expected_pay_date and expected_pay_date + ' ') + (aml.internal_note or ''),
                    {'name': '', 'blocked': aml.blocked},
                    amount,
                ]
                if self.env.context.get('print_mode'):
                    columns = columns[:4] + columns[6:]
                lines.append({
                    'id': aml.id,
                    'account_move': aml.move_id,
                    'name': aml.move_id.name,
                    'caret_options': 'followup',
                    'move_id': aml.move_id.id,
                    'type': is_payment and 'payment' or 'unreconciled_aml',
                    'unfoldable': False,
                    'columns': [type(v) == dict and v or {'name': v} for v in columns],
                })
            total_due = formatLang(self.env, total, currency_obj=currency)
            line_num += 1
            lines.append({
                'id': line_num,
                'name': '',
                'class': 'total',
                'style': 'border-top-style: double',
                'unfoldable': False,
                'level': 3,
                'columns': [{'name': v} for v in [''] * (3 if self.env.context.get('print_mode') else 5) + [total >= 0 and _('Total Due') or '', total_due]],
            })
            if total_issued > 0:
                total_issued = formatLang(self.env, total_issued, currency_obj=currency)
                line_num += 1
                lines.append({
                    'id': line_num,
                    'name': '',
                    'class': 'total',
                    'unfoldable': False,
                    'level': 3,
                    'columns': [{'name': v} for v in [''] * (3 if self.env.context.get('print_mode') else 5) + [_('Total Overdue'), total_issued]],
                })
            # Add an empty line after the total to make a space between two currencies
            line_num += 1
            lines.append({
                'id': line_num,
                'name': '',
                'class': '',
                'style': 'border-bottom-style: none',
                'unfoldable': False,
                'level': 0,
                'columns': [{} for col in columns],
            })
        # Remove the last empty line
        if lines:
            lines.pop()
        return lines

    @api.model
    def _get_sms_summary(self, options):
        partner = self.env['res.partner'].browse(options.get('partner_id'))
        level = partner.followup_level
        options = dict(options, followup_level=(level.id, level.delay))
        return self._build_followup_summary_with_field('sms_description', options)

    @api.model
    def _get_default_summary(self, options):
        return self._build_followup_summary_with_field('description', options)

    @api.model
    def _build_followup_summary_with_field(self, field, options):
        """
        Build the followup summary based on the relevent followup line.
        :param field: followup line field used as the summary "template"
        :param options: dict that should contain the followup level and the partner
        :return: the summary if a followup line exists or None
        """
        followup_line = self.get_followup_line(options)
        if followup_line:
            partner = self.env['res.partner'].browse(options['partner_id'])
            lang = partner.lang or get_lang(self.env).code
            summary = followup_line.with_context(lang=lang)[field]
            try:
                summary = summary % {'partner_name': partner.name,
                                     'date': time.strftime(DEFAULT_SERVER_DATE_FORMAT),
                                     'user_signature': html2plaintext(self.env.user.signature or ''),
                                     'company_name': self.env.company.name,
                                     'amount_due': partner.total_due,
                                     }
            except ValueError as exception:
                message = _("An error has occurred while formatting your followup letter/email. (Lang: %s, Followup Level: #%s) \n\nFull error description: %s") \
                          % (lang, followup_line.id, exception)
                raise ValueError(message)
            return summary
        raise UserError(_('You need a least one follow-up level in order to process your follow-up'))

    def _get_report_manager(self, options):
        """
        Override
        Compute and return the report manager for the partner_id in options
        """
        domain = [('report_name', '=', 'account.followup.report'), ('partner_id', '=', options.get('partner_id')), ('company_id', '=', self.env.company.id)]
        existing_manager = self.env['account.report.manager'].search(domain, limit=1)
        if existing_manager and not options.get('keep_summary'):
            existing_manager.write({'summary': self._get_default_summary(options)})
        if not existing_manager:
            existing_manager = self.env['account.report.manager'].create({
                'report_name': 'account.followup.report',
                'company_id': self.env.company.id,
                'partner_id': options.get('partner_id'),
                'summary': self._get_default_summary(options)})
        return existing_manager

    def get_html(self, options, line_id=None, additional_context=None):
        """
        Override
        Compute and return the content in HTML of the followup for the partner_id in options
        """
        if additional_context is None:
            additional_context = {}
            additional_context['followup_line'] = self.get_followup_line(options)
        partner = self.env['res.partner'].browse(options['partner_id'])
        additional_context['partner'] = partner
        additional_context['lang'] = partner.lang or get_lang(self.env).code
        additional_context['invoice_address_id'] = self.env['res.partner'].browse(partner.address_get(['invoice'])['invoice'])
        additional_context['today'] = fields.date.today().strftime(DEFAULT_SERVER_DATE_FORMAT)
        return super(AccountFollowupReport, self).get_html(options, line_id=line_id, additional_context=additional_context)

    def _get_report_name(self):
        """
        Override
        Return the name of the report
        """
        return _('Followup Report')

    def _get_reports_buttons(self):
        """
        Override
        Return an empty list because this report doesn't contain any buttons
        """
        return []

    def _get_templates(self):
        """
        Override
        Return the templates of the report
        """
        templates = super(AccountFollowupReport, self)._get_templates()
        templates['main_template'] = 'account_followup.template_followup_report'
        templates['line_template'] = 'account_followup.line_template_followup_report'
        return templates

    @api.model
    def get_followup_informations(self, partner_id, options):
        """
        Return all informations needed by the view:
        - the report manager id
        - the content in HTML of the report
        - the state of the next_action
        """
        options['partner_id'] = partner_id
        partner = self.env['res.partner'].browse(partner_id)
        followup_line = partner.followup_level
        report_manager_id = self._get_report_manager(options).id
        html = self.get_html(options)
        next_action = False
        if not options.get('keep_summary'):
            next_action = partner.get_next_action(followup_line)
        infos = {
            'report_manager_id': report_manager_id,
            'html': html,
            'next_action': next_action,
        }
        if partner.followup_level:
            infos['followup_level'] = self._get_line_info(followup_line)
            options['followup_level'] = (partner.followup_level.id, partner.followup_level.delay)
        return infos

    @api.model
    def send_sms(self, options):
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'name': _("Send SMS Text Message"),
            'res_model': 'sms.composer',
            'target': 'new',
            'views': [(False, "form")],
            'context': {
                'default_body': self._get_sms_summary(options),
                'default_res_model': 'res.partner',
                'default_res_id': options.get('partner_id'),
            },
        }

    def _replace_class(self):
        # OVERRIDE: When added to the chatter by mail, don't loose the table-responsive set on the followup report table.
        res = super()._replace_class()
        if self._context.get('mail'):
            res.pop(b'table-responsive', None)
        return res

    @api.model
    def send_email(self, options):
        """
        Send by mail the followup to the customer
        """
        partner = self.env['res.partner'].browse(options.get('partner_id'))
        non_blocked_invoices = partner.unpaid_invoices.filtered(lambda inv: not any(inv.line_ids.mapped('blocked')))
        non_printed_invoices = non_blocked_invoices.filtered(lambda inv: not inv.message_main_attachment_id)
        if non_printed_invoices and partner.followup_level.join_invoices:
            raise UserError(_('You are trying to send a followup report to a partner for which you didn\'t print all the invoices ({})').format(" ".join(non_printed_invoices.mapped('name'))))
        invoice_partner = self.env['res.partner'].browse(partner.address_get(['invoice'])['invoice'])
        email = invoice_partner.email
        options['keep_summary'] = True
        if email and email.strip():
            # When printing we need te replace the \n of the summary by <br /> tags
            body_html = self.with_context(print_mode=True, mail=True, lang=partner.lang or self.env.user.lang).get_html(options)
            body_html = body_html.replace(b'o_account_reports_edit_summary_pencil', b'o_account_reports_edit_summary_pencil d-none')
            start_index = body_html.find(b'<span>', body_html.find(b'<div class="o_account_reports_summary">'))
            end_index = start_index > -1 and body_html.find(b'</span>', start_index) or -1
            if end_index > -1:
                replaced_msg = body_html[start_index:end_index].replace(b'\n', b'')
                body_html = body_html[:start_index] + replaced_msg + body_html[end_index:]
            partner.with_context(mail_post_autofollow=True).message_post(
                partner_ids=[invoice_partner.id],
                body=body_html,
                subject=_('%s Payment Reminder') % (self.env.company.name) + ' - ' + partner.name,
                subtype_id=self.env.ref('mail.mt_note').id,
                model_description=_('payment reminder'),
                email_layout_xmlid='mail.mail_notification_light',
                attachment_ids=partner.followup_level.join_invoices and non_blocked_invoices.message_main_attachment_id.ids or [],
            )
            return True
        raise UserError(_('Could not send mail to partner %s because it does not have any email address defined') % partner.display_name)

    @api.model
    def print_followups(self, records):
        """
        Print one or more followups in one PDF
        records contains either a list of records (come from an server.action) or a field 'ids' which contains a list of one id (come from JS)
        """
        res_ids = records['ids'] if 'ids' in records else records.ids  # records come from either JS or server.action
        action = self.env.ref('account_followup.action_report_followup').report_action(res_ids)
        if action.get('type') == 'ir.actions.report':
            for partner in self.env['res.partner'].browse(res_ids):
                partner.message_post(body=_('Follow-up letter printed'))
        return action

    def _get_line_info(self, followup_line):
        return {
            'id': followup_line.id,
            'name': followup_line.name,
            'print_letter': followup_line.print_letter,
            'send_email': followup_line.send_email,
            'send_sms': followup_line.send_sms,
            'manual_action': followup_line.manual_action,
            'manual_action_note': followup_line.manual_action_note
        }

    @api.model
    def get_followup_line(self, options):
        if not options.get('followup_level'):
            partner = self.env['res.partner'].browse(options.get('partner_id'))
            options['followup_level'] = (partner.followup_level.id, partner.followup_level.delay)
        if options.get('followup_level'):
            followup_line = self.env['account_followup.followup.line'].browse(options['followup_level'][0])
            return followup_line
        return False

    @api.model
    def do_manual_action(self, options):
        msg = _('Manual action done')
        partner = self.env['res.partner'].browse(options.get('partner_id'))
        if options.get('followup_level'):
            followup_line = self.env['account_followup.followup.line'].browse(options.get('followup_level'))
            if followup_line:
                msg += '<br>' + followup_line.manual_action_note
        partner.message_post(body=msg)
