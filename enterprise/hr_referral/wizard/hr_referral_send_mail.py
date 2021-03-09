# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import formataddr


class HrReferralSendMail(models.TransientModel):
    _name = 'hr.referral.send.mail'
    _description = 'Referral Send Mail'

    @api.model
    def default_get(self, fields):
        result = super(HrReferralSendMail, self).default_get(fields)
        if 'job_id' not in result:
            result['job_id'] = self.env.context.get('active_id')
        return result

    job_id = fields.Many2one('hr.job', readonly=True)
    url = fields.Char("url", compute='_compute_url', readonly=True)
    email_to = fields.Char(type="char", string="Email", required=True)
    subject = fields.Char('Subject', default="Job for you")
    body_html = fields.Html('Body')

    @api.depends('job_id')
    def _compute_url(self):
        self.ensure_one()
        self.url = self.env['hr.referral.link.to.share'].create({
            'job_id': self.job_id.id,
            'channel': 'direct',
        }).url

    @api.onchange('job_id', 'url')
    def _onchange_body_html(self):
        if not self.job_id:
            self.body_html = _('Hello,<br><br>There are some amazing job offers in my company! Have a look, they  can be interesting for you<br><a href="%s">See Job Offers</a>') % (self.url)
        else:
            self.body_html = _('Hello,<br><br>There is an amazing job offer for %s in my company! It will be a fit for you<br><a href="%s">See Job Offer</a>') % (self.job_id.name, self.url)

    def send_mail_referral(self):
        if not self.env.user.has_group('hr_referral.group_hr_recruitment_referral_user'):
            raise AccessError(_("Do not have access"))

        email = self.env.user.work_email or self.env.user.email
        if not email:
            raise ValidationError(_("You must configure a mail address for your user."))

        self.env['mail.mail'].create({
            'body_html': self.body_html,
            'state': 'outgoing',
            'email_from': formataddr((self.env.user.name, email)),
            'email_to': self.email_to,
            'subject': self.subject
        }).send()

        return {'type': 'ir.actions.act_window_close'}
