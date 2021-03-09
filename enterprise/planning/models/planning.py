# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from ast import literal_eval
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
import logging
import pytz
import uuid
from math import ceil, modf

from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval
from odoo.tools import format_time
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)


def days_span(start_datetime, end_datetime):
    if not isinstance(start_datetime, datetime):
        raise ValueError
    if not isinstance(end_datetime, datetime):
        raise ValueError
    end = datetime.combine(end_datetime, datetime.min.time())
    start = datetime.combine(start_datetime, datetime.min.time())
    duration = end - start
    return duration.days + 1


class Planning(models.Model):
    _name = 'planning.slot'
    _description = 'Planning Shift'
    _order = 'start_datetime,id desc'
    _rec_name = 'name'
    _check_company_auto = True

    def _default_employee_id(self):
        return self.env.user.employee_id

    def _default_start_datetime(self):
        return fields.Datetime.to_string(datetime.combine(fields.Datetime.now(), datetime.min.time()))

    def _default_end_datetime(self):
        return fields.Datetime.to_string(datetime.combine(fields.Datetime.now(), datetime.max.time()))

    name = fields.Text('Note')
    employee_id = fields.Many2one('hr.employee', "Employee", default=_default_employee_id, group_expand='_read_group_employee_id')
    user_id = fields.Many2one('res.users', string="User", related='employee_id.user_id', store=True, readonly=True)
    company_id = fields.Many2one('res.company', string="Company", required=True, compute="_compute_planning_slot_company_id", store=True, readonly=False)
    role_id = fields.Many2one('planning.role', string="Role")
    color = fields.Integer("Color", related='role_id.color')
    was_copied = fields.Boolean("This shift was copied from previous week", default=False, readonly=True)

    start_datetime = fields.Datetime("Start Date", required=True, default=_default_start_datetime)
    end_datetime = fields.Datetime("End Date", required=True, default=_default_end_datetime)

    # UI fields and warnings
    allow_self_unassign = fields.Boolean('Let employee unassign themselves', related='company_id.planning_allow_self_unassign')
    is_assigned_to_me = fields.Boolean('Is this shift assigned to the current user', compute='_compute_is_assigned_to_me')
    overlap_slot_count = fields.Integer('Overlapping slots', compute='_compute_overlap_slot_count')

    # time allocation
    allocation_type = fields.Selection([
        ('planning', 'Planning'),
        ('forecast', 'Forecast')
    ], compute='_compute_allocation_type')
    allocated_hours = fields.Float("Allocated hours", default=0, compute='_compute_allocated_hours', store=True)
    allocated_percentage = fields.Float("Allocated Time (%)", default=100, help="Percentage of time the employee is supposed to work during the shift.")
    working_days_count = fields.Integer("Number of working days", compute='_compute_working_days_count', store=True)

    # publication and sending
    is_published = fields.Boolean("Is the shift sent", default=False, readonly=True, help="If checked, this means the planning entry has been sent to the employee. Modifying the planning entry will mark it as not sent.")
    publication_warning = fields.Boolean("Modified since last publication", default=False, readonly=True, help="If checked, it means that the shift contains has changed since its last publish.", copy=False)

    # template dummy fields (only for UI purpose)
    template_creation = fields.Boolean("Save as a Template", default=False, store=False, inverse='_inverse_template_creation')
    template_autocomplete_ids = fields.Many2many('planning.slot.template', store=False, compute='_compute_template_autocomplete_ids')
    template_id = fields.Many2one('planning.slot.template', string='Planning Templates', store=False)

    # Recurring (`repeat_` fields are none stored, only used for UI purpose)
    recurrency_id = fields.Many2one('planning.recurrency', readonly=True, index=True, ondelete="set null", copy=False)
    repeat = fields.Boolean("Repeat", compute='_compute_repeat', inverse='_inverse_repeat')
    repeat_interval = fields.Integer("Repeat every", default=1, compute='_compute_repeat', inverse='_inverse_repeat')
    repeat_type = fields.Selection([('forever', 'Forever'), ('until', 'Until')], string='Repeat Type', default='forever', compute='_compute_repeat', inverse='_inverse_repeat')
    repeat_until = fields.Date("Repeat Until", compute='_compute_repeat', inverse='_inverse_repeat', help="If set, the recurrence stop at that date. Otherwise, the recurrence is applied indefinitely.")

    _sql_constraints = [
        ('check_start_date_lower_end_date', 'CHECK(end_datetime > start_datetime)', 'Shift end date should be greater than its start date'),
        ('check_allocated_hours_positive', 'CHECK(allocated_hours >= 0)', 'You cannot have negative shift'),
    ]

    @api.depends('employee_id.company_id')
    def _compute_planning_slot_company_id(self):
        for slot in self:
            if slot.employee_id:
                slot.company_id = slot.employee_id.company_id.id
            if not slot.company_id.id:
                slot.company_id = slot.env.company

    @api.depends('user_id')
    def _compute_is_assigned_to_me(self):
        for slot in self:
            slot.is_assigned_to_me = slot.user_id == self.env.user

    @api.depends('start_datetime', 'end_datetime')
    def _compute_allocation_type(self):
        for slot in self:
            if slot.start_datetime and slot.end_datetime and (slot.end_datetime - slot.start_datetime).total_seconds() / 3600.0 < 24:
                slot.allocation_type = 'planning'
            else:
                slot.allocation_type = 'forecast'

    @api.depends('start_datetime', 'end_datetime', 'employee_id.resource_calendar_id', 'allocated_percentage')
    def _compute_allocated_hours(self):
        for slot in self:
            if slot.start_datetime and slot.end_datetime:
                percentage = slot.allocated_percentage / 100.0 or 1
                if slot.allocation_type == 'planning' and slot.start_datetime and slot.end_datetime:
                    slot.allocated_hours = (slot.end_datetime - slot.start_datetime).total_seconds() * percentage / 3600.0
                else:
                    if slot.employee_id:
                        slot.allocated_hours = slot.employee_id._get_work_days_data_batch(
                            slot.start_datetime, slot.end_datetime, compute_leaves=True
                        )[slot.employee_id.id]['hours'] * percentage
                    else:
                        slot.allocated_hours = 0.0

    @api.depends('start_datetime', 'end_datetime', 'employee_id')
    def _compute_working_days_count(self):
        for slot in self:
            if slot.employee_id:
                slot.working_days_count = ceil(slot.employee_id._get_work_days_data_batch(
                    slot.start_datetime, slot.end_datetime, compute_leaves=True
                )[slot.employee_id.id]['days'])
            else:
                slot.working_days_count = 0

    @api.depends('start_datetime', 'end_datetime', 'employee_id')
    def _compute_overlap_slot_count(self):
        if self.ids:
            self.flush(['start_datetime', 'end_datetime', 'employee_id'])
            query = """
                SELECT S1.id,count(*) FROM
                    planning_slot S1, planning_slot S2
                WHERE
                    S1.start_datetime < S2.end_datetime and S1.end_datetime > S2.start_datetime and S1.id <> S2.id and S1.employee_id = S2.employee_id
                GROUP BY S1.id;
            """
            self.env.cr.execute(query, (tuple(self.ids),))
            overlap_mapping = dict(self.env.cr.fetchall())
            for slot in self:
                slot.overlap_slot_count = overlap_mapping.get(slot.id, 0)
        else:
            self.overlap_slot_count = 0

    @api.depends('role_id')
    def _compute_template_autocomplete_ids(self):
        domain = []
        if self.role_id:
            domain = ['|', ('role_id', '=', self.role_id.id), ('role_id', '=', False)]
        self.template_autocomplete_ids = self.env['planning.slot.template'].search(domain, order='start_time', limit=10)

    @api.depends('recurrency_id')
    def _compute_repeat(self):
        for slot in self:
            if slot.recurrency_id:
                slot.repeat = True
                slot.repeat_interval = slot.recurrency_id.repeat_interval
                slot.repeat_until = slot.recurrency_id.repeat_until
                slot.repeat_type = slot.recurrency_id.repeat_type
            else:
                slot.repeat = False
                slot.repeat_interval = False
                slot.repeat_until = False
                slot.repeat_type = False

    def _inverse_repeat(self):
        for slot in self:
            if slot.repeat and not slot.recurrency_id.id:  # create the recurrence
                recurrency_values = {
                    'repeat_interval': slot.repeat_interval,
                    'repeat_until': slot.repeat_until if slot.repeat_type == 'until' else False,
                    'repeat_type': slot.repeat_type,
                    'company_id': slot.company_id.id,
                }
                recurrence = self.env['planning.recurrency'].create(recurrency_values)
                slot.recurrency_id = recurrence
                slot.recurrency_id._repeat_slot()
            # user wants to delete the recurrence
            # here we also check that we don't delete by mistake a slot of which the repeat parameters have been changed
            elif not slot.repeat and slot.recurrency_id.id and (
                slot.repeat_type == slot.recurrency_id.repeat_type and
                slot.repeat_until == slot.recurrency_id.repeat_until and
                slot.repeat_interval == slot.recurrency_id.repeat_interval
            ):
                slot.recurrency_id._delete_slot(slot.end_datetime)
                slot.recurrency_id.unlink()  # will set recurrency_id to NULL

    def _inverse_template_creation(self):
        values_list = []
        existing_values = []
        for slot in self:
            if slot.template_creation:
                values_list.append(slot._prepare_template_values())
        # Here we check if there's already a template w/ the same data
        existing_templates = self.env['planning.slot.template'].read_group([], ['role_id', 'start_time', 'duration'], ['role_id', 'start_time', 'duration'], limit=None, lazy=False)
        if len(existing_templates):
            for element in existing_templates:
                role_id = element['role_id'][0] if element.get('role_id') else False
                existing_values.append({'role_id': role_id, 'start_time': element['start_time'], 'duration': element['duration']})
        self.env['planning.slot.template'].create([x for x in values_list if x not in existing_values])

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            start = self.start_datetime or datetime.combine(fields.Datetime.now(), datetime.min.time())
            end = self.end_datetime or datetime.combine(fields.Datetime.now(), datetime.max.time())
            work_interval = self.employee_id.resource_id._get_work_interval(start, end)
            start_datetime, end_datetime = work_interval[self.employee_id.resource_id.id]
            if start_datetime:
                self.start_datetime = start_datetime.astimezone(pytz.utc).replace(tzinfo=None)
            if end_datetime:
                self.end_datetime = end_datetime.astimezone(pytz.utc).replace(tzinfo=None)
            # Set default role if the role field is empty
            if not self.role_id and self.employee_id.sudo().planning_role_id:
                self.role_id = self.employee_id.sudo().planning_role_id

    @api.onchange('start_datetime', 'end_datetime', 'employee_id')
    def _onchange_dates(self):
        if self.employee_id and self.is_published:
            self.publication_warning = True

    @api.onchange('template_creation')
    def _onchange_template_autocomplete_ids(self):
        templates = self.env['planning.slot.template'].search([], order='start_time', limit=10)
        if templates:
            if not self.template_creation:
                self.template_autocomplete_ids = templates
            else:
                self.template_autocomplete_ids = False
        else:
            self.template_autocomplete_ids = False

    @api.onchange('template_id')
    def _onchange_template_id(self):
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        if self.template_id and self.start_datetime:
            h = int(self.template_id.start_time)
            m = round(modf(self.template_id.start_time)[0] * 60.0)
            start = pytz.utc.localize(self.start_datetime).astimezone(user_tz)
            start = start.replace(hour=int(h), minute=int(m))
            self.start_datetime = start.astimezone(pytz.utc).replace(tzinfo=None)
            h = int(self.template_id.duration)
            m = round(modf(self.template_id.duration)[0] * 60.0)
            delta = timedelta(hours=int(h), minutes=int(m))
            self.end_datetime = fields.Datetime.to_string(self.start_datetime + delta)

            if self.template_id.role_id:
                self.role_id = self.template_id.role_id

    @api.onchange('repeat')
    def _onchange_default_repeat_values(self):
        """ When checking the `repeat` flag on an existing record, the values of recurring fields are `False`. This onchange
            restore the default value for usability purpose.
        """
        recurrence_fields = ['repeat_interval', 'repeat_until', 'repeat_type']
        default_values = self.default_get(recurrence_fields)
        for fname in recurrence_fields:
            self[fname] = default_values.get(fname)


    # ----------------------------------------------------
    # ORM overrides
    # ----------------------------------------------------

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        result = super(Planning, self).read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)
        prepend_open_shifts = self.env.context.get('prepend_open_shifts')
        if 'employee_id' in groupby and prepend_open_shifts:
            # Always prepend 'Undefined Employees' (will be printed 'Open Shifts' when called by the frontend)
            d = {}
            for field in fields:
                d.update({field: False})
            result.insert(0, d)
        return result

    def name_get(self):
        group_by = self.env.context.get('group_by', [])
        field_list = [fname for fname in self._name_get_fields() if fname not in group_by][:2]  # limit to 2 labels

        result = []
        for slot in self:
            # label part, depending on context `groupby`
            name = ' - '.join([self._fields[fname].convert_to_display_name(slot[fname], slot) for fname in field_list if slot[fname]])

            # date / time part
            destination_tz = pytz.timezone(self.env.user.tz or 'UTC')
            start_datetime = pytz.utc.localize(slot.start_datetime).astimezone(destination_tz).replace(tzinfo=None)
            end_datetime = pytz.utc.localize(slot.end_datetime).astimezone(destination_tz).replace(tzinfo=None)
            if slot.end_datetime - slot.start_datetime <= timedelta(hours=24):  # shift on a single day
                name = '%s - %s %s' % (
                    format_time(self.env, start_datetime.time(), time_format='short'),
                    format_time(self.env, end_datetime.time(), time_format='short'),
                    name
                )
            else:
                name = '%s - %s %s' % (
                    start_datetime.date(),
                    end_datetime.date(),
                    name
                )

            # add unicode bubble to tell there is a note
            if slot.name:
                name = u'%s \U0001F4AC' % name

            result.append([slot.id, name])
        return result

    @api.model
    def create(self, vals):
        if not vals.get('company_id') and vals.get('employee_id'):
            vals['company_id'] = self.env['hr.employee'].browse(vals.get('employee_id')).company_id.id
        if not vals.get('company_id'):
            vals['company_id'] = self.env.company.id
        return super().create(vals)

    def write(self, values):
        # detach planning entry from recurrency
        if any(fname in values.keys() for fname in self._get_fields_breaking_recurrency()) and not values.get('recurrency_id'):
            values.update({'recurrency_id': False})
        # warning on published shifts
        if 'publication_warning' not in values and (set(values.keys()) & set(self._get_fields_breaking_publication())):
            values['publication_warning'] = True
        result = super(Planning, self).write(values)
        # recurrence
        if any(key in ('repeat', 'repeat_type', 'repeat_until', 'repeat_interval') for key in values):
            # User is trying to change this record's recurrence so we delete future slots belonging to recurrence A
            # and we create recurrence B from now on w/ the new parameters
            for slot in self:
                if slot.recurrency_id and values.get('repeat') is None:
                    recurrency_values = {
                        'repeat_interval': values.get('repeat_interval') or slot.recurrency_id.repeat_interval,
                        'repeat_until': values.get('repeat_until') if values.get('repeat_type') == 'until' else False,
                        'repeat_type': values.get('repeat_type'),
                        'company_id': slot.company_id.id,
                    }
                    # Kill recurrence A
                    slot.recurrency_id.repeat_type = 'until'
                    slot.recurrency_id.repeat_until = slot.start_datetime
                    slot.recurrency_id._delete_slot(slot.end_datetime)
                    # Create recurrence B
                    recurrence = slot.env['planning.recurrency'].create(recurrency_values)
                    slot.recurrency_id = recurrence
                    slot.recurrency_id._repeat_slot()
        return result

    # ----------------------------------------------------
    # Actions
    # ----------------------------------------------------

    def action_unlink(self):
        self.unlink()
        return {'type': 'ir.actions.act_window_close'}

    def action_see_overlaping_slots(self):
        domain_map = self._get_overlap_domain()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'planning.slot',
            'name': _('Shifts in conflict'),
            'view_mode': 'gantt,list,form',
            'domain': domain_map[self.id],
            'context': {
                'initialDate': min([slot.start_datetime for slot in self.search(domain_map[self.id])])
            }
        }

    def action_self_assign(self):
        """ Allow planning user to self assign open shift. """
        self.ensure_one()
        # user must at least 'read' the shift to self assign (Prevent any user in the system (portal, ...) to assign themselves)
        if not self.check_access_rights('read', raise_exception=False):
            raise AccessError(_("You don't the right to self assign."))
        if self.employee_id:
            raise UserError(_("You can not assign yourself to an already assigned shift."))
        return self.sudo().write({'employee_id': self.env.user.employee_id.id if self.env.user.employee_id else False})

    def action_self_unassign(self):
        """ Allow planning user to self unassign from a shift, if the feature is activated """
        self.ensure_one()
        # The following condition will check the read access on planning.slot, and that user must at least 'read' the
        # shift to self unassign. Prevent any user in the system (portal, ...) to unassign any shift.
        if not self.allow_self_unassign:
            raise UserError(_("The company does not allow you to self unassign."))
        if self.employee_id != self.env.user.employee_id:
            raise UserError(_("You can not unassign another employee than yourself."))
        return self.sudo().write({'employee_id': False})

    # ----------------------------------------------------
    # Gantt view
    # ----------------------------------------------------

    @api.model
    def gantt_unavailability(self, start_date, end_date, scale, group_bys=None, rows=None):
        start_datetime = fields.Datetime.from_string(start_date)
        end_datetime = fields.Datetime.from_string(end_date)
        employee_ids = set()

        # function to "mark" top level rows concerning employees
        # the propagation of that item to subrows is taken care of in the traverse function below
        def tag_employee_rows(rows):
            for row in rows:
                group_bys = row.get('groupedBy')
                res_id = row.get('resId')
                if group_bys:
                    # if employee_id is the first grouping attribute, we mark the row
                    if group_bys[0] == 'employee_id' and res_id:
                        employee_id = res_id
                        employee_ids.add(employee_id)
                        row['employee_id'] = employee_id
                    # else we recursively traverse the rows where employee_id appears in the group_by
                    elif 'employee_id' in group_bys:
                        tag_employee_rows(row.get('rows'))

        tag_employee_rows(rows)
        employees = self.env['hr.employee'].browse(employee_ids)
        leaves_mapping = employees.mapped('resource_id')._get_unavailable_intervals(start_datetime, end_datetime)

        # function to recursively replace subrows with the ones returned by func
        def traverse(func, row):
            new_row = dict(row)
            if new_row.get('employee_id'):
                for sub_row in new_row.get('rows'):
                    sub_row['employee_id'] = new_row['employee_id']
            new_row['rows'] = [traverse(func, row) for row in new_row.get('rows')]
            return func(new_row)

        cell_dt = timedelta(hours=1) if scale in ['day', 'week'] else timedelta(hours=12)

        # for a single row, inject unavailability data
        def inject_unavailability(row):
            new_row = dict(row)

            if row.get('employee_id'):
                employee_id = self.env['hr.employee'].browse(row.get('employee_id'))
                if employee_id:
                    # remove intervals smaller than a cell, as they will cause half a cell to turn grey
                    # ie: when looking at a week, a employee start everyday at 8, so there is a unavailability
                    # like: 2019-05-22 20:00 -> 2019-05-23 08:00 which will make the first half of the 23's cell grey
                    notable_intervals = filter(lambda interval: interval[1] - interval[0] >= cell_dt, leaves_mapping[employee_id.resource_id.id])
                    new_row['unavailabilities'] = [{'start': interval[0], 'stop': interval[1]} for interval in notable_intervals]
            return new_row

        return [traverse(inject_unavailability, row) for row in rows]

    # ----------------------------------------------------
    # Period Duplication
    # ----------------------------------------------------

    @api.model
    def action_copy_previous_week(self, date_start_week):
        date_end_copy = datetime.strptime(date_start_week, DEFAULT_SERVER_DATETIME_FORMAT)
        date_start_copy = date_end_copy - relativedelta(days=7)
        domain = [
            ('start_datetime', '>=', date_start_copy),
            ('end_datetime', '<=', date_end_copy),
            ('recurrency_id', '=', False),
            ('was_copied', '=', False)
        ]
        slots_to_copy = self.search(domain)

        new_slot_values = []
        for slot in slots_to_copy:
            if not slot.was_copied:
                values = slot.copy_data()[0]
                if values.get('start_datetime'):
                    values['start_datetime'] += relativedelta(days=7)
                if values.get('end_datetime'):
                    values['end_datetime'] += relativedelta(days=7)
                values['is_published'] = False
                new_slot_values.append(values)
        slots_to_copy.write({'was_copied': True})
        return self.create(new_slot_values)

    # ----------------------------------------------------
    # Sending Shifts
    # ----------------------------------------------------

    def action_send(self):
        group_planning_user = self.env.ref('planning.group_planning_user')
        template = self.env.ref('planning.email_template_slot_single')
        # update context to build a link for view in the slot
        view_context = dict(self._context)
        view_context.update({
            'menu_id': str(self.env.ref('planning.planning_menu_root').id),
            'action_id': str(self.env.ref('planning.planning_action_open_shift').id),
            'dbname': self.env.cr.dbname,
            'render_link': self.employee_id.user_id and self.employee_id.user_id in group_planning_user.users,
            'unavailable_path': '/planning/myshifts/',
        })
        slot_template = template.with_context(view_context)

        mails_to_send = self.env['mail.mail']
        for slot in self:
            if slot.employee_id and slot.employee_id.work_email:
                mail_id = slot_template.with_context(view_context).send_mail(slot.id, notif_layout='mail.mail_notification_light')
                current_mail = self.env['mail.mail'].browse(mail_id)
                mails_to_send |= current_mail

        if mails_to_send:
            mails_to_send.send()

        self.write({
            'is_published': True,
            'publication_warning': False,
        })
        return mails_to_send

    def action_publish(self):
        self.write({
            'is_published': True,
            'publication_warning': False,
        })
        return True

    # ----------------------------------------------------
    # Business Methods
    # ----------------------------------------------------
    def _name_get_fields(self):
        """ List of fields that can be displayed in the name_get """
        return ['employee_id', 'role_id']

    def _get_fields_breaking_publication(self):
        """ Fields list triggering the `publication_warning` to True when updating shifts """
        return [
            'employee_id',
            'start_datetime',
            'end_datetime',
            'role_id',
        ]

    def _get_fields_breaking_recurrency(self):
        """Returns the list of field which when changed should break the relation of the forecast
            with it's recurrency
        """
        return [
            'employee_id',
            'role_id',
        ]

    def _get_overlap_domain(self):
        """ get overlapping domain for current shifts
            :returns dict : map with slot id as key and domain as value
        """
        domain_mapping = {}
        for slot in self:
            domain_mapping[slot.id] = [
                '&',
                    '&',
                        ('employee_id', '!=', False),
                        ('employee_id', '=', slot.employee_id.id),
                    '&',
                        ('start_datetime', '<', slot.end_datetime),
                        ('end_datetime', '>', slot.start_datetime)
            ]
        return domain_mapping

    def _prepare_template_values(self):
        """ extract values from shift to create a template """
        # compute duration w/ tzinfo otherwise DST will not be taken into account
        destination_tz = pytz.timezone(self.env.user.tz or 'UTC')
        start_datetime = pytz.utc.localize(self.start_datetime).astimezone(destination_tz)
        end_datetime = pytz.utc.localize(self.end_datetime).astimezone(destination_tz)

        # convert time delta to hours and minutes
        total_seconds = (end_datetime - start_datetime).total_seconds()
        m, s = divmod(total_seconds, 60)
        h, m = divmod(m, 60)

        return {
            'start_time': start_datetime.hour + start_datetime.minute / 60.0,
            'duration': h + (m / 60.0),
            'role_id': self.role_id.id
        }

    def _read_group_employee_id(self, employees, domain, order):
        if employees == self.env.user.employee_id or not employees:
            return employees
        all_employees = self.env['hr.employee'].search([])
        if len(all_employees) >= 20:
            return self.env['planning.slot'].search([('create_date', '>', datetime.now() - timedelta(days=30))]).mapped('employee_id')
        return all_employees


class PlanningRole(models.Model):
    _name = 'planning.role'
    _description = "Planning Role"
    _order = 'name,id desc'
    _rec_name = 'name'

    name = fields.Char('Name', required=True)
    color = fields.Integer("Color", default=0)


class PlanningPlanning(models.Model):
    _name = 'planning.planning'
    _description = 'Planning sent by email'

    @api.model
    def _default_access_token(self):
        return str(uuid.uuid4())

    start_datetime = fields.Datetime("Start Date", required=True)
    end_datetime = fields.Datetime("Stop Date", required=True)
    include_unassigned = fields.Boolean("Includes Open shifts", default=True)
    access_token = fields.Char("Security Token", default=_default_access_token, required=True, copy=False, readonly=True)
    last_sent_date = fields.Datetime("Last sent date")
    slot_ids = fields.Many2many('planning.slot', "Shifts", compute='_compute_slot_ids')
    company_id = fields.Many2one('res.company', "Company", required=True, default=lambda self: self.env.company)

    _sql_constraints = [
        ('check_start_date_lower_stop_date', 'CHECK(end_datetime > start_datetime)', 'Planning end date should be greater than its start date'),
    ]

    @api.depends('start_datetime', 'end_datetime')
    def _compute_display_name(self):
        """ This override is need to have a human readable string in the email light layout header (`message.record_name`) """
        for planning in self:
            number_days = (planning.end_datetime - planning.start_datetime).days
            planning.display_name = _('Planning of %s days') % (number_days,)

    @api.depends('start_datetime', 'end_datetime', 'include_unassigned')
    def _compute_slot_ids(self):
        domain_map = self._get_domain_slots()
        for planning in self:
            domain = domain_map[planning.id]
            if not planning.include_unassigned:
                domain = expression.AND([domain, [('employee_id', '!=', False)]])
            planning.slot_ids = self.env['planning.slot'].search(domain)

    # ----------------------------------------------------
    # Business Methods
    # ----------------------------------------------------

    def _get_domain_slots(self):
        result = {}
        for planning in self:
            domain = ['&', '&', ('start_datetime', '<=', planning.end_datetime), ('end_datetime', '>', planning.start_datetime), ('company_id', '=', planning.company_id.id)]
            result[planning.id] = domain
        return result

    def send_planning(self, message=None):
        email_from = self.env.user.email or self.env.user.company_id.email or ''
        sent_slots = self.env['planning.slot']
        for planning in self:
            # prepare planning urls, recipient employees, ...
            slots = planning.slot_ids
            slots_open = slots.filtered(lambda slot: not slot.employee_id)

            # extract planning URLs
            employees = slots.mapped('employee_id')
            employee_url_map = employees.sudo()._planning_get_url(planning)

            # send planning email template with custom domain per employee
            template = self.env.ref('planning.email_template_planning_planning', raise_if_not_found=False)
            template_context = {
                'slot_unassigned_count': len(slots_open),
                'slot_total_count': len(slots),
                'message': message,
            }
            if template:
                # /!\ For security reason, we only given the public employee to render mail template
                for employee in self.env['hr.employee.public'].browse(employees.ids):
                    if employee.work_email:
                        template_context['employee'] = employee
                        template_context['planning_url'] = employee_url_map[employee.id]
                        template.with_context(**template_context).send_mail(planning.id, email_values={'email_to': employee.work_email, 'email_from': email_from}, notif_layout='mail.mail_notification_light')
            sent_slots |= slots
        # mark as sent
        self.write({'last_sent_date': fields.Datetime.now()})
        sent_slots.write({
            'is_published': True,
            'publication_warning': False
        })
        return True
