# Author: Eimantas Nėjus. Copyright: JSC Focusate.
# Co-Authors: Silvija Butko, Andrius Laukavičius. Copyright: JSC Focusate
# See LICENSE file for full copyright and licensing details.
{
    'name': 'LT - Accounting Reports',
    'version': '1.0.0',
    'summary': 'accounting, report, Lithuanian',
    'description': """
        Accounting reports for Lithuania

        Contains Balance Sheet, Profit/Loss reports
    """,
    'license': 'OEEL-1',
    'author': "Focusate",
    'website': "http://www.focusate.eu",
    'category': 'Localization',
    'depends': [
        'account_reports',
        'l10n_lt'
    ],
    'data': [
        'data/account_financial_html_report_data.xml',
    ],
    'auto_install': True,
    'installable': True,
}
