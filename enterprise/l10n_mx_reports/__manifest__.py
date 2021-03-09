# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Odoo Mexican Localization Reports",
    "summary": """
        Electronic accounting reports
            - COA
            - Trial Balance
        DIOT Report
    """,
    "version": "1.0",
    "author": "Vauxoo",
    "category": "Accounting/Accounting",
    "website": "http://www.vauxoo.com",
    "license": "OEEL-1",
    "depends": [
        "account_reports",
        "l10n_mx",
    ],
    "demo": [
        "demo/res_company_demo.xml",
        "demo/res_partner_demo.xml",
    ],
    "data": [
        "data/account_financial_report_data.xml",
        "data/country_data.xml",
        "data/templates/cfdicoa.xml",
        "data/templates/cfdibalance.xml",
        "views/res_country_view.xml",
        "views/res_partner_view.xml",
        "views/report_financial.xml",
    ],
    "installable": True,
    "auto_install": True,
}
