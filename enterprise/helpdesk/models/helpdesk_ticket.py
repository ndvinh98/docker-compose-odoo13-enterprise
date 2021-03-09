# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime
from datetime import time
from dateutil import relativedelta

from odoo import api, fields, models, tools, _
from odoo.osv import expression
from odoo.exceptions import AccessError
from odoo.osv import expression

TICKET_PRIORITY = [
    ('0', 'All'),
    ('1', 'Low priority'),
    ('2', 'High priority'),
    ('3', 'Urgent'),
]


class HelpdeskTag(models.Model):
    _name = 'helpdesk.tag'
    _description = 'Helpdesk Tags'
    _order = 'name'

    name = fields.Char('Tag Name', required=True)
    color = fields.Integer('Color')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Tag name already exists !"),
    ]


class HelpdeskTicketType(models.Model):
    _name = 'helpdesk.ticket.type'
    _description = 'Helpdesk Ticket Type'
    _order = 'sequence'

    name = fields.Char('Type', required=True, translate=True)
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Type name already exists !"),
    ]


class HelpdeskSLAStatus(models.Model):
    _name = 'helpdesk.sla.status'
    _description = "Ticket SLA Status"
    _table = 'helpdesk_sla_status'
    _order = 'deadline ASC, sla_stage_id'
    _rec_name = 'sla_id'

    ticket_id = fields.Many2one('helpdesk.ticket', string='Ticket', required=True, ondelete='cascade', index=True)
    sla_id = fields.Many2one('helpdesk.sla', required=True, ondelete='cascade')
    sla_stage_id = fields.Many2one('helpdesk.stage', related='sla_id.stage_id', store=True)  # need to be stored for the search in `_sla_reach`
    deadline = fields.Datetime("Deadline", compute='_compute_deadline', compute_sudo=True, store=True)
    reached_datetime = fields.Datetime("Reached Date", help="Datetime at which the SLA stage was reached for the first time")
    status = fields.Selection([('failed', 'Failed'), ('reached', 'Reached'), ('ongoing', 'Ongoing')], string="Status", compute='_compute_status', compute_sudo=True, search='_search_status')
    color = fields.Integer("Color Index", compute='_compute_color')
    exceeded_days = fields.Float("Excedeed Working Days", compute='_compute_exceeded_days', compute_sudo=True, store=True, help="Working days exceeded for reached SLAs compared with deadline. Positive number means the SLA was eached after the deadline.")

    @api.depends('ticket_id.create_date', 'sla_id')
    def _compute_deadline(self):
        for status in self:
            deadline = status.ticket_id.create_date
            working_calendar = status.ticket_id.team_id.resource_calendar_id

            if not working_calendar:
                status.deadline = deadline
                continue

            if status.sla_id.time_days > 0:
                deadline = working_calendar.plan_days(status.sla_id.time_days + 1, deadline, compute_leaves=True)
                # We should also depend on ticket creation time, otherwise for 1 day SLA, all tickets
                # created on monday will have their deadline filled with tuesday 8:00
                create_dt = status.ticket_id.create_date
                deadline = deadline.replace(hour=create_dt.hour, minute=create_dt.minute, second=create_dt.second, microsecond=create_dt.microsecond)

                # Except if ticket creation time is later than the end time of the working day
                deadline_for_working_cal = working_calendar.plan_hours(0, deadline)
                if deadline_for_working_cal and deadline.day < deadline_for_working_cal.day:
                    deadline = deadline.replace(hour=0, minute=0, second=0, microsecond=0)
            # We should execute the function plan_hours in any case because, in a 1 day SLA environment,
            # if I create a ticket knowing that I'm not working the day after at the same time, ticket
            # deadline will be set at time I don't work (ticket creation time might not be in working calendar).
            status.deadline = working_calendar.plan_hours(status.sla_id.time_hours, deadline, compute_leaves=True)

    @api.depends('deadline', 'reached_datetime')
    def _compute_status(self):
        """ Note: this computed field depending on 'now()' is stored, but refreshed by a cron """
        for status in self:
            # if reached_datetime, SLA is finished: either failed or succeeded
            if status.reached_datetime and status.deadline:
                status.status = 'reached' if status.reached_datetime < status.deadline else 'failed'
            # reached a SLA without deadline: ongoing as it is not won if no deadline
            elif status.reached_datetime:
                status.status = 'ongoing'
            # if not finished, deadline should be compared to now()
            else:
                status.status = 'ongoing' if (not status.deadline or status.deadline > fields.Datetime.now()) else 'failed'

    @api.model
    def _search_status(self, operator, value):
        """ Supported operators: '=', 'in' and their negative form. """
        # constants
        datetime_now = fields.Datetime.now()
        positive_domain = {
            'failed': ['|', '&', ('reached_datetime', '=', True), ('deadline', '<=', 'reached_datetime'), '&', ('reached_datetime', '=', False), ('deadline', '<=', fields.Datetime.to_string(datetime_now))],
            'reached': ['&', ('reached_datetime', '=', True), ('reached_datetime', '<', 'deadline')],
            'ongoing': ['&', ('reached_datetime', '=', False), ('deadline', '<=', fields.Datetime.to_string(datetime_now))]
        }
        # in/not in case: we treat value as a list of selection item
        if not isinstance(value, list):
            value = [value]
        # transform domains
        if operator in expression.NEGATIVE_TERM_OPERATORS:
            # "('status', 'not in', [A, B])" tranformed into "('status', '=', C) OR ('status', '=', D)"
            domains_to_keep = [dom for key, dom in positive_domain if key not in value]
            return expression.OR(domains_to_keep)
        else:
            return expression.OR(positive_domain[value_item] for value_item in value)

    @api.depends('status')
    def _compute_color(self):
        for status in self:
            if status.status == 'failed':
                status.color = 1
            elif status.status == 'reached':
                status.color = 10
            else:
                status.color = 0

    @api.depends('deadline', 'reached_datetime')
    def _compute_exceeded_days(self):
        for status in self:
            if status.reached_datetime and status.ticket_id.team_id.resource_calendar_id:
                if status.reached_datetime <= status.deadline:
                    start_dt = status.reached_datetime
                    end_dt = status.deadline
                    factor = -1
                else:
                    start_dt = status.deadline
                    end_dt = status.reached_datetime
                    factor = 1
                duration_data = status.ticket_id.team_id.resource_calendar_id.get_work_duration_data(start_dt, end_dt, compute_leaves=True)
                status.exceeded_days = duration_data['days'] * factor
            else:
                status.exceeded_days = False


class HelpdeskTicket(models.Model):
    _name = 'helpdesk.ticket'
    _description = 'Helpdesk Ticket'
    _order = 'priority desc, id desc'
    _inherit = ['portal.mixin', 'mail.thread.cc', 'utm.mixin', 'rating.mixin', 'mail.activity.mixin']

    @api.model
    def default_get(self, fields):
        result = super(HelpdeskTicket, self).default_get(fields)
        if result.get('team_id') and fields:
            team = self.env['helpdesk.team'].browse(result['team_id'])
            if 'user_id' in fields and 'user_id' not in result:  # if no user given, deduce it from the team
                result['user_id'] = team._determine_user_to_assign()[team.id].id
            if 'stage_id' in fields and 'stage_id' not in result:  # if no stage given, deduce it from the team
                result['stage_id'] = team._determine_stage()[team.id].id
        return result

    def _default_team_id(self):
        team_id = self.env['helpdesk.team'].search([('member_ids', 'in', self.env.uid)], limit=1).id
        if not team_id:
            team_id = self.env['helpdesk.team'].search([], limit=1).id
        return team_id

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        # write the domain
        # - ('id', 'in', stages.ids): add columns that should be present
        # - OR ('team_ids', '=', team_id) if team_id: add team columns
        search_domain = [('id', 'in', stages.ids)]
        if self.env.context.get('default_team_id'):
            search_domain = ['|', ('team_ids', 'in', self.env.context['default_team_id'])] + search_domain

        return stages.search(search_domain, order=order)

    name = fields.Char(string='Subject', required=True, index=True)
    team_id = fields.Many2one('helpdesk.team', string='Helpdesk Team', default=_default_team_id, index=True)
    description = fields.Text()
    active = fields.Boolean(default=True)
    ticket_type_id = fields.Many2one('helpdesk.ticket.type', string="Ticket Type")
    tag_ids = fields.Many2many('helpdesk.tag', string='Tags')
    company_id = fields.Many2one(related='team_id.company_id', string='Company', store=True, readonly=True)
    color = fields.Integer(string='Color Index')
    kanban_state = fields.Selection([
        ('normal', 'Grey'),
        ('done', 'Green'),
        ('blocked', 'Red')], string='Kanban State',
        default='normal', required=True)
    kanban_state_label = fields.Char(compute='_compute_kanban_state_label', string='Column Status', tracking=True)
    legend_blocked = fields.Char(related='stage_id.legend_blocked', string='Kanban Blocked Explanation', readonly=True, related_sudo=False)
    legend_done = fields.Char(related='stage_id.legend_done', string='Kanban Valid Explanation', readonly=True, related_sudo=False)
    legend_normal = fields.Char(related='stage_id.legend_normal', string='Kanban Ongoing Explanation', readonly=True, related_sudo=False)
    user_id = fields.Many2one('res.users', string='Assigned to', tracking=True, domain=lambda self: [('groups_id', 'in', self.env.ref('helpdesk.group_helpdesk_user').id)])
    partner_id = fields.Many2one('res.partner', string='Customer')
    partner_ticket_count = fields.Integer('Number of closed tickets from the same partner', compute='_compute_partner_ticket_count')
    attachment_number = fields.Integer(compute='_compute_attachment_number', string="Number of Attachments")
    is_self_assigned = fields.Boolean("Am I assigned", compute='_compute_is_self_assigned')

    # Used to submit tickets from a contact form
    partner_name = fields.Char(string='Customer Name')
    partner_email = fields.Char(string='Customer Email')

    closed_by_partner = fields.Boolean('Closed by Partner', readonly=True, help="If checked, this means the ticket was closed through the customer portal by the customer.")
    # Used in message_get_default_recipients, so if no partner is created, email is sent anyway
    email = fields.Char(related='partner_email', string='Email on Customer', readonly=False)

    priority = fields.Selection(TICKET_PRIORITY, string='Priority', default='0')
    stage_id = fields.Many2one('helpdesk.stage', string='Stage', ondelete='restrict', tracking=True,
                               group_expand='_read_group_stage_ids', copy=False,
                               index=True, domain="[('team_ids', '=', team_id)]")
    date_last_stage_update = fields.Datetime("Last Stage Update", copy=False, readonly=True)

    # next 4 fields are computed in write (or create)
    assign_date = fields.Datetime("First assignation date")
    assign_hours = fields.Integer("Time to first assignation (hours)", compute='_compute_assign_hours', store=True, help="This duration is based on the working calendar of the team")
    close_date = fields.Datetime("Close date", copy=False)
    close_hours = fields.Integer("Time to close (hours)", compute='_compute_close_hours', store=True, help="This duration is based on the working calendar of the team")
    open_hours = fields.Integer("Open Time (hours)", compute='_compute_open_hours', search='_search_open_hours', help="This duration is not based on the working calendar of the team")

    # SLA relative
    sla_ids = fields.Many2many('helpdesk.sla', 'helpdesk_sla_status', 'ticket_id', 'sla_id', string="SLAs", copy=False)
    sla_status_ids = fields.One2many('helpdesk.sla.status', 'ticket_id', string="SLA Status")
    sla_reached_late = fields.Boolean("Has SLA reached late", compute='_compute_sla_reached_late', compute_sudo=True, store=True)
    sla_deadline = fields.Datetime("SLA Deadline", compute='_compute_sla_deadline', compute_sudo=True, store=True, help="The closest deadline of all SLA applied on this ticket")
    sla_fail = fields.Boolean("Failed SLA Policy", compute='_compute_sla_fail', search='_search_sla_fail')

    use_credit_notes = fields.Boolean(related='team_id.use_credit_notes', string='Use Credit Notes')
    use_coupons = fields.Boolean(related='team_id.use_coupons', string='Use Coupons')
    use_product_returns = fields.Boolean(related='team_id.use_product_returns', string='Use Returns')
    use_product_repairs = fields.Boolean(related='team_id.use_product_repairs', string='Use Repairs')

    # customer portal: include comment and incoming emails in communication history
    website_message_ids = fields.One2many(domain=lambda self: [('model', '=', self._name), ('message_type', 'in', ['email', 'comment'])])

    @api.depends('stage_id', 'kanban_state')
    def _compute_kanban_state_label(self):
        for task in self:
            if task.kanban_state == 'normal':
                task.kanban_state_label = task.legend_normal
            elif task.kanban_state == 'blocked':
                task.kanban_state_label = task.legend_blocked
            else:
                task.kanban_state_label = task.legend_done

    def _compute_access_url(self):
        super(HelpdeskTicket, self)._compute_access_url()
        for ticket in self:
            ticket.access_url = '/my/ticket/%s' % ticket.id

    def _compute_attachment_number(self):
        read_group_res = self.env['ir.attachment'].read_group(
            [('res_model', '=', 'helpdesk.ticket'), ('res_id', 'in', self.ids)],
            ['res_id'], ['res_id'])
        attach_data = { res['res_id']: res['res_id_count'] for res in read_group_res }
        for record in self:
            record.attachment_number = attach_data.get(record.id, 0)

    @api.depends('sla_status_ids.deadline', 'sla_status_ids.reached_datetime')
    def _compute_sla_reached_late(self):
        """ Required to do it in SQL since we need to compare 2 columns value """
        mapping = {}
        if self.ids:
            self.env.cr.execute("""
                SELECT ticket_id, COUNT(id) AS reached_late_count
                FROM helpdesk_sla_status
                WHERE ticket_id IN %s AND deadline < reached_datetime
                GROUP BY ticket_id
            """, (tuple(self.ids),))
            mapping = dict(self.env.cr.fetchall())

        for ticket in self:
            ticket.sla_reached_late = mapping.get(ticket.id, 0) > 0

    @api.depends('sla_status_ids.deadline', 'sla_status_ids.reached_datetime')
    def _compute_sla_deadline(self):
        """ Keep the deadline for the last stage (closed one), so a closed ticket can have a status failed.
            Note: a ticket in a closed stage will probably have no deadline
        """
        for ticket in self:
            deadline = False
            status_not_reached = ticket.sla_status_ids.filtered(lambda status: not status.reached_datetime)
            ticket.sla_deadline = min(status_not_reached.mapped('deadline')) if status_not_reached else deadline

    @api.depends('sla_deadline', 'sla_reached_late')
    def _compute_sla_fail(self):
        now = fields.Datetime.now()
        for ticket in self:
            if ticket.sla_deadline:
                ticket.sla_fail = (ticket.sla_deadline < now) or ticket.sla_reached_late
            else:
                ticket.sla_fail = ticket.sla_reached_late

    @api.model
    def _search_sla_fail(self, operator, value):
        datetime_now = fields.Datetime.now()
        if (value and operator in expression.NEGATIVE_TERM_OPERATORS) or (not value and operator not in expression.NEGATIVE_TERM_OPERATORS):  # is not failed
            return ['&', ('sla_reached_late', '=', False), ('sla_deadline', '>=', datetime_now)]
        return ['|', ('sla_reached_late', '=', True), ('sla_deadline', '<', datetime_now)]  # is failed

    @api.depends('user_id')
    def _compute_is_self_assigned(self):
        for ticket in self:
            ticket.is_self_assigned = self.env.user == ticket.user_id

    @api.onchange('team_id')
    def _onchange_team_id(self):
        if self.team_id:
            if not self.user_id:
                self.user_id = self.team_id._determine_user_to_assign()[self.team_id.id]
            if not self.stage_id or self.stage_id not in self.team_id.stage_ids:
                self.stage_id = self.team_id._determine_stage()[self.team_id.id]

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.partner_name = self.partner_id.name
            self.partner_email = self.partner_id.email

    @api.depends('partner_id')
    def _compute_partner_ticket_count(self):
        data = self.env['helpdesk.ticket'].read_group([
            ('partner_id', 'in', self.mapped('partner_id').ids),
            ('stage_id.is_close', '=', False)
        ], ['partner_id'], ['partner_id'], lazy=False)
        ticket_per_partner_map = dict((item['partner_id'][0], item['__count']) for item in data)
        for ticket in self:
            ticket.partner_ticket_count = ticket_per_partner_map.get(ticket.partner_id.id, 0)

    @api.depends('assign_date')
    def _compute_assign_hours(self):
        for ticket in self:
            create_date = fields.Datetime.from_string(ticket.create_date)
            if create_date and ticket.assign_date:
                duration_data = ticket.team_id.resource_calendar_id.get_work_duration_data(create_date, fields.Datetime.from_string(ticket.assign_date), compute_leaves=True)
                ticket.assign_hours = duration_data['hours']
            else:
                ticket.assign_hours = False

    @api.depends('create_date', 'close_date')
    def _compute_close_hours(self):
        for ticket in self:
            create_date = fields.Datetime.from_string(ticket.create_date)
            if create_date and ticket.close_date:
                duration_data = ticket.team_id.resource_calendar_id.get_work_duration_data(create_date, fields.Datetime.from_string(ticket.close_date), compute_leaves=True)
                ticket.close_hours = duration_data['hours']
            else:
                ticket.close_hours = False

    @api.depends('close_hours')
    def _compute_open_hours(self):
        for ticket in self:
            if ticket.create_date:  # fix from https://github.com/odoo/enterprise/commit/928fbd1a16e9837190e9c172fa50828fae2a44f7
                if ticket.close_date:
                    time_difference = ticket.close_date - fields.Datetime.from_string(ticket.create_date)
                else:
                    time_difference = fields.Datetime.now() - fields.Datetime.from_string(ticket.create_date)
                ticket.open_hours = (time_difference.seconds) / 3600 + time_difference.days * 24
            else:
                ticket.open_hours = 0

    @api.model
    def _search_open_hours(self, operator, value):
        dt = fields.Datetime.now() - relativedelta.relativedelta(hours=value)

        d1, d2 = False, False
        if operator in ['<', '<=', '>', '>=']:
            d1 = ['&', ('close_date', '=', False), ('create_date', expression.TERM_OPERATORS_NEGATION[operator], dt)]
            d2 = ['&', ('close_date', '!=', False), ('close_hours', operator, value)]
        elif operator in ['=', '!=']:
            subdomain = ['&', ('create_date', '>=', dt.replace(minute=0, second=0, microsecond=0)), ('create_date', '<=', dt.replace(minute=59, second=59, microsecond=99))]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                subdomain = expression.distribute_not(subdomain)
            d1 = expression.AND([[('close_date', '=', False)], subdomain])
            d2 = ['&', ('close_date', '!=', False), ('close_hours', operator, value)]
        return expression.OR([d1, d2])

    # ------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------

    def name_get(self):
        result = []
        for ticket in self:
            result.append((ticket.id, "%s (#%d)" % (ticket.name, ticket._origin.id)))
        return result

    @api.model_create_multi
    def create(self, list_value):
        now = fields.Datetime.now()
        # determine user_id and stage_id if not given. Done in batch.
        teams = self.env['helpdesk.team'].browse([vals['team_id'] for vals in list_value if vals.get('team_id')])
        team_default_map = dict.fromkeys(teams.ids, dict())
        for team in teams:
            team_default_map[team.id] = {
                'stage_id': team._determine_stage()[team.id].id,
                'user_id': team._determine_user_to_assign()[team.id].id
            }

        # Manually create a partner now since 'generate_recipients' doesn't keep the name. This is
        # to avoid intrusive changes in the 'mail' module
        for vals in list_value:
            if 'partner_name' in vals and 'partner_email' in vals and 'partner_id' not in vals:
                try:
                    vals['partner_id'] = self.env['res.partner'].find_or_create(
                        tools.formataddr((vals['partner_name'], vals['partner_email']))
                    )
                except UnicodeEncodeError:
                    # 'formataddr' doesn't support non-ascii characters in email. Therefore, we fall
                    # back on a simple partner creation.
                    vals['partner_id'] = self.env['res.partner'].create({
                        'name': vals['partner_name'],
                        'email': vals['partner_email'],
                    }).id

        # determine partner email for ticket with partner but no email given
        partners = self.env['res.partner'].browse([vals['partner_id'] for vals in list_value if 'partner_id' in vals and vals.get('partner_id') and 'partner_email' not in vals])
        partner_email_map = {partner.id: partner.email for partner in partners}
        partner_name_map = {partner.id: partner.name for partner in partners}

        for vals in list_value:
            if vals.get('team_id'):
                team_default = team_default_map[vals['team_id']]
                if 'stage_id' not in vals:
                    vals['stage_id'] = team_default['stage_id']
                # Note: this will break the randomly distributed user assignment. Indeed, it will be too difficult to
                # equally assigned user when creating ticket in batch, as it requires to search after the last assigned
                # after every ticket creation, which is not very performant. We decided to not cover this user case.
                if 'user_id' not in vals:
                    vals['user_id'] = team_default['user_id']
                if vals.get('user_id'):  # if a user is finally assigned, force ticket assign_date and reset assign_hours
                    vals['assign_date'] = fields.Datetime.now()
                    vals['assign_hours'] = 0

            # set partner email if in map of not given
            if vals.get('partner_id') in partner_email_map:
                vals['partner_email'] = partner_email_map.get(vals['partner_id'])
            # set partner name if in map of not given
            if vals.get('partner_id') in partner_name_map:
                vals['partner_name'] = partner_name_map.get(vals['partner_id'])

            if vals.get('stage_id'):
                vals['date_last_stage_update'] = now

        # context: no_log, because subtype already handle this
        tickets = super(HelpdeskTicket, self).create(list_value)

        # make customer follower
        for ticket in tickets:
            if ticket.partner_id:
                ticket.message_subscribe(partner_ids=ticket.partner_id.ids)

        # apply SLA
        tickets.sudo()._sla_apply()

        return tickets

    def write(self, vals):
        # we set the assignation date (assign_date) to now for tickets that are being assigned for the first time
        # same thing for the closing date
        assigned_tickets = closed_tickets = self.browse()
        if vals.get('user_id'):
            assigned_tickets = self.filtered(lambda ticket: not ticket.assign_date)

        if vals.get('stage_id'):
            if self.env['helpdesk.stage'].browse(vals.get('stage_id')).is_close:
                closed_tickets = self.filtered(lambda ticket: not ticket.close_date)
            else:  # auto reset the 'closed_by_partner' flag
                vals['closed_by_partner'] = False

        now = fields.Datetime.now()

        # update last stage date when changing stage
        if 'stage_id' in vals:
            vals['date_last_stage_update'] = now

        res = super(HelpdeskTicket, self - assigned_tickets - closed_tickets).write(vals)
        res &= super(HelpdeskTicket, assigned_tickets - closed_tickets).write(dict(vals, **{
            'assign_date': now,
        }))
        res &= super(HelpdeskTicket, closed_tickets - assigned_tickets).write(dict(vals, **{
            'close_date': now,
        }))
        res &= super(HelpdeskTicket, assigned_tickets & closed_tickets).write(dict(vals, **{
            'assign_date': now,
            'close_date': now,
        }))

        if vals.get('partner_id'):
            self.message_subscribe([vals['partner_id']])

        # SLA business
        sla_triggers = self._sla_reset_trigger()
        if any(field_name in sla_triggers for field_name in vals.keys()):
            self.sudo()._sla_apply(keep_reached=True)
        if 'stage_id' in vals:
            self.sudo()._sla_reach(vals['stage_id'])

        return res

    # ------------------------------------------------------------
    # Actions and Business methods
    # ------------------------------------------------------------

    @api.model
    def _sla_reset_trigger(self):
        """ Get the list of field for which we have to reset the SLAs (regenerate) """
        return ['team_id', 'priority', 'ticket_type_id']

    def _sla_apply(self, keep_reached=False):
        """ Apply SLA to current tickets: erase the current SLAs, then find and link the new SLAs to each ticket.
            Note: transferring ticket to a team "not using SLA" (but with SLAs defined), SLA status of the ticket will be
            erased but nothing will be recreated.
            :returns recordset of new helpdesk.sla.status applied on current tickets
        """
        # get SLA to apply
        sla_per_tickets = self._sla_find()

        # generate values of new sla status
        sla_status_value_list = []
        for tickets, slas in sla_per_tickets.items():
            sla_status_value_list += tickets._sla_generate_status_values(slas, keep_reached=keep_reached)

        sla_status_to_remove = self.mapped('sla_status_ids')
        if keep_reached:  # keep only the reached one to avoid losing reached_date info
            sla_status_to_remove = sla_status_to_remove.filtered(lambda status: not status.reached_datetime)

        # if we are going to recreate many sla.status, then add norecompute to avoid 2 recomputation (unlink + recreate). Here,
        # `norecompute` will not trigger recomputation. It will be done on the create multi (if value list is not empty).
        if sla_status_value_list:
            sla_status_to_remove.with_context(norecompute=True)

        # unlink status and create the new ones in 2 operations (recomputation optimized)
        sla_status_to_remove.unlink()
        return self.env['helpdesk.sla.status'].create(sla_status_value_list)

    def _sla_find(self):
        """ Find the SLA to apply on the current tickets
            :returns a map with the tickets linked to the SLA to apply on them
            :rtype : dict {<helpdesk.ticket>: <helpdesk.sla>}
        """
        tickets_map = {}
        sla_domain_map = {}

        def _generate_key(ticket):
            """ Return a tuple identifying the combinaison of field determining the SLA to apply on the ticket """
            fields_list = self._sla_reset_trigger()
            key = list()
            for field_name in fields_list:
                if ticket._fields[field_name].type == 'many2one':
                    key.append(ticket[field_name].id)
                else:
                    key.append(ticket[field_name])
            return tuple(key)

        for ticket in self:
            if ticket.team_id.use_sla:  # limit to the team using SLA
                key = _generate_key(ticket)
                # group the ticket per key
                tickets_map.setdefault(key, self.env['helpdesk.ticket'])
                tickets_map[key] |= ticket
                # group the SLA to apply, by key
                if key not in sla_domain_map:
                    sla_domain_map[key] = [('team_id', '=', ticket.team_id.id), ('priority', '<=', ticket.priority), ('stage_id.sequence', '>=', ticket.stage_id.sequence), '|', ('ticket_type_id', '=', ticket.ticket_type_id.id), ('ticket_type_id', '=', False)]

        result = {}
        for key, tickets in tickets_map.items():  # only one search per ticket group
            domain = sla_domain_map[key]
            result[tickets] = self.env['helpdesk.sla'].search(domain)  # SLA to apply on ticket subset

        return result

    def _sla_generate_status_values(self, slas, keep_reached=False):
        """ Return the list of values for given SLA to be applied on current ticket """
        status_to_keep = dict.fromkeys(self.ids, list())

        # generate the map of status to keep by ticket only if requested
        if keep_reached:
            for ticket in self:
                for status in ticket.sla_status_ids:
                    if status.reached_datetime:
                        status_to_keep[ticket.id].append(status.sla_id.id)

        # create the list of value, and maybe exclude the existing ones
        result = []
        for ticket in self:
            for sla in slas:
                if not (keep_reached and sla.id in status_to_keep[ticket.id]):
                    result.append({
                        'ticket_id': ticket.id,
                        'sla_id': sla.id,
                        'reached_datetime': fields.Datetime.now() if ticket.stage_id == sla.stage_id else False  # in case of SLA on first stage
                    })

        return result

    def _sla_reach(self, stage_id):
        """ Flag the SLA status of current ticket for the given stage_id as reached, and even the unreached SLA applied
            on stage having a sequence lower than the given one.
        """
        stage = self.env['helpdesk.stage'].browse(stage_id)
        stages = self.env['helpdesk.stage'].search([('sequence', '<=', stage.sequence), ('team_ids', 'in', self.mapped('team_id').ids)])  # take previous stages
        self.env['helpdesk.sla.status'].search([
            ('ticket_id', 'in', self.ids),
            ('sla_stage_id', 'in', stages.ids),
            ('reached_datetime', '=', False)
        ]).write({'reached_datetime': fields.Datetime.now()})

    def assign_ticket_to_self(self):
        self.ensure_one()
        self.user_id = self.env.user

    def open_customer_tickets(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Customer Tickets'),
            'res_model': 'helpdesk.ticket',
            'view_mode': 'kanban,tree,form,pivot,graph',
            'context': {'search_default_is_open': True, 'search_default_partner_id': self.partner_id.id}
        }

    def action_get_attachment_tree_view(self):
        attachment_action = self.env.ref('base.action_attachment')
        action = attachment_action.read()[0]
        action['domain'] = str(['&', ('res_model', '=', self._name), ('res_id', 'in', self.ids)])
        return action

    # ------------------------------------------------------------
    # Messaging API
    # ------------------------------------------------------------

    #DVE FIXME: if partner gets created when sending the message it should be set as partner_id of the ticket.
    def _message_get_suggested_recipients(self):
        recipients = super(HelpdeskTicket, self)._message_get_suggested_recipients()
        try:
            for ticket in self:
                if ticket.partner_id and ticket.partner_id.email:
                    ticket._message_add_suggested_recipient(recipients, partner=ticket.partner_id, reason=_('Customer'))
                elif ticket.partner_email:
                    ticket._message_add_suggested_recipient(recipients, email=ticket.partner_email, reason=_('Customer Email'))
        except AccessError:  # no read access rights -> just ignore suggested recipients because this implies modifying followers
            pass
        return recipients

    def _ticket_email_split(self, msg):
        email_list = tools.email_split((msg.get('to') or '') + ',' + (msg.get('cc') or ''))
        # check left-part is not already an alias
        return [
            x for x in email_list
            if x.split('@')[0] not in self.mapped('team_id.alias_name')
        ]

    @api.model
    def message_new(self, msg, custom_values=None):
        values = dict(custom_values or {}, partner_email=msg.get('from'), partner_id=msg.get('author_id'))
        ticket = super(HelpdeskTicket, self).message_new(msg, custom_values=values)
        partner_ids = [x.id for x in self.env['mail.thread']._mail_find_partner_from_emails(self._ticket_email_split(msg), records=ticket) if x]
        customer_ids = [p.id for p in self.env['mail.thread']._mail_find_partner_from_emails(tools.email_split(values['partner_email']), records=ticket) if p]
        partner_ids += customer_ids
        if customer_ids and not values.get('partner_id'):
            ticket.partner_id = customer_ids[0]
        if partner_ids:
            ticket.message_subscribe(partner_ids)
        return ticket

    def message_update(self, msg, update_vals=None):
        partner_ids = [x.id for x in self.env['mail.thread']._mail_find_partner_from_emails(self._ticket_email_split(msg), records=self) if x]
        if partner_ids:
            self.message_subscribe(partner_ids)
        return super(HelpdeskTicket, self).message_update(msg, update_vals=update_vals)

    def _message_post_after_hook(self, message, msg_vals):
        if self.partner_email and self.partner_id and not self.partner_id.email:
            self.partner_id.email = self.partner_email

        if self.partner_email and not self.partner_id:
            # we consider that posting a message with a specified recipient (not a follower, a specific one)
            # on a document without customer means that it was created through the chatter using
            # suggested recipients. This heuristic allows to avoid ugly hacks in JS.
            new_partner = message.partner_ids.filtered(lambda partner: partner.email == self.partner_email)
            if new_partner:
                self.search([
                    ('partner_id', '=', False),
                    ('partner_email', '=', new_partner.email),
                    ('stage_id.fold', '=', False)]).write({'partner_id': new_partner.id})
        return super(HelpdeskTicket, self)._message_post_after_hook(message, msg_vals)

    def _track_template(self, changes):
        res = super(HelpdeskTicket, self)._track_template(changes)
        ticket = self[0]
        if 'stage_id' in changes and ticket.stage_id.template_id:
            res['stage_id'] = (ticket.stage_id.template_id, {
                'auto_delete_message': True,
                'subtype_id': self.env['ir.model.data'].xmlid_to_res_id('mail.mt_note'),
                'email_layout_xmlid': 'mail.mail_notification_light'
            }
        )
        return res

    def _creation_subtype(self):
        return self.env.ref('helpdesk.mt_ticket_new')

    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'stage_id' in init_values:
            return self.env.ref('helpdesk.mt_ticket_stage')
        return super(HelpdeskTicket, self)._track_subtype(init_values)

    def _notify_get_groups(self):
        """ Handle helpdesk users and managers recipients that can assign
        tickets directly from notification emails. Also give access button
        to portal and portal customers. If they are notified they should
        probably have access to the document. """
        groups = super(HelpdeskTicket, self)._notify_get_groups()

        self.ensure_one()
        for group_name, group_method, group_data in groups:
            if group_name != 'customer':
                group_data['has_button_access'] = True

        if self.user_id:
            return groups

        take_action = self._notify_get_action_link('assign')
        helpdesk_actions = [{'url': take_action, 'title': _('Assign to me')}]
        helpdesk_user_group_id = self.env.ref('helpdesk.group_helpdesk_user').id
        new_groups = [(
            'group_helpdesk_user',
            lambda pdata: pdata['type'] == 'user' and helpdesk_user_group_id in pdata['groups'],
            {'actions': helpdesk_actions}
        )]
        return new_groups + groups

    def _notify_get_reply_to(self, default=None, records=None, company=None, doc_names=None):
        """ Override to set alias of tickets to their team if any. """
        aliases = self.mapped('team_id').sudo()._notify_get_reply_to(default=default, records=None, company=company, doc_names=None)
        res = {ticket.id: aliases.get(ticket.team_id.id) for ticket in self}
        leftover = self.filtered(lambda rec: not rec.team_id)
        if leftover:
            res.update(super(HelpdeskTicket, leftover)._notify_get_reply_to(default=default, records=None, company=company, doc_names=doc_names))
        return res

    # ------------------------------------------------------------
    # Rating Mixin
    # ------------------------------------------------------------

    def rating_apply(self, rate, token=None, feedback=None, subtype=None):
        return super(HelpdeskTicket, self).rating_apply(rate, token=token, feedback=feedback, subtype="helpdesk.mt_ticket_rated")

    def _rating_get_parent_field_name(self):
        return 'team_id'
