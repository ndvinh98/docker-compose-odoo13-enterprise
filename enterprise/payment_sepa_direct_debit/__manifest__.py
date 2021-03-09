# -*- coding: utf-8 -*-
{
    'name': "Sepa Direct Debit Payment Acquirer",
    'category': 'Accounting/Accounting',
    'summary': "Payment Acquirer: Sepa Direct Debit",
    'version': '1.0',
    'description': """Sepa Direct Debit Payment Acquirer""",
    'depends': ['account_sepa_direct_debit', 'payment', 'sms'],
    'data': [
        'views/payment_views.xml',
        'views/payment_sepa_direct_debit_templates.xml',
        'data/mail_templates.xml',
        'data/payment_acquirer_data.xml',
    ],
    'installable': True,
    'post_init_hook': 'create_missing_journal_for_acquirers',
}
