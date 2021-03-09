# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    rule_type = fields.Selection(related='company_id.rule_type', readonly=False)
    applicable_on = fields.Selection(related='company_id.applicable_on', readonly=False)
    auto_validation = fields.Boolean(related='company_id.auto_validation', readonly=False)
    intercompany_user_id = fields.Many2one(related='company_id.intercompany_user_id', readonly=False, required=True)
    rules_company_id = fields.Many2one(related='company_id', string='Select Company', readonly=True)
    warehouse_id = fields.Many2one(related='company_id.warehouse_id', string='Warehouse For Purchase Orders', readonly=False, domain=lambda self: [('company_id', '=', self.env.company.id)])
    intercompany_transaction_message = fields.Char()

    @api.onchange('rule_type', 'applicable_on', 'auto_validation', 'warehouse_id')
    def onchange_intercompany_transaction_message(self):
        self.intercompany_transaction_message = self.company_id._intercompany_transaction_message(self.rule_type, self.auto_validation, self.applicable_on, self.warehouse_id)

    @api.onchange('rule_type')
    def onchange_rule_type(self):
        if self.rule_type != 'so_and_po':
            self.applicable_on = False
            self.auto_validation = False
            self.warehouse_id = False
        else:
            warehouse_id = self.warehouse_id or self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
            self.warehouse_id = warehouse_id
            self.applicable_on = 'sale_purchase'
