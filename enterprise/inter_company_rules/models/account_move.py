# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    auto_generated = fields.Boolean(string='Auto Generated Document', copy=False, default=False)
    auto_invoice_id = fields.Many2one('account.move', string='Source Invoice', readonly=True, copy=False)

    def post(self):
        # OVERRIDE to generate cross invoice based on company rules.
        res = super(AccountMove, self).post()
        invoices_map = {}
        for invoice in self.filtered(lambda move: move.is_invoice()):
            company = self.env['res.company']._find_company_from_partner(invoice.partner_id.id)
            if company and company.rule_type == 'invoice_and_refund' and not invoice.auto_generated:
                invoices_map.setdefault(company, self.env['account.move'])
                invoices_map[company] += invoice
        for company, invoices in invoices_map.items():
            invoices._inter_company_create_invoices(company)
        return res

    def _inter_company_create_invoices(self, company):
        ''' Create cross company invoices.
        :param company: The targeted new company (res.company record).
        :return:        The newly created invoices.
        '''

        context = dict(self.env.context)
        context.pop('default_journal_id', None)
        context['default_company_id'] = company.id
        context['force_company'] = company.id
        invoices_ctx = self.with_user(company.intercompany_user_id).with_context(context)
        # Prepare invoice values.
        invoices_vals_per_type = {}
        inverse_types = {
            'in_invoice': 'out_invoice',
            'in_refund': 'out_refund',
            'out_invoice': 'in_invoice',
            'out_refund': 'in_refund',
        }
        for inv in invoices_ctx:
            invoice_vals = inv._inter_company_prepare_invoice_data(company, inverse_types[inv.type])
            invoice_vals['invoice_line_ids'] = []
            for line in inv.invoice_line_ids:
                invoice_vals['invoice_line_ids'].append((0, 0, line._inter_company_prepare_invoice_line_data(company)))

            inv_new = inv.with_context(default_type=invoice_vals['type']).new(invoice_vals)
            for line in inv_new.invoice_line_ids:
                price_unit = line.price_unit
                line._onchange_product_id()
                line.price_unit = price_unit
            invoice_vals = inv_new._convert_to_write(inv_new._cache)
            invoice_vals.pop('line_ids', None)

            invoices_vals_per_type.setdefault(invoice_vals['type'], [])
            invoices_vals_per_type[invoice_vals['type']].append(invoice_vals)

        # Create invoices.
        moves = None
        for invoice_type, invoices_vals in invoices_vals_per_type.items():
            invoices = invoices_ctx.with_context(default_type=invoice_type).create(invoices_vals)
            if moves:
                moves += invoices
            else:
                moves = invoices
        return moves

    def _inter_company_prepare_invoice_data(self, company, invoice_type):
        ''' Get values to create the invoice.
        /!\ Doesn't care about lines, see '_inter_company_prepare_invoice_line_data'.
        :param company: The targeted company.
        :return: Python dictionary of values.
        '''
        self.ensure_one()
        delivery_partner_id = self.company_id.partner_id.address_get(['delivery'])['delivery']
        new_fiscal_position_id = self.env['account.fiscal.position'].with_context(force_company=company.id).get_fiscal_position(
        self.company_id.partner_id.id, delivery_id=delivery_partner_id)
        return {
            'type': invoice_type,
            'ref': self.ref,
            'partner_id': self.company_id.partner_id.id,
            'currency_id': self.currency_id.id,
            'auto_generated': True,
            'auto_invoice_id': self.id,
            'invoice_date': self.invoice_date,
            'invoice_payment_ref': self.invoice_payment_ref,
            'invoice_origin': _('%s Invoice: %s') % (self.company_id.name, self.name),
            'fiscal_position_id': new_fiscal_position_id,
        }


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _inter_company_prepare_invoice_line_data(self, company):
        ''' Get values to create the invoice line.
        :param company: The targeted company.
        :return: Python dictionary of values.
        '''
        self.ensure_one()

        vals = {
            'display_type': self.display_type,
            'sequence': self.sequence,
            'name': self.name,
            'product_id': self.product_id.id,
            'product_uom_id': self.product_uom_id.id,
            'quantity': self.quantity,
            'discount': self.discount,
            'price_unit': self.price_unit,
            'analytic_account_id': self.analytic_account_id.id,
            'analytic_tag_ids': [(6, 0, self.analytic_tag_ids.ids)],
        }
        # Ensure no account will be set at creation
        if self.display_type:
            vals['account_id'] = False
        return vals
