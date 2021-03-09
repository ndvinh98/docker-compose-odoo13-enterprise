# -*- coding: utf-8 -*-

from odoo import api, models
from odoo.tests.common import Form

TOLERANCE = 0.02  # tolerance applied to the total when searching for a matching purchase order


class AccountMove(models.Model):
    _inherit = ['account.move']

    @api.model
    def _save_form(self, ocr_results, no_ref=False):
        supplier_ocr = ocr_results['supplier']['selected_value']['content'] if 'supplier' in ocr_results else ""
        vat_number_ocr = ocr_results['VAT_Number']['selected_value']['content'] if 'VAT_Number' in ocr_results else ""
        total_ocr = ocr_results['total']['selected_value']['content'] if 'total' in ocr_results else 0.0

        partner_id = self.env["res.partner"].search([("vat", "=ilike", vat_number_ocr)], limit=1)
        if partner_id.exists():
            partner_id = partner_id.id
        else:
            partner_id = self.find_partner_id_with_name(supplier_ocr)
        if self.type == 'in_invoice' and partner_id and total_ocr:
            purchase_id_domain = [('company_id', '=', self.company_id.id), ('partner_id', 'child_of', [partner_id]),
                                  ('amount_total', '>=', total_ocr - TOLERANCE), ('amount_total', '<=', total_ocr + TOLERANCE), ('state', '=', 'purchase')]
            matching_po = self.env['purchase.order'].search(purchase_id_domain)
            if len(matching_po) == 1:
                with Form(self) as move_form:
                    move_form.purchase_id = matching_po
        super(AccountMove, self)._save_form(ocr_results, no_ref=no_ref)
