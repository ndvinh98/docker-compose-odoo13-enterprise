# -*- coding: utf-8 -*-
{
    'name': "web_dashboard",
    'category': 'Hidden',
    'version': '1.0',
    'description':
        """
Odoo Dashboard View.
========================

This module defines the Dashboard view, a new type of reporting view. This view
can embed graph and/or pivot views, and displays aggregate values.
        """,
    'depends': ['web'],
    'data': [
        'views/assets.xml',
    ],
    'qweb': [
        "static/src/xml/dashboard.xml",
    ],
    'license': 'OEEL-1',
}
