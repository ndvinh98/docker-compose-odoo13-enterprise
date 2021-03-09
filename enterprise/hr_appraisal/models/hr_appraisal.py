# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import datetime

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import formataddr


class HrAppraisal(models.Model):
    _name = "hr.appraisal"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Employee Appraisal"
    _order = 'date_close, date_final_interview'
    _rec_name = 'employee_id'

    active = fields.Boolean(default=True)
    action_plan = fields.Text(string="Action Plan", help="If the evaluation does not meet the expectations, you can propose an action plan")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    color = fields.Integer(string='Color Index', help='This color will be used in the kanban view.')
    employee_id = fields.Many2one('hr.employee', required=True, string='Employee', index=True, domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    department_id = fields.Many2one('hr.department', related='employee_id.department_id', string='Department', store=True, readonly=True)
    date_close = fields.Date(string='Appraisal Deadline', required=True, default=lambda self: datetime.date.today().replace(day=1)+relativedelta(months=+1, days=-1))
    state = fields.Selection([
        ('new', 'To Start'),
        ('pending', 'Appraisal Sent'),
        ('done', 'Done'),
        ('cancel', "Cancelled"),
    ], string='Status', tracking=True, required=True, copy=False, default='new', index=True, group_expand='_group_expand_states')
    manager_appraisal = fields.Boolean(string='Appraisal by Manager', help="This employee will be appraised by his managers")
    manager_ids = fields.Many2many('hr.employee', 'appraisal_manager_rel', 'hr_appraisal_id', domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    manager_body_html = fields.Html(string="Manager's Appraisal Invite Body Email", default=lambda self: self.env.company.appraisal_by_manager_body_html, translate=True)
    collaborators_appraisal = fields.Boolean(string='Collaborator Appraisal', help="This employee will be appraised by his collaborators")
    collaborators_ids = fields.Many2many('hr.employee', 'appraisal_subordinates_rel', 'hr_appraisal_id', domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    collaborators_body_html = fields.Html(string="Collaborator's Appraisal Invite Body Email", default=lambda self: self.env.company.appraisal_by_collaborators_body_html, translate=True)
    colleagues_appraisal = fields.Boolean(string='Colleagues Appraisal', help="This employee will be appraised by his colleagues")
    colleagues_ids = fields.Many2many('hr.employee', 'appraisal_colleagues_rel', 'hr_appraisal_id', domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]", string="Colleagues")
    colleagues_body_html = fields.Html(string="Colleague's Appraisal Invite Body Email", default=lambda self: self.env.company.appraisal_by_colleagues_body_html, translate=True)
    employee_appraisal = fields.Boolean(help="This employee will do a self-appraisal")
    employee_body_html = fields.Html(string="Employee's Appraisal Invite Body Email", default=lambda self: self.env.company.appraisal_by_employee_body_html, translate=True)
    meeting_id = fields.Many2one('calendar.event', string='Meeting')
    date_final_interview = fields.Date(string="Final Interview", index=True, tracking=True)
    is_autorized_to_send = fields.Boolean('Autorized Employee to Start Appraisal', compute='_compute_authorization')


    def _group_expand_states(self, states, domain, order):
        return [key for key, val in self._fields['state'].selection]

    def _compute_authorization(self):
        user = self.env.user
        appraisal_user = user.has_group('hr_appraisal.group_hr_appraisal_user')
        for appraisal in self:
            appraisal.is_autorized_to_send = appraisal_user or \
                user.employee_id == appraisal.employee_id and user != appraisal.create_uid

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        self = self.sudo()  # fields are not on the employee public
        if self.employee_id:
            self.company_id = self.employee_id.company_id
            self.manager_appraisal = self.employee_id.appraisal_by_manager
            self.manager_ids = self.employee_id.appraisal_manager_ids
            self.colleagues_appraisal = self.employee_id.appraisal_by_colleagues
            self.colleagues_ids = self.employee_id.appraisal_colleagues_ids
            self.employee_appraisal = self.employee_id.appraisal_self
            self.collaborators_appraisal = self.employee_id.appraisal_by_collaborators
            self.collaborators_ids = self.employee_id.appraisal_collaborators_ids

    @api.onchange('company_id')
    def _onchange_company_id(self):
        self.manager_body_html = self.company_id.appraisal_by_manager_body_html
        self.colleagues_body_html = self.company_id.appraisal_by_colleagues_body_html
        self.employee_body_html = self.company_id.appraisal_by_employee_body_html
        self.collaborators_body_html = self.company_id.appraisal_by_collaborators_body_html

    @api.onchange('manager_appraisal', 'colleagues_appraisal', 'collaborators_appraisal')
    def _onchange_manager_appraisal(self):
        if not self.manager_appraisal:
            self.manager_ids = False
        if not self.colleagues_appraisal:
            self.colleagues_ids = False
        if not self.collaborators_appraisal:
            self.collaborators_ids = False

    def subscribe_employees(self):
        """
        Subscribes the employee and his manager to the appraisal thread.
        Also subscribes other employees designed as manager for this appraisal, and the manager of the employee's department if he's different from the employee's direct manager.
        """
        for appraisal in self:
            partner_ids = [emp.related_partner_id.id for emp in appraisal.manager_ids if emp.related_partner_id]

            if appraisal.employee_id.related_partner_id:
                partner_ids.append(appraisal.employee_id.related_partner_id.id)
            if appraisal.employee_id.parent_id.related_partner_id:
                partner_ids.append(appraisal.employee_id.parent_id.related_partner_id.id)
            if appraisal.employee_id.department_id.manager_id.related_partner_id:
                partner_ids.append(appraisal.employee_id.department_id.manager_id.related_partner_id.id)

            partner_ids = list(set(partner_ids))
            appraisal.message_subscribe(partner_ids=partner_ids)
        return True

    def schedule_final_meeting(self, interview_deadline):
        """ Creates event when user enters date manually from the form view.
            If users edit the already entered date, created meeting is updated accordingly.
            Deprecated but public method: Should be remove in next version
        """
        CalendarEvent = self.env['calendar.event']
        values = {'start': interview_deadline, 'stop': interview_deadline}
        for appraisal in self:
            if appraisal.meeting_id and appraisal.meeting_id.allday:
                appraisal.meeting_id.write(values)
                appraisal.activity_reschedule(['mail.mail_activity_data_meeting'], date_deadline=interview_deadline)
            elif appraisal.meeting_id and not appraisal.meeting_id.allday:
                date = fields.Date.from_string(interview_deadline)
                meeting_date = fields.Datetime.to_string(date)
                appraisal.meeting_id.write({'start_datetime': meeting_date, 'stop_datetime': meeting_date})
                appraisal.activity_reschedule(['mail.mail_activity_data_meeting'], date_deadline=interview_deadline)
            if not appraisal.meeting_id:
                employee_attendees = appraisal.manager_ids | appraisal.employee_id
                values['name'] = _('Appraisal Meeting For %s') % appraisal.employee_id.name
                values['allday'] = True
                values['partner_ids'] = [(4, partner.id) for partner in employee_attendees.mapped('related_partner_id')]
                user_ids = employee_attendees.mapped('user_id').ids or [self.env.uid]
                values['user_id'] = user_ids[0]
                # values['activity_ids'] = [(4, activity.id)]
                meeting = CalendarEvent.create(values)
                appraisal.activity_schedule(
                    'mail.mail_activity_data_meeting', interview_deadline,
                    note=_('<a href="#" data-oe-model="%s" data-oe-id="%s">Meeting</a> for <a href="#" data-oe-model="%s" data-oe-id="%s">%s\'s</a> appraisal') % (
                        meeting._name, meeting.id, appraisal.employee_id._name,
                        appraisal.employee_id.id, appraisal.employee_id.display_name),
                    user_id=user_ids[0],
                    calendar_event_id=meeting.id)
                appraisal.meeting_id = meeting.id
        return True

    def _prepare_user_input_receivers(self):
        """
        @return: returns a list of tuple (body in html for mail, list of employees).
        """
        appraisal_receiver = []
        if self.manager_appraisal and self.manager_ids:
            appraisal_receiver.append((self.manager_body_html, self.manager_ids))
        if self.colleagues_appraisal and self.colleagues_ids:
            appraisal_receiver.append((self.colleagues_body_html, self.colleagues_ids))
        if self.collaborators_appraisal and self.collaborators_ids:
            appraisal_receiver.append((self.collaborators_body_html, self.collaborators_ids))
        if self.employee_appraisal:
            appraisal_receiver.append((self.employee_body_html, self.employee_id))
        return appraisal_receiver

    def _send_mail(self, recipient, company_id, header_text, subject, body):
        """ Send the email reminder to specified employee (in recipient)
            :param recipient: employee identifier to send the reminder
            :param company_id: company object
            :param header_text: text for header
            :param subject: subject
            :param body: body
        """

        msg = self.env['mail.message'].sudo().new(dict(body=body))

        notif_layout = self.env.ref('mail.mail_notification_light')
        notif_values = {'model_description': header_text, 'company': company_id}
        body_html = notif_layout.render(dict(message=msg, **notif_values), engine='ir.qweb', minimal_qcontext=True)
        body_html = self.env['mail.thread']._replace_local_links(body_html)
        email = self.env.user.work_email or self.env.user.email

        if not email:
            raise ValidationError(_("You must configure your mail address."))

        mail_values = {
            'email_from': formataddr((self.env.user.name, email)),
            'email_to': formataddr((recipient.name, recipient.work_email)),
            'subject': subject
            }
        self.env['mail.mail'].create(dict(body_html=body_html, state='outgoing', **mail_values))

    def send_appraisal(self):
        for appraisal in self:
            appraisal_data = appraisal._prepare_user_input_receivers()
            for body_html, employees in appraisal_data:
                for employee in employees:
                    if not employee.work_email:
                        continue

                    subject = _('%s appraisal') % (appraisal.employee_id.name)
                    template_data = {
                        'record': employee,
                        'body': body_html if body_html != '<p><br></p>' else False,
                        'deadline': appraisal.date_close,
                    }
                    if employee != appraisal.employee_id:
                        template_data.update({'employee_name': appraisal.employee_id.display_name})
                        header_text = _('appraisal about %s') % (appraisal.employee_id.name)
                    else:
                        header_text = _('appraisal')
                    tpl = self.env.ref('hr_appraisal.mail_template_appraisal_reminder')
                    body = tpl.render(template_data, engine='ir.qweb', minimal_qcontext=True)
                    self._send_mail(employee, appraisal.company_id, header_text, subject, body)

                    if employee.user_id:
                        appraisal.activity_schedule(
                            'hr_appraisal.mail_act_appraisal_form', appraisal.date_close,
                            note=_('Fill appraisal for <a href="#" data-oe-model="%s" data-oe-id="%s">%s</a>') % (
                                appraisal.employee_id._name, appraisal.employee_id.id, appraisal.employee_id.display_name),
                            user_id=employee.user_id.id)
            appraisal.message_post(body=_("Appraisal form(s) have been sent"))
        return True

    def cancel_appraisal(self):
        """ Cancels the appraisal process, removing related calendar events,
        removes sent surveys and generated activities. """
        for appraisal in self:
            if appraisal.meeting_id:
                appraisal.meeting_id.unlink()

            appraisal.date_final_interview = False
        self.activity_unlink(['mail.mail_activity_data_meeting', 'hr_appraisal.mail_act_appraisal_form'])

    @api.model
    def create(self, vals):
        employee_id = vals.get('employee_id') or self.env.context.get('default_employee_id')
        appraisals = self.search([('employee_id', '=', employee_id), ('state', '!=', 'cancel')])
        if appraisals and not self.env.user.has_group('hr_appraisal.group_hr_appraisal_manager'):
            last_appraisal_date = max(appraisals.mapped('date_close'))
            appraisal_min_period = int(self.env['ir.config_parameter'].sudo().get_param('hr_appraisal.appraisal_min_period'))
            next_authorized_appraisal = last_appraisal_date + relativedelta(months=appraisal_min_period)
            if datetime.date.today() < next_authorized_appraisal:
                raise ValidationError(_("Your last appraisal was on %s %s. You will be able to request a new \
appraisal on %s %s. If you think it's too late, feel free to have a chat with your manager.") %
                    (last_appraisal_date.strftime("%B"), last_appraisal_date.strftime("%Y"),
                    next_authorized_appraisal.strftime("%B"), next_authorized_appraisal.strftime("%Y")))

        if vals.get('manager_ids') != [[6, 0, []]]:
            vals.update({'manager_appraisal': True})
        else:
            vals.update({'manager_appraisal': False})
        if vals.get('collaborators_ids') != [[6, 0, []]]:
            vals.update({'collaborators_appraisal': True})
        else:
            vals.update({'collaborators_appraisal': False})
        if vals.get('colleagues_ids') != [[6, 0, []]]:
            vals.update({'colleagues_appraisal': True})
        else:
            vals.update({'colleagues_appraisal': False})

        result = super(HrAppraisal, self).create(vals)
        if vals.get('state') and vals['state'] == 'pending':
            self.send_appraisal()

        result.employee_id.sudo().appraisal_date = result.date_close
        result.subscribe_employees()
        return result

    def write(self, vals):
        if vals.get('state'):
            if vals['state'] == 'cancel':
                self.cancel_appraisal()
            if vals['state'] == 'pending':
                self.send_appraisal()
        result = super(HrAppraisal, self).write(vals)
        if vals.get('date_close'):
            self.mapped('employee_id').write({'appraisal_date': vals.get('date_close'), 'last_duration_reminder_send': 0})
            self.activity_reschedule(['hr_appraisal.mail_act_appraisal_form'], date_deadline=vals['date_close'])
        return result

    def unlink(self):
        if any(appraisal.state not in ['new', 'cancel'] for appraisal in self):
            raise UserError(_("You cannot delete appraisal which is not in draft or canceled state"))
        return super(HrAppraisal, self).unlink()

    def action_calendar_event(self):
        """ Link to open calendar view for creating employee interview/meeting"""
        self.ensure_one()
        partner_ids = [manager.related_partner_id.id for manager in self.manager_ids if manager.related_partner_id]
        if self.employee_id.related_partner_id:
            partner_ids.append(self.employee_id.related_partner_id.id)
        action = self.env.ref('calendar.action_calendar_event').read()[0]
        partner_ids.append(self.env.user.partner_id.id)
        action['context'] = {
            'default_partner_ids': partner_ids,
            'search_default_mymeetings': 1
        }
        return action

    def button_send_appraisal(self):
        self.write({'state': 'pending'})

    def button_done_appraisal(self):
        self.write({'state': 'done'})
        self.activity_feedback(['mail.mail_activity_data_meeting', 'hr_appraisal.mail_act_appraisal_form'])

    def button_cancel_appraisal(self):
        self.write({'state': 'cancel'})

    def write_and_open(self):
        return {
            'view_mode': 'form',
            'res_model': 'hr.appraisal',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_id': self.id,
        }
