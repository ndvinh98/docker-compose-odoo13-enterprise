# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.tests import common


class TestInterCompanyRulesCommon(common.SavepointCase):

    @classmethod
    def setUpClass(cls):
        super(TestInterCompanyRulesCommon, cls).setUpClass()

        # Create a new company named company_a
        cls.company_a = cls.env['res.company'].create({
            'name': 'Company A',
            'currency_id': cls.env.ref('base.EUR').id,
        })

        # Set warehouse on company A
        cls.company_a.warehouse_id = cls.env['stock.warehouse'].search([('company_id', '=', cls.company_a.id)])

        # Create a new company named company_b
        cls.company_b = cls.env['res.company'].create({
            'name': 'Company B',
            'currency_id': cls.env.ref('base.EUR').id,
        })

        # Set warehouse on company B
        cls.company_b.warehouse_id = cls.env['stock.warehouse'].search([('company_id', '=', cls.company_b.id)])

        # Create a new product named product_consultant
        cls.product_consultant = cls.env['product.product'].create({
            'name': 'Service',
            'uom_id': cls.env.ref('uom.product_uom_hour').id,
            'uom_po_id': cls.env.ref('uom.product_uom_hour').id,
            'categ_id': cls.env.ref('product.product_category_all').id,
            'type': 'service',
            'company_id': False
        })

        # Create user of company_a
        cls.res_users_company_a = cls.env['res.users'].create({
            'name': 'User A',
            'login': 'usera',
            'email': 'usera@yourcompany.com',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('sales_team.group_sale_salesman').id,
                cls.env.ref('purchase.group_purchase_user').id,
                cls.env.ref('account.group_account_user').id,
                cls.env.ref('account.group_account_manager').id
            ])]
        })

        # Create user of company_b
        cls.res_users_company_b = cls.env['res.users'].create({
            'name': 'User B',
            'login': 'userb',
            'email': 'userb@yourcompany.com',
            'company_id': cls.company_b.id,
            'company_ids': [(6, 0, [cls.company_b.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('sales_team.group_sale_salesman').id,
                cls.env.ref('purchase.group_purchase_user').id,
                cls.env.ref('account.group_account_user').id
            ])]
        })
