# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import Form, TransactionCase


class TestCommissionsSetup(TransactionCase):

    def _setup_accounting(self):
        self.account_type_receivable = self.env['account.account.type'].create({
            'name': 'receivable',
            'type': 'receivable',
            'internal_group': 'income',
        })

        self.account_receivable = self.env['account.account'].create({
            'code': '...',
            'name': '...',
            'user_type_id': self.account_type_receivable.id,
            'company_id': self.company.id,
            'reconcile': True,
        })

        self.account_sale = self.env['account.account'].create({
            'code': 'SAL',
            'name': 'sales',
            'reconcile': True,
            'user_type_id': self.env.ref('account.data_account_type_revenue').id,
        })

        self.bank_journal = self.env['account.journal'].create({
            'name': '...',
            'code': '...',
            'type': 'bank',
        })

        self.sale_journal = self.env['account.journal'].create({
            'name': 'sales',
            'code': 'SAL',
            'type': 'sale',
        })

    def _make_partners(self):
        self.referrer = self.env['res.partner'].create({
            'name': 'Referrer',
            'company_id': self.company.id,
            'property_account_payable_id': self.account_receivable.id,
            'property_account_receivable_id': self.account_receivable.id,
        })

        self.customer = self.env['res.partner'].create({
            'name': 'Customer',
            'property_account_payable_id': self.account_receivable.id,
            'property_account_receivable_id': self.account_receivable.id,
            'company_id': self.company.id,
        })

    def _make_products(self):
        # pricelists
        self.eur_20 = self.env['product.pricelist'].create({
            'name': 'EUR 20',
            'currency_id': self.env.ref('base.EUR').id,
        })
        self.usd_8 = self.env['product.pricelist'].create({
            'name': 'USD 8',
            'currency_id': self.env.ref('base.USD').id,
        })

        # subscription templates
        self.template_yearly = self.env['sale.subscription.template'].create({
            'name': 'Odoo yearly',
            'code': 'OY',
            'recurring_rule_type': 'yearly',
            'recurring_interval': 1,
            'recurring_rule_boundary': 'unlimited',
        })

        # odoo sh
        self.odoo_sh = self.env['product.category'].create({
            'name': 'Odoo.SH',
        })

        self.worker = self.env['product.product'].create({
            'name': 'Odoo.sh Worker',
            'categ_id': self.odoo_sh.id,
            'list_price': 100.0,
            'recurring_invoice': True,
            'purchase_ok': True,
            'property_account_income_id': self.account_sale.id,
            'subscription_template_id': self.template_yearly.id
        })

        self.staging = self.env['product.product'].create({
            'name': 'Odoo.sh Staging Branch',
            'categ_id': self.odoo_sh.id,
            'list_price': 30.0,
            'recurring_invoice': True,
            'purchase_ok': True,
            'property_account_income_id': self.account_sale.id,
            'subscription_template_id': self.template_yearly.id
        })

        # apps support
        self.apps_support = self.env['product.category'].create({
            'name': 'Apps Support',
        })

        self.crm = self.env['product.product'].create({
            'name': 'CRM',
            'categ_id': self.apps_support.id,
            'list_price': 20.0,
            'recurring_invoice': True,
            'purchase_ok': True,
            'property_account_income_id': self.account_sale.id,
            'subscription_template_id': self.template_yearly.id
        })

        self.invoicing = self.env['product.product'].create({
            'name': 'Invoicing',
            'categ_id': self.apps_support.id,
            'list_price': 20.0,
            'recurring_invoice': True,
            'purchase_ok': True,
            'property_account_income_id': self.account_sale.id,
            'subscription_template_id': self.template_yearly.id
        })

    def _make_commission_plans(self):
        self.learning_plan = self.env['commission.plan'].create({
            'name': 'Learning Plan',
            'product_id': self.env.ref('partner_commission.product_commission').id,
            'commission_rule_ids': [
                (0, 0, self._make_rule(self.odoo_sh, 10, product=self.worker, pricelist=self.eur_20, is_capped=True, max_comm=150)),
                (0, 0, self._make_rule(self.odoo_sh, 10, product=self.worker, pricelist=self.usd_8, is_capped=True, max_comm=180)),
                (0, 0, self._make_rule(self.apps_support, 10)),
            ],
        })

        self.ready_plan = self.env['commission.plan'].create({
            'name': 'Ready Plan',
            'product_id': self.env.ref('partner_commission.product_commission').id,
            'commission_rule_ids': [
                (0, 0, self._make_rule(self.odoo_sh, 100, product=self.worker, pricelist=self.eur_20, is_capped=True, max_comm=150)),
                (0, 0, self._make_rule(self.odoo_sh, 100, product=self.worker, pricelist=self.usd_8, is_capped=True, max_comm=180)),
                (0, 0, self._make_rule(self.apps_support, 10)),
            ],
        })

        self.silver_plan = self.env['commission.plan'].create({
            'name': 'Silver Plan',
            'product_id': self.env.ref('partner_commission.product_commission').id,
            'commission_rule_ids': [
                (0, 0, self._make_rule(self.odoo_sh, 100, product=self.worker, pricelist=self.eur_20, is_capped=True, max_comm=150)),
                (0, 0, self._make_rule(self.odoo_sh, 100, product=self.worker, pricelist=self.usd_8, is_capped=True, max_comm=180)),
                (0, 0, self._make_rule(self.apps_support, 15)),
            ],
        })

        self.gold_plan = self.env['commission.plan'].create({
            'name': 'Gold Plan',
            'product_id': self.env.ref('partner_commission.product_commission').id,
            'commission_rule_ids': [
                (0, 0, self._make_rule(self.odoo_sh, 100, pricelist=self.eur_20, is_capped=True, max_comm=150)),
                (0, 0, self._make_rule(self.odoo_sh, 100, pricelist=self.usd_8, is_capped=True, max_comm=180)),
                (0, 0, self._make_rule(self.apps_support, 20)),
            ],
        })

        self.greedy_plan = self.env['commission.plan'].create({
            'name': 'Greedy Plan',
            'product_id': self.env.ref('partner_commission.product_commission').id,
            'commission_rule_ids': [
                (0, 0, self._make_rule(self.odoo_sh, 100, pricelist=self.usd_8, is_capped=True, max_comm=18)),
            ],
        })

    def _make_rule(self, category, rate, product=None, template=None, pricelist=None, is_capped=False, max_comm=0):
        return {
            'category_id': category.id,
            'product_id': product.id if product else None,
            'template_id': template.id if template else None,
            'pricelist_id': pricelist.id if pricelist else None,
            'rate': rate,
            'is_capped': is_capped,
            'max_commission': max_comm,
        }

    def _make_grades(self):
        self.learning = self.env['res.partner.grade'].create({
            'name': 'Learning',
            'default_commission_plan_id': self.learning_plan.id,
        })
        self.ready = self.env['res.partner.grade'].create({
            'name': 'Ready',
            'default_commission_plan_id': self.ready_plan.id,
        })
        self.silver = self.env['res.partner.grade'].create({
            'name': 'Silver',
            'default_commission_plan_id': self.silver_plan.id,
        })
        self.gold = self.env['res.partner.grade'].create({
            'name': 'Gold',
            'default_commission_plan_id': self.gold_plan.id,
        })

    def setUp(self):
        super(TestCommissionsSetup, self).setUp()

        self.company = self.env.ref('base.main_company')

        # Test with the following access rights.
        groups = [
            # Internal User
            self.ref('base.group_user'),
            # Billing, implied from base.group_user
            self.ref('account.group_account_invoice'),
            # Sales: User: All Documents
            self.ref('sales_team.group_sale_salesman_all_leads'),
            # Subscription: See Subscriptions
            self.ref('sale_subscription.group_sale_subscription_view'),
            # Show Full Accounting Features
            self.ref('account.group_account_user'),
            # Billing Administrator
            self.ref('account.group_account_manager'),
        ]

        self.salesman = self.env['res.users'].create({
            'name': '...',
            'login': 'sales',
            'email': 'sales@odoo.com',
            'company_id': self.company.id,
            'groups_id': [(6, 0, groups)],
        })

        self._setup_accounting()
        self._make_partners()
        self._make_products()
        self._make_commission_plans()
        self._make_grades()

    # Helpers.

    def purchase(self, spec):
        """Helper that simulates the user-flow and returns the resulting move."""
        self.referrer.grade_id = spec.grade.id
        self.referrer._onchange_grade_id()

        form = Form(self.env['sale.order'].with_user(self.salesman).with_context(tracking_disable=True))
        form.partner_id = self.customer
        form.referrer_id = self.referrer

        for l in spec.lines:
            with form.order_line.new() as line:
                line.name = l.product.name
                line.product_id = l.product
                line.product_uom_qty = l.quantity

        so = form.save()
        if spec.pricelist:
            so.pricelist_id = spec.pricelist
        so.action_confirm()

        inv = so._create_invoices()
        inv.post()
        self._pay_invoice(inv)

        return inv

    def _pay_invoice(self, invoice):
        ctx = {'active_model': 'account.move', 'active_ids': [invoice.id]}
        payment_register = self.env['account.payment.register'].with_user(self.salesman).with_context(ctx).create({
            'journal_id': self.bank_journal.id,
        })
        payment_register.create_payments()


class Spec:
    """Simple data structure to hold the user-flow's input data.
    Attribute `commission` holds the expected resulting commission amount."""
    def __init__(self, grade, lines, pricelist=None, commission=0):
        self.grade = grade
        self.lines = lines
        self.pricelist = pricelist
        self.commission = commission


class Line:
    def __init__(self, product, quantity):
        self.product = product
        self.quantity = quantity
