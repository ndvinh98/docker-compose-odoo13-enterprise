# -*- coding: utf-8 -*-

import datetime
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare, float_round
from odoo.tests.common import Form

from .taxcloud_request import TaxCloudRequest

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    is_taxcloud_configured = fields.Boolean(related='company_id.is_taxcloud_configured', help='Used to determine whether or not to warn the user to configure TaxCloud.')
    is_taxcloud = fields.Boolean(related='fiscal_position_id.is_taxcloud', help='Technical field to determine whether to hide taxes in views or not.')

    def post(self):
        # OVERRIDE

        # Don't change anything on moves used to cancel another ones.
        if self._context.get('move_reverse_cancel'):
            return super(AccountMove, self).post()

        invoices_to_validate = self.filtered(
            lambda move: move.is_sale_document() and move.fiscal_position_id.is_taxcloud)

        if invoices_to_validate:
            for invoice in invoices_to_validate.with_context(taxcloud_authorize_transaction=True):
                invoice.validate_taxes_on_invoice()
        return super(AccountMove, self).post()

    def button_draft(self):
        """At confirmation below, the AuthorizedWithCapture encodes the invoice
           in TaxCloud. Returned cancels it for a refund.
           See https://dev.taxcloud.com/taxcloud/guides/5%20Returned%20Orders
        """
        if self.filtered(lambda inv: inv.type in ['out_invoice', 'out_refund'] and inv.fiscal_position_id.is_taxcloud):
            raise UserError(_("You cannot cancel an invoice sent to TaxCloud.\n"
                              "You need to issue a refund (credit note) for it instead.\n"
                              "This way the tax entries will be cancelled in TaxCloud."))
        return super(AccountMove, self).button_draft()

    @api.model
    def _get_TaxCloudRequest(self, api_id, api_key):
        return TaxCloudRequest(api_id, api_key)

    def validate_taxes_on_invoice(self):
        self.ensure_one()
        company = self.company_id
        shipper = company or self.env.company
        api_id = shipper.taxcloud_api_id
        api_key = shipper.taxcloud_api_key
        request = self._get_TaxCloudRequest(api_id, api_key)

        request.set_location_origin_detail(shipper)
        request.set_location_destination_detail(
            self.env['res.partner'].browse(self._get_invoice_delivery_partner_id()))

        request.set_invoice_items_detail(self)

        response = request.get_all_taxes_values()

        if response.get('error_message'):
            raise ValidationError(
                _('Unable to retrieve taxes from TaxCloud: ') + '\n' +
                response['error_message']
            )

        tax_values = response['values']

        # warning: this is tightly coupled to TaxCloudRequest's _process_lines method
        # do not modify without syncing the other method
        raise_warning = False
        taxes_to_set = []
        for index, line in enumerate(self.invoice_line_ids.filtered(lambda l: not l.display_type)):
            if line._get_taxcloud_price() >= 0.0 and line.quantity >= 0.0:
                price = line.price_unit * (1 - (line.discount or 0.0) / 100.0) * line.quantity
                if not price:
                    tax_rate = 0.0
                else:
                    tax_rate = tax_values[index] / price * 100
                if len(line.tax_ids) != 1 or float_compare(line.tax_ids.amount, tax_rate, precision_digits=3):
                    raise_warning = True
                    tax_rate = float_round(tax_rate, precision_digits=3)
                    tax = self.env['account.tax'].sudo().with_context(active_test=False).search([
                        ('amount', '=', tax_rate),
                        ('amount_type', '=', 'percent'),
                        ('type_tax_use', '=', 'sale'),
                        ('company_id', '=', company.id),
                    ], limit=1)
                    if tax:
                        tax.active = True  # Needs to be active to be included in invoice total computation
                    else:
                        tax = self.env['account.tax'].sudo().with_context(default_company_id=company.id).create({
                            'name': 'Tax %.3f %%' % (tax_rate),
                            'amount': tax_rate,
                            'amount_type': 'percent',
                            'type_tax_use': 'sale',
                            'description': 'Sales Tax',
                        })
                    taxes_to_set.append((index, tax))

        with Form(self) as move_form:
            for index, tax in taxes_to_set:
                with move_form.invoice_line_ids.edit(index) as line_form:
                    line_form.tax_ids.clear()
                    line_form.tax_ids.add(tax)

        if self.env.context.get('taxcloud_authorize_transaction'):
            current_date = fields.Datetime.context_timestamp(self, datetime.datetime.now())

            if self.type == 'out_invoice':
                request.client.service.AuthorizedWithCapture(
                    request.api_login_id,
                    request.api_key,
                    request.customer_id,
                    request.cart_id,
                    self.id,
                    current_date,  # DateAuthorized
                    current_date,  # DateCaptured
                )
            elif self.type == 'out_refund' and self.invoice_origin:
                request.set_invoice_items_detail(self)
                origin_invoice = self.reversed_entry_id
                if origin_invoice:
                    request.client.service.Returned(
                        request.api_login_id,
                        request.api_key,
                        origin_invoice.id,
                        request.cart_items,
                        fields.Datetime.from_string(self.invoice_date)
                    )
                else:
                    _logger.warning(_("The source document on the refund is not valid and thus the refunded cart won't be logged on your taxcloud account"))

        if raise_warning:
            return {'warning': _('The tax rates have been updated, you may want to check it before validation')}
        else:
            return True

    def action_invoice_paid(self):
        for invoice in self:
            company = invoice.company_id
            if invoice.fiscal_position_id.is_taxcloud:
                api_id = company.taxcloud_api_id
                api_key = company.taxcloud_api_key
                request = TaxCloudRequest(api_id, api_key)
                if invoice.type == 'out_invoice':
                    request.client.service.Captured(
                        request.api_login_id,
                        request.api_key,
                        invoice.id,
                    )
                else:
                    request.set_invoice_items_detail(invoice)
                    origin_invoice = self.reversed_entry_id
                    if origin_invoice:
                        request.client.service.Returned(
                            request.api_login_id,
                            request.api_key,
                            origin_invoice.id,
                            request.cart_items,
                            fields.Datetime.from_string(invoice.invoice_date)
                        )
                    else:
                        _logger.warning(_("The source document on the refund is not valid and thus the refunded cart won't be logged on your taxcloud account"))

        return super(AccountMove, self).action_invoice_paid()


class AccountMoveLine(models.Model):
    """Defines getters to have a common facade for order and move lines in TaxCloud."""
    _inherit = 'account.move.line'

    def _get_taxcloud_price(self):
        self.ensure_one()
        return self.price_unit

    def _get_qty(self):
        self.ensure_one()
        return self.quantity
