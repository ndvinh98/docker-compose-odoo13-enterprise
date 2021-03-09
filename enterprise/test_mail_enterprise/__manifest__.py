# -*- coding: utf-8 -*-

{
    'name': 'Mail Tests (Enterprise)',
    'version': '1.0',
    'category': 'Hidden',
    'sequence': 9876,
    'summary': 'Mail Tests: performances and tests specific to mail with all sub-modules',
    'description': """This module contains tests related to mail. Those are
contained in a separate module as it contains models used only to perform
tests independently to functional aspects of other models. Moreover most of
modules build on mail (sms, snailmail, mail_enterprise) are set as dependencies
in order to test the whole mail codebase. """,
    'depends': [
        'mail',
        'mail_bot',
        'mass_mailing',
        'marketing_automation',
        'ocn_client',
        'snailmail',
        'sms',
        'test_mail',
        'test_mail_full',
        'test_mass_mailing',
    ],
    'data': [
    ],
    'demo': [
    ],
    'installable': True,
    'application': False,
}
