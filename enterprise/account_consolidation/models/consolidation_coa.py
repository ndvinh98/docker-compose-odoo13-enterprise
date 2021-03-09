# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.osv import expression
from odoo.exceptions import ValidationError


class ConsolidationChart(models.Model):
    _name = "consolidation.chart"
    _description = "Consolidation chart"

    name = fields.Char(string='Consolidation Name', required=True)
    currency_id = fields.Many2one('res.currency', string="Target Currency", required=True)
    period_ids = fields.One2many('consolidation.period', 'chart_id', string="Analysis Periods")
    period_ids_count = fields.Integer(compute='_compute_period_ids_count', string='# Periods')
    account_ids = fields.One2many('consolidation.account', 'chart_id', 'Consolidation Accounts', copy=True)
    account_ids_count = fields.Integer(compute='_compute_account_ids_count', string='# Accounts')
    group_ids = fields.One2many('consolidation.group', 'chart_id', 'Account Groups')
    group_ids_count = fields.Integer(compute='_compute_group_ids_count', string='# Groups')

    color = fields.Integer('Color Index', help='Used in the kanban view', default=0)
    company_ids = fields.Many2many('res.company', string="Companies")
    children_ids = fields.Many2many('consolidation.chart', 'account_consolidation_inner_rel', 'children_ids',
                                    'parent_ids', string="Sub-consolidations")
    parents_ids = fields.Many2many('consolidation.chart', 'account_consolidation_inner_rel', 'parent_ids',
                                   'children_ids', string="Consolidated In")

    # COMPUTEDS
    @api.depends('account_ids')
    def _compute_account_ids_count(self):
        """
        Compute the amount of consolidation accounts are linked to this chart.
        """
        for record in self:
            record.account_ids_count = len(record.account_ids)

    @api.depends('group_ids')
    def _compute_group_ids_count(self):
        """
        Compute the amount of consolidation account sections are linked to this chart.
        """
        for record in self:
            record.group_ids_count = len(record.group_ids)

    @api.depends('period_ids')
    def _compute_period_ids_count(self):
        """
        Compute the amount of analysis periods are linked to this chart.
        """
        for record in self:
            record.period_ids_count = len(record.period_ids)

    def copy(self, default=None):
        default = dict(default or {})
        default['name'] = self.name + ' (copy)'
        default['color'] = ((self.color if self.color else 0) + 1) % 12
        return super().copy(default)

    # ACTIONS

    def action_open_mapping(self):
        """
        Open mapping view for this chart.
        :return: the action to execute
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'consolidation.account',
            'view_mode': 'tree',
            'views': [[self.env.ref('account_consolidation.consolidation_account_tree_mapping').id, 'list']],
            'domain': [('chart_id', '=', self.id)],
            'context': {},
            'name': _('Account Mapping: ') + self.name,
            'search_view_id': [self.env.ref('account_consolidation.consolidation_account_search_mapping').id, 'search']
        }

    # ONBOARDING
    @api.model
    # Onboarding requires an object method
    def setting_consolidation_action(self):
        """
        Called by the 'Create' button of the setup bar in "first consolidation" step.
        :return: the action to execute
        """
        action = self.env.ref('account_consolidation.consolidation_chart_action_onboarding').read()[0]
        last_chart = self.search([], order="id desc", limit=1)
        if last_chart.id:
            action.update({
                'res_id': last_chart.id,
            })
        return action

    def action_save_onboarding_consolidation_step(self):
        self.env.company.sudo().set_onboarding_step_done('consolidation_setup_consolidation_state')

    @api.model
    def setting_consolidated_chart_of_accounts_action(self):
        """
        Called by the 'Setup' button of the setup bar in "Consolidated Chart of Accounts" step.
        :return: the action to execute
        """
        action = self.env.ref('account_consolidation.consolidation_account_action').read()[0]
        last_chart = self.search([], order="id desc", limit=1)
        action.update({
            'context': {'default_chart_id': last_chart.id, 'search_default_chart_id': last_chart.id},
            'views': [
                (self.env.ref('account_consolidation.consolidation_account_tree_onboarding').id, 'list'),
                (False, 'form')
            ]
        })
        self.env.company.sudo().set_onboarding_step_done('consolidation_setup_ccoa_state')
        return action

    @api.model
    def setting_create_period_action(self):
        """
        Called by the 'Create' button of the setup bar in "first period" step.
        :return: the action to execute
        """
        action = self.env.ref('account_consolidation.consolidation_period_action_onboarding').read()[0]
        last_chart = self.search([], order="id desc", limit=1)
        action.update({'context': {'default_chart_id': last_chart.id}})
        return action


class ConsolidationAccount(models.Model):
    _name = "consolidation.account"
    _description = "Consolidation account"
    _order = 'sequence asc, id'
    _rec_name = 'name'

    def get_default_chart_id(self):
        return self.env['consolidation.chart'].search([], order="id desc", limit=1)

    chart_id = fields.Many2one('consolidation.chart', string="Consolidation", ondelete="cascade", required=True,
                               default=get_default_chart_id)
    name = fields.Char(string='Name', required=True)
    code = fields.Char(size=64, required=False, index=True, copy=False)
    full_name = fields.Char(string='Full Name', compute='_compute_full_name')
    sequence = fields.Integer()

    group_id = fields.Many2one('consolidation.group', string='Group')
    account_ids = fields.Many2many('account.account', string="Accounts")
    currency_mode = fields.Selection([('end', 'Closing Rate'), ('avg', 'Average Rate'), ('hist', 'Historical Rate')],
                                     required=True, default='end', string='Currency Conversion Method')
    line_ids = fields.One2many('consolidation.journal.line', 'account_id', string="Account")

    linked_chart_ids = fields.Many2many('consolidation.chart', store=False, related="chart_id.children_ids")
    company_ids = fields.Many2many('res.company', store=False, related="chart_id.company_ids")

    # HIERARCHY
    #TODO I've no idea what this is for...
    using_ids = fields.Many2many('consolidation.account', 'consolidation_accounts_rel', 'used_in_ids',
                                 'using_ids', string="Consolidation Accounts")
    used_in_ids = fields.Many2many('consolidation.account', 'consolidation_accounts_rel', 'using_ids',
                                   'used_in_ids', string='Consolidated in')
    filtered_used_in_ids = fields.Many2many('consolidation.account', readonly=False,
                                            compute="_compute_filtered_used_in_ids",
                                            search="_search_filtered_used_in_ids",
                                            inverse='_inverse_filtered_used_in_ids',
                                            )

    _sql_constraints = [
        ('code_uniq', 'unique (code, chart_id)',
         "A consolidation account with the same code already exists in this consolidation."),
    ]

    # COMPUTEDS

    @api.depends('group_id', 'name')
    def _compute_full_name(self):
        for record in self:
            if record.group_id:
                record.full_name = '%s / %s' % (record.group_id.name_get()[0][1], record.name)
            else:
                record.full_name = record.name

    @api.depends('used_in_ids')
    @api.depends_context('chart_id')
    def _compute_filtered_used_in_ids(self):
        """
        Compute filtered_used_in_ids field which is the list of consolidation account ids linked to this
        consolidation account filtered to only contains the ones linked to the chart contained in the context
        """
        chart_id = self.env.context.get('chart_id', False)
        for record in self:
            if chart_id:
                record.filtered_used_in_ids = record.used_in_ids.filtered(lambda x: x.chart_id.id == chart_id)
            else:
                record.filtered_used_in_ids = record.used_in_ids.ids

    def _inverse_filtered_used_in_ids(self):
        """
        Allow the write back of filtered field to the not filtered one. This method makes sure to not erase the
        consolidation accounts from other charts.
        """
        chart_id = self.env.context.get('chart_id', False)
        for record in self:
            record.used_in_ids = record.filtered_used_in_ids + record.used_in_ids.filtered(lambda x: x.chart_id.id != (chart_id or False))

    def _search_filtered_used_in_ids(self, operator, operand):
        """
        Allow the "mapped" and "not mapped" filters in the account list views.
        :rtype: list
        """
        if operator in ('!=', '=') and operand == False:
            chart_id = self.env.context.get('chart_id', False)
            domain = [('used_in_ids', '!=', False)]
            if chart_id:
                domain = expression.AND([domain, [('used_in_ids.chart_id', '=', chart_id)]])
            if operator == '=':
                result = self.search_read(domain, ['id'])
                domain = [('id', 'not in', [r['id'] for r in result])]
            return domain
        else:
            return [('used_in_ids', operator, operand)]

    # ORM OVERRIDES

    def name_get(self):
        ret_list = []
        for record in self:
            if record.code:
                name = '%s %s' % (record.code, record.name)
            else:
                name = record.name
            ret_list.append((record.id, name))
        return ret_list

    # HELPERS

    def get_display_currency_mode(self):
        """
        Get the display name of the currency mode of this consolidation account
        :return: the repr string of the currency mode
        :rtype: str
        """
        self.ensure_one()
        return dict(self._fields['currency_mode'].selection).get(self.currency_mode)


class ConsolidationGroup(models.Model):
    _name = "consolidation.group"
    _description = "Consolidation Group"
    _order = 'parent_id asc, sequence asc, name asc'
    _parent_name = "parent_id"
    _parent_store = True

    chart_id = fields.Many2one('consolidation.chart', string="Consolidation", required=True)
    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer()
    show_on_dashboard = fields.Boolean(default=False)
    parent_id = fields.Many2one('consolidation.group', string='Parent')
    child_ids = fields.One2many('consolidation.group', 'parent_id', 'Children')
    parent_path = fields.Char(index=True)
    account_ids = fields.One2many('consolidation.account', 'group_id', 'Consolidation Account')
    line_ids = fields.One2many('consolidation.journal.line', 'group_id', 'Journal lines',
                               related="account_ids.line_ids")

    # CONSTRAINTS
    @api.constrains('child_ids', 'account_ids')
    def _check_unique_type_of_descendant(self):
        """
        Check that the section only have account children or section children but not both.
        """
        for record in self:
            if record.child_ids and len(record.child_ids) > 0 and record.account_ids and len(record.account_ids) > 0:
                raise models.ValidationError(_("An account group can only have accounts or other groups children but not both !"))

    def name_get(self):
        ret_list = []
        for section in self:
            orig_section = section
            name = section.name
            while section.parent_id:
                section = section.parent_id
                name = section.name + " / " + name
            ret_list.append((orig_section.id, name))
        return ret_list
