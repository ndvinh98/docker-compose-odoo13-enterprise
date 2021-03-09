# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import odoo.addons.decimal_precision as dp


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_mx_edi_customs_number = fields.Char(
        help='Optional field for entering the customs information in the case '
        'of first-hand sales of imported goods or in the case of foreign trade'
        ' operations with goods or services.\n'
        'The format must be:\n'
        ' - 2 digits of the year of validation followed by two spaces.\n'
        ' - 2 digits of customs clearance followed by two spaces.\n'
        ' - 4 digits of the serial number followed by two spaces.\n'
        ' - 1 digit corresponding to the last digit of the current year, '
        'except in case of a consolidated customs initiated in the previous '
        'year of the original request for a rectification.\n'
        ' - 6 digits of the progressive numbering of the custom.',
        string='Customs number',
        copy=False)
    l10n_mx_edi_tariff_fraction_id = fields.Many2one(
        'l10n_mx_edi.tariff.fraction', 'Tariff Fraction', store=True,
        related='product_id.l10n_mx_edi_tariff_fraction_id', readonly=True,
        compute_sudo=True,
        help='It is used to express the key of the tariff fraction '
        'corresponding to the description of the product to export.')
    l10n_mx_edi_umt_aduana_id = fields.Many2one(
        'uom.uom', 'UMT Aduana', store=True,
        related='product_id.l10n_mx_edi_umt_aduana_id', readonly=True,
        compute_sudo=True,
        help='Used in complement "Comercio Exterior" to indicate in the '
        'products the TIGIE Units of Measurement. It is based in the SAT '
        'catalog.')
    l10n_mx_edi_qty_umt = fields.Float(
        'Qty UMT', help='Quantity expressed in the UMT from product. It is '
        'used in the attribute "CantidadAduana" in the CFDI',
        digits='Product Unit of Measure')
    l10n_mx_edi_price_unit_umt = fields.Float(
        'Unit Value UMT', help='Unit value expressed in the UMT from product. '
        'It is used in the attribute "ValorUnitarioAduana" in the CFDI')

    def reconcile(self, writeoff_acc_id=False, writeoff_journal_id=False):
        """Create payment complement with a full reconciliation"""
        res = super(AccountMoveLine, self).reconcile(
            writeoff_acc_id, writeoff_journal_id)
        # return if the call is not from a manual reconciliation
        if not self._context.get('l10n_mx_edi_manual_reconciliation', True):
            return res
        for pay in self.mapped('payment_id'):
            pay.write({'invoice_ids': [
                (6, 0, pay.reconciled_invoice_ids.ids)]})
            if pay.l10n_mx_edi_is_required() and pay.l10n_mx_edi_pac_status != 'signed':
                pay.l10n_mx_edi_cfdi_name = ('%s-%s-MX-Payment-10.xml' % (
                    pay.journal_id.code, pay.name))
                pay._l10n_mx_edi_retry()
        return res

    @api.constrains('l10n_mx_edi_customs_number')
    def _check_l10n_mx_edi_customs_number(self):
        """Check the validity of the 'l10n_mx_edi_customs_number' field."""
        pattern = re.compile(r'[0-9]{2}  [0-9]{2}  [0-9]{4}  [0-9]{7}')
        invalid_product_names = []
        for line in self.filtered(lambda line: line.l10n_mx_edi_customs_number):
            for ped in line.l10n_mx_edi_customs_number.split(','):
                if not pattern.match(ped.strip()):
                    invalid_product_names.append(line.product_id.name)
        if invalid_product_names:
            help_message = self.filtered(
                lambda line: not line.exclude_from_invoice_tab).fields_get().get(
                    'l10n_mx_edi_customs_number').get('help').split('\n', 1)[1]
            raise ValidationError(_(
                'Error in the products:\n%s\n\n The format of the customs '
                'number is incorrect. %s\n For example: 15  48  3009  0001234') % (
                    '\n'.join(invalid_product_names), help_message))

    def _set_price_unit_umt(self):
        for res in self:
            res.l10n_mx_edi_price_unit_umt = round(
                res.quantity * res.price_unit / res.l10n_mx_edi_qty_umt
                if res.l10n_mx_edi_qty_umt else
                res.l10n_mx_edi_price_unit_umt, 2)

    @api.onchange('quantity', 'product_id', 'l10n_mx_edi_umt_aduana_id')
    def onchange_quantity(self):
        """When change the quantity by line, update the QTY in the UMT"""
        for res in self.filtered(
                lambda l: l.move_id.l10n_mx_edi_external_trade and
                l.product_id):
            pdt_aduana = res.l10n_mx_edi_umt_aduana_id.l10n_mx_edi_code_aduana
            if pdt_aduana == res.product_uom_id.l10n_mx_edi_code_aduana:
                res.l10n_mx_edi_qty_umt = res.quantity
            elif pdt_aduana and '01' in pdt_aduana:
                res.l10n_mx_edi_qty_umt = round(
                    res.product_id.weight * res.quantity, 3)


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    def _get_amount_tax_cash_basis(self, amount, line):
        if (self.env.company.country_id != self.env.ref('base.mx') or
                not line.currency_id or not self.debit_move_id.currency_id or
                not self.credit_move_id.currency_id):
            return (super(AccountPartialReconcile, self)
                    ._get_amount_tax_cash_basis(amount, line))

        aml_obj = self.env['account.move.line']
        aml_ids = (self.debit_move_id | self.credit_move_id).ids
        # Use the payment date to compute currency conversion. When reconciling
        # an invoice and a credit note - we will use the greatest date of them.
        inv_types = self.env['account.move'].get_invoice_types()
        domain = [('id', 'in', aml_ids), ('move_id.type', 'not in', inv_types)]
        move_date = aml_obj.search(domain, limit=1, order="date desc").date
        if not move_date:
            domain.pop()
            move_date = aml_obj.search(domain, limit=1, order="date desc").date
        return (
            line.amount_currency and line.balance and line.currency_id._convert(  # noqa
                line.amount_currency * amount / line.balance,
                line.company_id.currency_id, line.company_id, move_date) or 0.0)  # noqa
