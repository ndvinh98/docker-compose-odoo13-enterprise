# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import Warning


class sale_order(models.Model):

    _inherit = "sale.order"

    auto_generated = fields.Boolean(string='Auto Generated Sales Order', copy=False)
    auto_purchase_order_id = fields.Many2one('purchase.order', string='Source Purchase Order', readonly=True, copy=False)

    def _action_confirm(self):
        """ Generate inter company purchase order based on conditions """
        res = super(sale_order, self)._action_confirm()
        for order in self:
            if not order.company_id: # if company_id not found, return to normal behavior
                continue
            # if company allow to create a Purchase Order from Sales Order, then do it !
            company = self.env['res.company']._find_company_from_partner(order.partner_id.id)
            if company and company.applicable_on in ('sale', 'sale_purchase') and (not order.auto_generated):
                order.inter_company_create_purchase_order(company)
        return res

    def inter_company_create_purchase_order(self, company):
        """ Create a Purchase Order from the current SO (self)
            Note : In this method, reading the current SO is done as sudo, and the creation of the derived
            PO as intercompany_user, minimizing the access right required for the trigger user
            :param company : the company of the created PO
            :rtype company : res.company record
        """
        self = self.with_context(force_company=company.id, company_id=company.id)
        PurchaseOrder = self.env['purchase.order']
        PurchaseOrderLine = self.env['purchase.order.line']

        for rec in self:
            if not company or not rec.company_id.partner_id:
                continue

            # find user for creating and validating SO/PO from company
            intercompany_uid = company.intercompany_user_id and company.intercompany_user_id.id or False
            if not intercompany_uid:
                raise Warning(_('Provide one user for intercompany relation for % ') % company.name)
            # check intercompany user access rights
            if not PurchaseOrder.with_user(intercompany_uid).check_access_rights('create', raise_exception=False):
                raise Warning(_("Inter company user of company %s doesn't have enough access rights") % company.name)

            company_partner = rec.company_id.partner_id.with_user(intercompany_uid)
            # create the PO and generate its lines from the SO
            # read it as sudo, because inter-compagny user can not have the access right on PO
            po_vals = rec.sudo()._prepare_purchase_order_data(company, company_partner)
            inter_user = self.env['res.users'].sudo().browse(intercompany_uid)
            purchase_order = PurchaseOrder.with_context(allowed_company_ids=inter_user.company_ids.ids).with_user(intercompany_uid).create(po_vals)
            for line in rec.order_line.sudo():
                po_line_vals = rec._prepare_purchase_order_line_data(line, rec.date_order,
                    purchase_order.id, company)
                # TODO: create can be done in batch; this may be a performance bottleneck
                PurchaseOrderLine.with_user(intercompany_uid).with_context(allowed_company_ids=inter_user.company_ids.ids).create(po_line_vals)

            # write customer reference field on SO
            if not rec.client_order_ref:
                rec.client_order_ref = purchase_order.name

            # auto-validate the purchase order if needed
            if company.auto_validation:
                purchase_order.with_user(intercompany_uid).button_confirm()

    def _prepare_purchase_order_data(self, company, company_partner):
        """ Generate purchase order values, from the SO (self)
            :param company_partner : the partner representing the company of the SO
            :rtype company_partner : res.partner record
            :param company : the company in which the PO line will be created
            :rtype company : res.company record
        """
        self.ensure_one()
        # find location and warehouse, pick warehouse from company object
        PurchaseOrder = self.env['purchase.order']
        warehouse = company.warehouse_id and company.warehouse_id.company_id.id == company.id and company.warehouse_id or False
        if not warehouse:
            raise Warning(_('Configure correct warehouse for company(%s) from Menu: Settings/Users/Companies' % (company.name)))
        picking_type_id = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'), ('warehouse_id', '=', warehouse.id)
        ], limit=1)
        if not picking_type_id:
            intercompany_uid = company.intercompany_user_id.id
            picking_type_id = PurchaseOrder.with_user(intercompany_uid)._default_picking_type()
        return {
            'name': self.env['ir.sequence'].sudo().next_by_code('purchase.order'),
            'origin': self.name,
            'partner_id': company_partner.id,
            'picking_type_id': picking_type_id.id,
            'date_order': self.date_order,
            'company_id': company.id,
            'fiscal_position_id': company_partner.property_account_position_id.id,
            'payment_term_id': company_partner.property_supplier_payment_term_id.id,
            'auto_generated': True,
            'auto_sale_order_id': self.id,
            'partner_ref': self.name,
            'currency_id': self.currency_id.id
        }

    @api.model
    def _prepare_purchase_order_line_data(self, so_line, date_order, purchase_id, company):
        """ Generate purchase order line values, from the SO line
            :param so_line : origin SO line
            :rtype so_line : sale.order.line record
            :param date_order : the date of the orgin SO
            :param purchase_id : the id of the purchase order
            :param company : the company in which the PO line will be created
            :rtype company : res.company record
        """
        # price on PO so_line should be so_line - discount
        price = so_line.price_unit - (so_line.price_unit * (so_line.discount / 100))

        # computing Default taxes of so_line. It may not affect because of parallel company relation
        taxes = so_line.tax_id
        if so_line.product_id:
            taxes = so_line.product_id.supplier_taxes_id

        # fetch taxes by company not by inter-company user
        company_taxes = taxes.filtered(lambda t: t.company_id == company)
        if purchase_id:
            po = self.env["purchase.order"].with_user(company.intercompany_user_id).browse(purchase_id)
            company_taxes = po.fiscal_position_id.map_tax(company_taxes, so_line.product_id, po.partner_id)

        quantity = so_line.product_id and so_line.product_uom._compute_quantity(so_line.product_uom_qty, so_line.product_id.uom_po_id) or so_line.product_uom_qty
        price = so_line.product_id and so_line.product_uom._compute_price(price, so_line.product_id.uom_po_id) or price
        return {
            'name': so_line.name,
            'order_id': purchase_id,
            'product_qty': quantity,
            'product_id': so_line.product_id and so_line.product_id.id or False,
            'product_uom': so_line.product_id and so_line.product_id.uom_po_id.id or so_line.product_uom.id,
            'price_unit': price or 0.0,
            'company_id': company.id,
            'date_planned': so_line.order_id.expected_date or date_order,
            'taxes_id': [(6, 0, company_taxes.ids)],
            'display_type': so_line.display_type,
        }
