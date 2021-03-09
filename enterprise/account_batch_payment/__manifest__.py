# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Batch Payment',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'description': """
Batch Payments
=======================================
Batch payments allow grouping payments.

They are for example used to regroup serveral received checks before you deposit them in a single batch to the bank.
The total amount deposited will then appear as a single transaction on your bank statement.
When you proceed with the reconciliation, simply select the corresponding batch payment to reconcile all the payments within.
    """,
    'website': 'https://www.odoo.com/page/accounting',
    'depends' : ['account'],
    'data': [
        'security/account_batch_payment_security.xml',
        'security/ir.model.access.csv',
        'data/account_batch_payment_data.xml',
        'report/account_batch_payment_reports.xml',
        'report/account_batch_payment_report_templates.xml',
        'views/account_batch_payment_templates.xml',
        'views/account_batch_payment_views.xml',
        'views/account_journal_views.xml',
        'wizard/download_wizard_views.xml',
    ],
    'qweb': [
        "static/src/xml/account_reconciliation.xml",
    ],
    'test': [],
    'installable': True,
    'license': 'OEEL-1',
}
