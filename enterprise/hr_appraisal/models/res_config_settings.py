# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    appraisal_min_period = fields.Integer(string="Minimum Time between Appraisals", default=6, config_parameter='hr_appraisal.appraisal_min_period')
    appraisal_max_period = fields.Integer(string="Maximum Time between Appraisals", default=18, config_parameter='hr_appraisal.appraisal_max_period')
    appraisal_send_reminder = fields.Boolean(string="Send Automatic Appraisals Reminder", related='company_id.appraisal_send_reminder', readonly=False)

    appraisal_by_manager = fields.Boolean(string="Managers", related='company_id.appraisal_by_manager', readonly=False)
    appraisal_by_employee = fields.Boolean(string="Employee", related='company_id.appraisal_by_employee', readonly=False)
    appraisal_by_collaborators = fields.Boolean(string="Collaborators", related='company_id.appraisal_by_collaborators', readonly=False)
    appraisal_by_colleagues = fields.Boolean(string="Colleagues", related='company_id.appraisal_by_colleagues', readonly=False)
    appraisal_by_manager_body_html = fields.Html(related='company_id.appraisal_by_manager_body_html', readonly=False)
    appraisal_by_employee_body_html = fields.Html(related='company_id.appraisal_by_employee_body_html', readonly=False)
    appraisal_by_collaborators_body_html = fields.Html(related='company_id.appraisal_by_collaborators_body_html', readonly=False)
    appraisal_by_colleagues_body_html = fields.Html(related='company_id.appraisal_by_colleagues_body_html', readonly=False)
