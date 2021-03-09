# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import Warning


class res_company(models.Model):
    _inherit = 'res.company'

    rule_type = fields.Selection([('not_synchronize', 'Do not synchronize'),
        ('invoice_and_refund', 'Synchronize invoices/bills'),
        ('so_and_po', 'Synchronize sales/purchase orders')], string="Rule",
        help='Select the type to setup inter company rules in selected company.', default='not_synchronize')
    applicable_on = fields.Selection([('sale', 'Sales Order'), ('purchase', 'Purchase Order'),
          ('sale_purchase', 'Sales and Purchase Order')], string="Apply on")
    auto_validation = fields.Boolean(string="Automatic Validation")
    intercompany_user_id = fields.Many2one("res.users", string="Assign to", default=SUPERUSER_ID,
        help="Responsible user for creation of documents triggered by intercompany rules.")
    warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse",
        help="Default value to set on Purchase(Sales) Orders that will be created based on Sale(Purchase) Orders made to this company")
    intercompany_transaction_message = fields.Char(compute='_compute_intercompany_transaction_message')

    def _intercompany_transaction_message(self, rule_type, auto_validation, applicable_on, warehouse_id):
        if rule_type == 'not_synchronize':
            return ''
        if rule_type == 'invoice_and_refund':
            return _('Generate a bill/invoice when a company confirms an invoice/bill for %s.') % self.name

        genereted_object = {
            'sale': _('purchase order'),
            'purchase': _('sales order'),
            'sale_purchase': _('purchase/sales order'),
            False: ''
        }
        event_type = {
            'sale': _('sales order'),
            'purchase': _('purchase order'),
            'sale_purchase': _('sales/purchase order'),
            False: ''
        }
        text = {
            'validation': _('validated') if auto_validation else _('draft'),
            'generated_object': genereted_object[applicable_on],
            'warehouse': warehouse_id.display_name,
            'event_type': event_type[applicable_on],
            'company': self.name,
        }
        if applicable_on != 'sale':
            return _('Generate a %(validation)s %(generated_object)s\
                using warehouse %(warehouse)s when a company confirms a %(event_type)s for %(company)s.') % text
        else:
            return _('Generate a %(validation)s %(generated_object)s\
                when a company confirms a %(event_type)s for %(company)s.') % text

    @api.depends('rule_type', 'applicable_on', 'auto_validation', 'warehouse_id', 'name')
    def _compute_intercompany_transaction_message(self):
        self.intercompany_transaction_message = self._intercompany_transaction_message(self.rule_type, self.auto_validation, self.applicable_on, self.warehouse_id)

    @api.model
    def _find_company_from_partner(self, partner_id):
        company = self.sudo().search([('partner_id', '=', partner_id)], limit=1)
        return company or False

    @api.onchange('rule_type')
    def onchange_rule_type(self):
        if self.rule_type != 'so_and_po':
            self.applicable_on = False
            self.auto_validation = False
            self.warehouse_id = False
        else:
            warehouse_id = self.env['stock.warehouse'].search([('company_id', '=', self._origin.id)], limit=1)
            self.warehouse_id = warehouse_id
            self.applicable_on = 'sale_purchase'

    @api.constrains('applicable_on', 'rule_type')
    def _check_intercompany_missmatch_selection(self):
        for rec in self:
            if rec.applicable_on and rec.rule_type == 'invoice_and_refund':
                raise Warning(_('''You cannot select to create invoices based on other invoices
                        simultaneously with another option ('Create Sales Orders when buying to this
                        company' or 'Create Purchase Orders when selling to this company')!'''))
