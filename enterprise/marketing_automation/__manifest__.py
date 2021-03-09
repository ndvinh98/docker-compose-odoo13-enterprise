# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "Marketing Automation",
    'version': "1.0",
    'summary': "Build automated mailing campaigns",
    'website': 'https://www.odoo.com/page/marketing-automation',
    'category': "Marketing/Marketing Automation",
    'depends': ['mass_mailing'],
    'data': [
        'security/marketing_automation_security.xml',
        'security/ir.model.access.csv',
        'views/assets.xml',
        'views/ir_model_views.xml',
        'views/marketing_automation_menus.xml',
        'wizard/marketing_campaign_test_views.xml',
        'views/link_tracker_views.xml',
        'views/mailing_mailing_views.xml',
        'views/mailing_trace_views.xml',
        'views/marketing_activity_views.xml',
        'views/marketing_participant_views.xml',
        'views/marketing_trace_views.xml',
        'views/marketing_campaign_views.xml',
        'data/ir_cron_data.xml',
    ],
    'demo': [
        'data/marketing_automation_demo.xml'
    ],
    'application': True,
    'license': 'OEEL-1',
    'uninstall_hook': 'uninstall_hook',
}
