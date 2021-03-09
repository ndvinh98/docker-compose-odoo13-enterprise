# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Employee Referral',
    'version': '1.0',
    'category': 'Human Resources/Referrals',
    'summary': 'Let your employees share job positions and refer their friends',
    'description': """Let your employees share job positions and refer their friends""",
    'website': ' ',
    'depends': ['hr_recruitment', 'link_tracker', 'website_hr_recruitment', 'web_dashboard'],
    'data': [
        'data/data.xml',
        'security/hr_referral_security.xml',
        'security/ir.model.access.csv',
        'views/hr_applicant_views.xml',
        'wizard/hr_referral_link_to_share_views.xml',
        'wizard/hr_referral_send_mail_views.xml',
        'views/hr_job_views.xml',
        'views/hr_recruitment_views.xml',
        'views/hr_referral_onboarding_views.xml',
        'views/hr_referral_level_views.xml',
        'views/hr_referral_friend_views.xml',
        'views/hr_referral_alert_views.xml',
        'views/hr_referral_reward_views.xml',
        'views/hr_referral_templates.xml',
        'views/hr_referral_views.xml',
        'report/hr_referral_report_views.xml',
    ],
    'qweb': [
        'static/src/xml/hr_referral_templates.xml',
    ],
    'demo': ['data/hr_referral_demo.xml'],
    'installable': True,
    'application': True,
    'pre_init_hook': '_pre_init_referral',
    'post_init_hook': '_update_stage',
}
