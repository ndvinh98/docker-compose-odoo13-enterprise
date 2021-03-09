# -*- coding: utf-8 -*-

{
    'name': 'Web Cohort Tests',
    'version': '1.0',
    'category': 'Hidden',
    'sequence': 9876,
    'summary': 'Web cohort Test',
    'description': """This module contains tests related to web cohort. Those are
contained in a separate module as it contains models used only to perform
tests independently to functional aspects of other models. """,
    'depends': ['web_cohort'],
    'data': [
        'security/ir.model.access.csv',
    ],
    'demo': [
    ],
    'installable': True,
    'application': False,
}
