from odoo import http
from odoo.http import request


class OnboardingController(http.Controller):

    @http.route('/website_sale_dashboard/website_sale_dashboard_onboarding', auth='user', type='json')
    def website_dashboard_onboarding(self):
        """ Returns the `banner` for the website sale onboarding panel.
            It can be empty if the user has closed it or if he doesn't have
            the permission to see it. """

        company = request.env.company
        if not request.env.is_admin() or \
           company.website_sale_dashboard_onboarding_state == 'closed':
            return {}

        return {
            'html': request.env.ref('website_sale_dashboard.website_sale_dashboard_onboarding_panel').render({
                'company': company,
                'state': company.get_and_update_website_sale_dashboard_onboarding_state()
            })
        }
