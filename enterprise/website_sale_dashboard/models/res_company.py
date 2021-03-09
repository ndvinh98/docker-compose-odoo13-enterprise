# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # dashboard onboarding
    website_sale_dashboard_onboarding_state = fields.Selection([('not_done', "Not done"), ('just_done', "Just done"), ('done', "Done"),
                      ('closed', "Closed")], string="State of the website sale onboarding panel",
                     default='not_done')

    @api.model
    def action_close_website_sale_dashboard_onboarding(self):
        """ Mark the website sale dashboard onboarding panel as closed. """
        self.env.company.website_sale_dashboard_onboarding_state = 'closed'

    def get_and_update_website_sale_dashboard_onboarding_state(self):
        """ This method is called on the controller rendering method and ensures that the animations
            are displayed only one time. """
        return self.get_and_update_onbarding_state('website_sale_dashboard_onboarding_state',
            self.get_website_sale_dashboard_onboarding_steps_states_names())

    def get_website_sale_dashboard_onboarding_steps_states_names(self):
        return [
            'base_onboarding_company_state',
            'payment_acquirer_onboarding_state',
            'account_onboarding_sale_tax_state',
        ]
