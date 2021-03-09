# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class Company(models.Model):
    _inherit = 'res.company'

    def _default_consolidation_color(self):
        return self.search_count([]) % 12

    """The color used to color mapped accounts in consolidation account tree view"""
    consolidation_color = fields.Integer('Accounts color', required=False, store=True, default=_default_consolidation_color)

    account_consolidation_currency_is_different = fields.Boolean(
        compute='_compute_account_consolidation_currency_is_different')

    # ONBOARDING
    # Global onboarding state
    consolidation_dashboard_onboarding_state = fields.Selection(
        [('not_done', "Not done"), ('just_done', "Just done"), ('done', "Done"), ('closed', "Closed")],
        string="State Of The Account Consolidation Dashboard Onboarding Panel", default='not_done')

    # Onboarding steps states
    consolidation_setup_consolidation_state = fields.Selection(
        [('not_done', "Not done"), ('just_done', "Just done"), ('done', "Done")],
        string="State Of The Onboarding Consolidation Step", default='not_done')
    consolidation_setup_ccoa_state = fields.Selection(
        [('not_done', "Not done"), ('just_done', "Just done"), ('done', "Done")],
        string="State Of The Onboarding Consolidated Chart Of Account Step", default='not_done')
    consolidation_create_period_state = fields.Selection(
        [('not_done', "Not done"), ('just_done', "Just done"), ('done', "Done")],
        string="State Of The Onboarding Create Period Step", default='not_done')

    @api.depends('currency_id')
    @api.depends_context('consolidation_currency_id')
    def _compute_account_consolidation_currency_is_different(self):
        for record in self:
            record.account_consolidation_currency_is_different = self._context.get('consolidation_currency_id') != record.currency_id.id

    def action_open_mapping(self):
        # Only needed because the action is called via a button and we need to set a domain and button does not allow it
        """
        Open mapping view for this company.
        :return: the action to execute
        """
        self.ensure_one()
        action = self.env.ref('account_consolidation.account_mapping_action').read()[0]
        action.update({
            'domain': [('company_id', '=', self.id)],
            'display_name': _('Account Mapping: ') + self.name,
        })
        return action

    def action_open_rate_ranges(self):
        # Only needed because the action is called via a button and we need to set a domain and button does not allow it
        """
        Open historical rate ranges tree view for this company.
        :return: the action to execute
        """
        self.ensure_one()
        action = self.env.ref('account_consolidation.consolidation_rate_action').read()[0]
        action.update({
            'context': {
                'default_chart_id': self.env.context.get('chart_id', False),
                'search_default_chart_id': self.env.context.get('chart_id', False),
                'default_company_id': self.id,
                'search_default_company_id': self.id
            },
            'domain': [('company_id', '=', self.id)],
            'display_name': _('Historical Rates: ') + self.name,
        })
        return action

    def get_and_update_consolidation_dashboard_onboarding_state(self):
        """
        This method is called on the controller rendering method and ensures that the animations
        are displayed only one time.
        :return: the state of the onboarding.
        """
        return self.get_and_update_onbarding_state('consolidation_dashboard_onboarding_state', [
            'consolidation_setup_consolidation_state',
            'consolidation_setup_ccoa_state',
            'consolidation_create_period_state',
        ])
