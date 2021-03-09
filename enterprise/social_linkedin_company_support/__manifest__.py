# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "LinkedIn Company Support",
    'summary': "Post on your LinkedIn company pages instead of you personnal accounts",
    'description': """
This module intends to add support for company pages and remove the support of personal accounts.
This is done to prepare the next iteration of the social_linkedin module that will allow a full "Streams" support,
meaning you will be able to read your posts (and not only publish them), but only for company accounts.
As we don't want existing users to keep adding their personal accounts to remove them later, we add a technical
module in order to minimize impact and support.
""",
    'version': '1.0',
    'depends': ['social_linkedin'],
    'category': 'Hidden',
    'auto_install': True,
    'post_init_hook': '_remove_existing_linkedin_account',
}
