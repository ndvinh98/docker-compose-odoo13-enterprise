# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from werkzeug import url_encode

from odoo import api, fields, models, _


class HrAppraisalReminder(models.Model):
    _name = "hr.appraisal.reminder"
    _description = "Employee Appraisal Reminder Setting"

    notify = fields.Selection([
        ('manager', 'manager'),
        ('employee', 'employee')
        ], string='Notify', required=True, default='manager')
    appraisal_reminder = fields.Integer(string="Send Reminder (in months)", default=6, required=True)
    event = fields.Selection([
        ('arrival', 'after the arrival date'),
        ('last_appraisal', 'after the last appraisal')
        ], string='After event', required=True, default='last_appraisal')
    subject = fields.Char('Subject')
    body_html = fields.Html('Body')
    company_id = fields.Many2one('res.company', required=True, ondelete='cascade', default=lambda self: self.env.company)

    _sql_constraints = [
        ('positif_number_months', 'CHECK(appraisal_reminder > 0)', "The reminder time must be bigger or equal to 1 month."),
    ]

    def name_get(self):
        result = []
        event_selection_vals = {elem[0]: elem[1] for elem in self._fields['event']._description_selection(self.env)}
        notify_selection_vals = {elem[0]: elem[1] for elem in self._fields['notify']._description_selection(self.env)}
        for reminder in self:
            notify_name = notify_selection_vals[reminder.notify]
            event_name = event_selection_vals[reminder.event]
            result.append((reminder.id, _('%s: %s months %s') % (notify_name, reminder.appraisal_reminder, event_name)))
        return result

    @api.onchange('notify')
    def on_change_notify(self):
        if self.notify == 'manager':
            self.subject = _("${(object.name)} appraisal reminder")
            self.body_html = _("It has been a while since the last appraisal of one of your employee, go to his employee profile to request an appraisal.")
        else:
            self.subject = _("${(object.name)}'s appraisal reminder")
            self.body_html = _("It has been a while since your last appraisal, go to your employee profile to request an appraisal to your manager.")

    def _send_reminder_mail(self, reminder, recipient, employee):
        """ Prepare and send the email reminder to specified employee (in recipient)
            :param template : reminder mail template
            :param recipient : employee identifier to send the reminder
            :param employee : if the recipient is a manager, give informations about employee
        """

        if not recipient.work_email:
            return

        template_data = {
            'record': recipient,
            'subject': self.env['mail.template']._render_template(reminder.subject, 'hr.employee', employee.id, post_process=True),
            'body': reminder.body_html if reminder.body_html != '<p><br></p>' else False,
        }

        if reminder.notify == 'manager':
            url = url_encode({'action': 'hr.open_view_employee_list', 'id': employee.id, 'active_model': 'hr.employee'})
            template_data.update({
                'button_name': 'Employee profile',
                'employee_name': employee.display_name,
            })
            header_text = _('appraisal about %s') % (employee.name)
        else:
            url = url_encode({'action': 'hr.res_users_action_my', 'id': employee.user_id.id, 'active_model': 'res.users'})
            template_data.update({
                'button_name': 'Your profile',
            })
            header_text = _('appraisal')

        if reminder.event == 'arrival':
            template_data.update({'employee_creation': employee.create_date})
        else:
            template_data.update({'last_appraisal': employee.appraisal_date})

        action_url = '%s/web#%s' % (self.env['ir.config_parameter'].sudo().get_param('web.base.url'), url)
        template_data.update({'link': action_url})

        tpl = self.env.ref('hr_appraisal.mail_template_appraisal_reminder')
        body = tpl.render(template_data, engine='ir.qweb', minimal_qcontext=True)

        self.env['hr.appraisal']._send_mail(recipient, reminder.company_id, header_text, template_data['subject'], body)

    def _run_employee_appraisal_reminder(self):
        company_id = self.env['res.company'].search([('appraisal_send_reminder', '=', True)])
        # only select compnay who want send reminder
        reminders = self.search([('company_id', 'in', company_id.ids)], order='appraisal_reminder')

        for duration_month in set(reminders.mapped('appraisal_reminder')):
            employee_to_write = []
            for reminder in reminders.filtered(lambda r: r.appraisal_reminder == duration_month):
                employees = self.env['hr.employee']._get_employees_to_send_reminder_appraisal(duration_month, reminder)
                for employee in employees:
                    if reminder.notify == 'manager':
                        for manager in employee.appraisal_manager_ids:
                            self._send_reminder_mail(reminder, manager, employee)
                    else:
                        self._send_reminder_mail(reminder, employee, employee)
                employee_to_write.extend(employees.ids)
            if employee_to_write:
                self.env['hr.employee'].browse(employee_to_write).write({'last_duration_reminder_send': duration_month})
