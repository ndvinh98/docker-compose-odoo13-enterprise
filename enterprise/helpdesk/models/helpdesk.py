# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from dateutil import relativedelta
from odoo import api, fields, models, _
from odoo.addons.helpdesk.models.helpdesk_ticket import TICKET_PRIORITY
from odoo.addons.http_routing.models.ir_http import slug
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression


class HelpdeskTeam(models.Model):
    _name = "helpdesk.team"
    _inherit = ['mail.alias.mixin', 'mail.thread', 'rating.parent.mixin']
    _description = "Helpdesk Team"
    _order = 'sequence,name'
    _rating_satisfaction_days = False  # takes all existing ratings

    def _default_stage_ids(self):
        return [(0, 0, {'name': 'New', 'sequence': 0, 'template_id': self.env.ref('helpdesk.new_ticket_request_email_template', raise_if_not_found=False) or None})]

    def _default_domain_member_ids(self):
        return [('groups_id', 'in', self.env.ref('helpdesk.group_helpdesk_user').id)]

    name = fields.Char('Helpdesk Team', required=True, translate=True)
    description = fields.Text('About Team', translate=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    sequence = fields.Integer("Sequence", default=10)
    color = fields.Integer('Color Index', default=1)
    stage_ids = fields.Many2many(
        'helpdesk.stage', relation='team_stage_rel', string='Stages',
        default=_default_stage_ids,
        help="Stages the team will use. This team's tickets will only be able to be in these stages.")
    assign_method = fields.Selection([
        ('manual', 'Manually'),
        ('randomly', 'Random'),
        ('balanced', 'Balanced')], string='Assignation Method',
        default='manual', required=True,
        help='Automatic assignation method for new tickets:\n'
             '\tManually: manual\n'
             '\tRandomly: randomly but everyone gets the same amount\n'
             '\tBalanced: to the person with the least amount of open tickets')
    member_ids = fields.Many2many('res.users', string='Team Members', domain=lambda self: self._default_domain_member_ids())
    ticket_ids = fields.One2many('helpdesk.ticket', 'team_id', string='Tickets')

    use_alias = fields.Boolean('Email alias', default=True)
    allow_portal_ticket_closing = fields.Boolean('Ticket closing', help="Allow customers to close their tickets")
    use_website_helpdesk_form = fields.Boolean('Website Form')
    use_website_helpdesk_livechat = fields.Boolean('Live chat',
        help="In Channel: You can create a new ticket by typing /helpdesk [ticket title]. You can search ticket by typing /helpdesk_search [Keyword1],[Keyword2],.")
    use_website_helpdesk_forum = fields.Boolean('Help Center')
    use_website_helpdesk_slides = fields.Boolean('Enable eLearning')
    use_helpdesk_timesheet = fields.Boolean('Timesheet on Ticket', help="This required to have project module installed.")
    use_helpdesk_sale_timesheet = fields.Boolean('Time Reinvoicing', help="Reinvoice the time spent on ticket through tasks.")
    use_credit_notes = fields.Boolean('Refunds')
    use_coupons = fields.Boolean('Coupons')
    use_product_returns = fields.Boolean('Returns')
    use_product_repairs = fields.Boolean('Repairs')
    use_twitter = fields.Boolean('Twitter')
    use_api = fields.Boolean('API')
    use_rating = fields.Boolean('Ratings on tickets')
    portal_show_rating = fields.Boolean('Display Rating on Customer Portal')
    portal_rating_url = fields.Char('URL to Submit an Issue', readonly=True, compute='_compute_portal_rating_url')
    use_sla = fields.Boolean('SLA Policies')
    upcoming_sla_fail_tickets = fields.Integer(string='Upcoming SLA Fail Tickets', compute='_compute_upcoming_sla_fail_tickets')
    unassigned_tickets = fields.Integer(string='Unassigned Tickets', compute='_compute_unassigned_tickets')
    resource_calendar_id = fields.Many2one('resource.calendar', 'Working Hours',
        default=lambda self: self.env.company.resource_calendar_id, domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    @api.depends('name', 'portal_show_rating')
    def _compute_portal_rating_url(self):
        for team in self:
            if team.name and team.portal_show_rating and team.id:
                team.portal_rating_url = '/helpdesk/rating/%s' % slug(team)
            else:
                team.portal_rating_url = False

    def _compute_upcoming_sla_fail_tickets(self):
        ticket_data = self.env['helpdesk.ticket'].read_group([
            ('team_id', 'in', self.ids),
            ('sla_deadline', '!=', False),
            ('sla_deadline', '<=', fields.Datetime.to_string((datetime.date.today() + relativedelta.relativedelta(days=1)))),
        ], ['team_id'], ['team_id'])
        mapped_data = dict((data['team_id'][0], data['team_id_count']) for data in ticket_data)
        for team in self:
            team.upcoming_sla_fail_tickets = mapped_data.get(team.id, 0)

    def _compute_unassigned_tickets(self):
        ticket_data = self.env['helpdesk.ticket'].read_group([('user_id', '=', False), ('team_id', 'in', self.ids), ('stage_id.is_close', '!=', True)], ['team_id'], ['team_id'])
        mapped_data = dict((data['team_id'][0], data['team_id_count']) for data in ticket_data)
        for team in self:
            team.unassigned_tickets = mapped_data.get(team.id, 0)

    @api.onchange('member_ids')
    def _onchange_member_ids(self):
        if not self.member_ids:
            self.assign_method = 'manual'

    @api.onchange('use_alias', 'name')
    def _onchange_use_alias(self):
        if not self.alias_name and self.name and self.use_alias:
            self.alias_name = self.env['mail.alias']._clean_and_make_unique(self.name)
        if not self.use_alias:
            self.alias_name = False

    @api.onchange('use_helpdesk_timesheet')
    def _onchange_use_helpdesk_timesheet(self):
        if not self.use_helpdesk_timesheet:
            self.use_helpdesk_sale_timesheet = False

    @api.constrains('assign_method', 'member_ids')
    def _check_member_assignation(self):
        if not self.member_ids and self.assign_method != 'manual':
            raise ValidationError(_("You must have team members assigned to change the assignation method."))

    # ------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------

    @api.model
    def create(self, vals):
        team = super(HelpdeskTeam, self.with_context(mail_create_nosubscribe=True)).create(vals)
        team.sudo()._check_sla_group()
        team.sudo()._check_modules_to_install()
        # If you plan to add something after this, use a new environment. The one above is no longer valid after the modules install.
        return team

    def write(self, vals):
        result = super(HelpdeskTeam, self).write(vals)
        if 'active' in vals:
            self.with_context(active_test=False).mapped('ticket_ids').write({'active': vals['active']})
        self.sudo()._check_sla_group()
        self.sudo()._check_modules_to_install()
        # If you plan to add something after this, use a new environment. The one above is no longer valid after the modules install.
        return result

    def unlink(self):
        stages = self.mapped('stage_ids').filtered(lambda stage: stage.team_ids <= self)  # remove stages that only belong to team in self
        stages.unlink()
        return super(HelpdeskTeam, self).unlink()

    def _check_sla_group(self):
        for team in self:
            if team.use_sla and not self.user_has_groups('helpdesk.group_use_sla'):
                self.env.ref('helpdesk.group_helpdesk_user').write({'implied_ids': [(4, self.env.ref('helpdesk.group_use_sla').id)]})
            if team.use_sla:
                self.env['helpdesk.sla'].with_context(active_test=False).search([('team_id', '=', team.id), ('active', '=', False)]).write({'active': True})
            else:
                self.env['helpdesk.sla'].search([('team_id', '=', team.id)]).write({'active': False})
                if not self.search_count([('use_sla', '=', True)]):
                    self.env.ref('helpdesk.group_helpdesk_user').write({'implied_ids': [(3, self.env.ref('helpdesk.group_use_sla').id)]})
                    self.env.ref('helpdesk.group_use_sla').write({'users': [(5, 0, 0)]})

    def _check_modules_to_install(self):
        # mapping of field names to module names
        FIELD_MODULE = {
            'use_website_helpdesk_form': 'website_helpdesk_form',
            'use_website_helpdesk_livechat': 'website_helpdesk_livechat',
            'use_website_helpdesk_forum': 'website_helpdesk_forum',
            'use_website_helpdesk_slides': 'website_helpdesk_slides',
            'use_helpdesk_timesheet': 'helpdesk_timesheet',
            'use_helpdesk_sale_timesheet': 'helpdesk_sale_timesheet',
            'use_credit_notes': 'helpdesk_account',
            'use_product_returns': 'helpdesk_stock',
            'use_product_repairs': 'helpdesk_repair',
            'use_coupons': 'helpdesk_sale_coupon',
        }

        # determine the modules to be installed
        expected = [
            mname
            for fname, mname in FIELD_MODULE.items()
            if any(team[fname] for team in self)
        ]
        modules = self.env['ir.module.module']
        if expected:
            STATES = ('installed', 'to install', 'to upgrade')
            modules = modules.search([('name', 'in', expected)])
            modules = modules.filtered(lambda module: module.state not in STATES)

        # other stuff
        for team in self:
            if team.use_rating:
                for stage in team.stage_ids:
                    if stage.is_close and not stage.fold:
                        stage.template_id = self.env.ref('helpdesk.rating_ticket_request_email_template', raise_if_not_found= False)

        if modules:
            modules.button_immediate_install()

        # just in case we want to do something if we install a module. (like a refresh ...)
        return bool(modules)

    # ------------------------------------------------------------
    # Mail Alias Mixin
    # ------------------------------------------------------------

    def get_alias_model_name(self, vals):
        return vals.get('alias_model', 'helpdesk.ticket')

    def get_alias_values(self):
        values = super(HelpdeskTeam, self).get_alias_values()
        values['alias_defaults'] = {'team_id': self.id}
        return values

    # ------------------------------------------------------------
    # Business Methods
    # ------------------------------------------------------------

    @api.model
    def retrieve_dashboard(self):
        domain = [('user_id', '=', self.env.uid)]
        group_fields = ['priority', 'create_date', 'stage_id', 'close_hours']
        list_fields = ['priority', 'create_date', 'stage_id', 'close_hours']
        #TODO: remove SLA calculations if user_uses_sla is false.
        user_uses_sla = self.user_has_groups('helpdesk.group_use_sla') and\
            bool(self.env['helpdesk.team'].search([('use_sla', '=', True), '|', ('member_ids', 'in', self._uid), ('member_ids', '=', False)]))

        if user_uses_sla:
            group_fields.insert(1, 'sla_deadline:year')
            group_fields.insert(2, 'sla_deadline:hour')
            group_fields.insert(3, 'sla_reached_late')
            list_fields.insert(1, 'sla_deadline')
            list_fields.insert(2, 'sla_reached_late')

        HelpdeskTicket = self.env['helpdesk.ticket']
        tickets = HelpdeskTicket.search_read(expression.AND([domain, [('stage_id.is_close', '=', False)]]), ['sla_deadline', 'open_hours', 'sla_reached_late', 'priority'])

        result = {
            'helpdesk_target_closed': self.env.user.helpdesk_target_closed,
            'helpdesk_target_rating': self.env.user.helpdesk_target_rating,
            'helpdesk_target_success': self.env.user.helpdesk_target_success,
            'today': {'count': 0, 'rating': 0, 'success': 0},
            '7days': {'count': 0, 'rating': 0, 'success': 0},
            'my_all': {'count': 0, 'hours': 0, 'failed': 0},
            'my_high': {'count': 0, 'hours': 0, 'failed': 0},
            'my_urgent': {'count': 0, 'hours': 0, 'failed': 0},
            'show_demo': not bool(HelpdeskTicket.search([], limit=1)),
            'rating_enable': False,
            'success_rate_enable': user_uses_sla
        }

        def _is_sla_failed(data):
            deadline = data.get('sla_deadline')
            sla_deadline = fields.Datetime.now() > deadline if deadline else False
            return sla_deadline or data.get('sla_reached_late')

        def add_to(ticket, key="my_all"):
            result[key]['count'] += 1
            result[key]['hours'] += ticket['open_hours']
            if _is_sla_failed(ticket):
                result[key]['failed'] += 1

        for ticket in tickets:
            add_to(ticket, 'my_all')
            if ticket['priority'] == '2':
                add_to(ticket, 'my_high')
            if ticket['priority'] == '3':
                add_to(ticket, 'my_urgent')

        dt = fields.Date.today()
        tickets = HelpdeskTicket.read_group(domain + [('stage_id.is_close', '=', True), ('close_date', '>=', dt)], list_fields, group_fields, lazy=False)
        for ticket in tickets:
            result['today']['count'] += ticket['__count']
            if not _is_sla_failed(ticket):
                result['today']['success'] += ticket['__count']

        dt = fields.Datetime.to_string((datetime.date.today() - relativedelta.relativedelta(days=6)))
        tickets = HelpdeskTicket.read_group(domain + [('stage_id.is_close', '=', True), ('close_date', '>=', dt)], list_fields, group_fields, lazy=False)
        for ticket in tickets:
            result['7days']['count'] += ticket['__count']
            if not _is_sla_failed(ticket):
                result['7days']['success'] += ticket['__count']

        result['today']['success'] = (result['today']['success'] * 100) / (result['today']['count'] or 1)
        result['7days']['success'] = (result['7days']['success'] * 100) / (result['7days']['count'] or 1)
        result['my_all']['hours'] = round(result['my_all']['hours'] / (result['my_all']['count'] or 1), 2)
        result['my_high']['hours'] = round(result['my_high']['hours'] / (result['my_high']['count'] or 1), 2)
        result['my_urgent']['hours'] = round(result['my_urgent']['hours'] / (result['my_urgent']['count'] or 1), 2)

        if self.env['helpdesk.team'].search([('use_rating', '=', True), '|', ('member_ids', 'in', self._uid), ('member_ids', '=', False)]):
            result['rating_enable'] = True
            # rating of today
            domain = [('user_id', '=', self.env.uid)]
            dt = fields.Date.today()
            tickets = self.env['helpdesk.ticket'].search(domain + [('stage_id.is_close', '=', True), ('close_date', '>=', dt)])
            activity = tickets.rating_get_grades()
            total_rating = self._compute_activity_avg(activity)
            total_activity_values = sum(activity.values())
            team_satisfaction = round((total_rating / total_activity_values if total_activity_values else 0), 2) *10
            if team_satisfaction:
                result['today']['rating'] = team_satisfaction

            # rating of last 7 days (6 days + today)
            dt = fields.Datetime.to_string((datetime.date.today() - relativedelta.relativedelta(days=6)))
            tickets = self.env['helpdesk.ticket'].search(domain + [('stage_id.is_close', '=', True), ('close_date', '>=', dt)])
            activity = tickets.rating_get_grades()
            total_rating = self._compute_activity_avg(activity)
            total_activity_values = sum(activity.values())
            team_satisfaction_7days = round((total_rating / total_activity_values if total_activity_values else 0), 2) * 10
            if team_satisfaction_7days:
                result['7days']['rating'] = team_satisfaction_7days
        return result

    def _action_view_rating(self, period=False, only_my_closed=False):
        """ return the action to see all the rating about the tickets of the Team
            :param period: either 'today' or 'seven_days' to include (or not) the tickets closed in this period
            :param only_my_closed: True will include only the ticket of the current user in a closed stage
        """
        domain = [('team_id', 'in', self.ids)]

        if period == 'seven_days':
            domain += [('close_date', '>=', fields.Datetime.to_string((datetime.date.today() - relativedelta.relativedelta(days=6))))]
        elif period == 'today':
            domain += [('close_date', '>=', fields.Datetime.to_string(datetime.date.today()))]

        if only_my_closed:
            domain += [('user_id', '=', self._uid), ('stage_id.is_close', '=', True)]

        ticket_ids = self.env['helpdesk.ticket'].search(domain).ids
        action = self.env.ref('rating.action_view_rating').read()[0]
        action['domain'] = [('res_id', 'in', ticket_ids), ('rating', '!=', -1), ('res_model', '=', 'helpdesk.ticket'), ('consumed', '=', True)]
        return action

    @api.model
    def action_view_rating_today(self):
        #  call this method of on click "Customer Rating" button on dashbord for today rating of teams tickets
        return self.search(['|', ('member_ids', 'in', self._uid), ('member_ids', '=', False)])._action_view_rating(period='today', only_my_closed=True)

    @api.model
    def action_view_rating_7days(self):
        #  call this method of on click "Customer Rating" button on dashbord for last 7days rating of teams tickets
        return self.search(['|', ('member_ids', 'in', self._uid), ('member_ids', '=', False)])._action_view_rating(period='seven_days', only_my_closed=True)

    def action_view_all_rating(self):
        """ return the action to see all the rating about the all sort of activity of the team (tickets) """
        return self._action_view_rating()

    def action_unhappy_rating_ticket(self):
        self.ensure_one()
        action = self.env.ref('helpdesk.helpdesk_ticket_action_main').read()[0]
        action['domain'] = [('team_id', '=', self.id), ('user_id', '=', self.env.uid), ('rating_ids.rating', '=', 1)]
        action['context'] = {'default_team_id': self.id}
        return action

    @api.model
    def _compute_activity_avg(self, activity):
        # compute average base on all rating value
        # like: 5 great, 2 okey, 1 bad
        # great = 10, okey = 5, bad = 0
        # (5*10) + (2*5) + (1*0) = 60 / 8 (nuber of activity for rating)
        great = activity['great'] * 10.00
        okey = activity['okay'] * 5.00
        bad = activity['bad'] * 0.00
        return great + okey + bad

    def _determine_user_to_assign(self):
        """ Get a dict with the user (per team) that should be assign to the nearly created ticket according to the team policy
            :returns a mapping of team identifier with the "to assign" user (maybe an empty record).
            :rtype : dict (key=team_id, value=record of res.users)
        """
        result = dict.fromkeys(self.ids, self.env['res.users'])
        for team in self:
            member_ids = sorted(team.member_ids.ids)
            if member_ids:
                if team.assign_method == 'randomly':  # randomly means new tickets get uniformly distributed
                    last_assigned_user = self.env['helpdesk.ticket'].search([('team_id', '=', team.id)], order='create_date desc, id desc', limit=1).user_id
                    index = 0
                    if last_assigned_user and last_assigned_user.id in member_ids:
                        previous_index = member_ids.index(last_assigned_user.id)
                        index = (previous_index + 1) % len(member_ids)
                    result[team.id] = self.env['res.users'].browse(member_ids[index])
                elif team.assign_method == 'balanced':  # find the member with the least open ticket
                    ticket_count_data = self.env['helpdesk.ticket'].read_group([('stage_id.is_close', '=', False), ('user_id', 'in', member_ids), ('team_id', '=', team.id)], ['user_id'], ['user_id'])
                    open_ticket_per_user_map = dict.fromkeys(member_ids, 0)  # dict: user_id -> open ticket count
                    open_ticket_per_user_map.update((item['user_id'][0], item['user_id_count']) for item in ticket_count_data)
                    result[team.id] = self.env['res.users'].browse(min(open_ticket_per_user_map, key=open_ticket_per_user_map.get))
        return result

    def _determine_stage(self):
        """ Get a dict with the stage (per team) that should be set as first to a created ticket
            :returns a mapping of team identifier with the stage (maybe an empty record).
            :rtype : dict (key=team_id, value=record of helpdesk.stage)
        """
        result = dict.fromkeys(self.ids, self.env['helpdesk.stage'])
        for team in self:
            result[team.id] = self.env['helpdesk.stage'].search([('team_ids', 'in', team.id)], order='sequence', limit=1)
        return result

    def _get_closing_stage(self):
        """
            Return the first closing kanban stage or the last stage of the pipe if none
        """
        closed_stage = self.stage_ids.filtered(lambda stage: stage.is_close)
        if not closed_stage:
            closed_stage = self.stage_ids[-1]
        return closed_stage



class HelpdeskStage(models.Model):
    _name = 'helpdesk.stage'
    _description = 'Helpdesk Stage'
    _order = 'sequence, id'

    def _default_team_ids(self):
        team_id = self.env.context.get('default_team_id')
        if team_id:
            return [(4, team_id, 0)]

    name = fields.Char('Stage Name', required=True, translate=True)
    description = fields.Text(translate=True)
    sequence = fields.Integer('Sequence', default=10)
    is_close = fields.Boolean(
        'Closing Stage',
        help='Tickets in this stage are considered as done. This is used notably when '
             'computing SLAs and KPIs on tickets.')
    fold = fields.Boolean(
        'Folded in Kanban',
        help='This stage is folded in the kanban view when there are no records in that stage to display.')
    team_ids = fields.Many2many(
        'helpdesk.team', relation='team_stage_rel', string='Team',
        default=_default_team_ids,
        help='Specific team that uses this stage. Other teams will not be able to see or use this stage.')
    template_id = fields.Many2one(
        'mail.template', 'Email Template',
        domain="[('model', '=', 'helpdesk.ticket')]",
        help="Automated email sent to the ticket's customer when the ticket reaches this stage.")
    legend_blocked = fields.Char(
        'Red Kanban Label', default=lambda s: _('Blocked'), translate=True, required=True,
        help='Override the default value displayed for the blocked state for kanban selection, when the task or issue is in that stage.')
    legend_done = fields.Char(
        'Green Kanban Label', default=lambda s: _('Ready for Next Stage'), translate=True, required=True,
        help='Override the default value displayed for the done state for kanban selection, when the task or issue is in that stage.')
    legend_normal = fields.Char(
        'Grey Kanban Label', default=lambda s: _('In Progress'), translate=True, required=True,
        help='Override the default value displayed for the normal state for kanban selection, when the task or issue is in that stage.')

    def unlink(self):
        stages = self
        default_team_id = self.env.context.get('default_team_id')
        if default_team_id:
            shared_stages = self.filtered(lambda x: len(x.team_ids) > 1 and default_team_id in x.team_ids.ids)
            tickets = self.env['helpdesk.ticket'].with_context(active_test=False).search([('team_id', '=', default_team_id), ('stage_id', 'in', self.ids)])
            if shared_stages and not tickets:
                shared_stages.write({'team_ids': [(3, default_team_id)]})
                stages = self.filtered(lambda x: x not in shared_stages)
        return super(HelpdeskStage, stages).unlink()


class HelpdeskSLA(models.Model):
    _name = "helpdesk.sla"
    _order = "name"
    _description = "Helpdesk SLA Policies"

    name = fields.Char('SLA Policy Name', required=True, index=True)
    description = fields.Text('SLA Policy Description')
    active = fields.Boolean('Active', default=True)
    team_id = fields.Many2one('helpdesk.team', 'Team', required=True)
    ticket_type_id = fields.Many2one(
        'helpdesk.ticket.type', "Ticket Type",
        help="Only apply the SLA to a specific ticket type. If left empty it will apply to all types.")
    stage_id = fields.Many2one(
        'helpdesk.stage', 'Target Stage', required=True,
        help='Minimum stage a ticket needs to reach in order to satisfy this SLA.')
    priority = fields.Selection(
        TICKET_PRIORITY, string='Minimum Priority',
        default='0', required=True,
        help='Tickets under this priority will not be taken into account.')
    company_id = fields.Many2one('res.company', 'Company', related='team_id.company_id', readonly=True, store=True)
    time_days = fields.Integer('Days', default=0, required=True, help="Days to reach given stage based on ticket creation date")
    time_hours = fields.Integer('Hours', default=0, required=True, help="Hours to reach given stage based on ticket creation date")

    @api.onchange('time_hours')
    def _onchange_time_hours(self):
        if self.time_hours >= 24:
            self.time_days += self.time_hours / 24
            self.time_hours = self.time_hours % 24
