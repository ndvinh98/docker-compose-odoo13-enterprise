# -*- coding: utf-8 -*-
from odoo.http import request
from odoo import api, fields, models, SUPERUSER_ID
from hashlib import md5


class Lead(models.Model):
    _inherit = 'crm.lead'

    @api.depends('score_ids', 'score_ids.value')
    def _compute_score(self):
        self._cr.execute("""
             SELECT
                lead_id, COALESCE(sum(s.value), 0) as sum
             FROM
                crm_lead_score_rel rel
             LEFT JOIN
                website_crm_score s ON (s.id = rel.score_id)
             WHERE lead_id = any(%s)
             GROUP BY lead_id
             """, (self.ids,))
        scores = dict(self._cr.fetchall())
        for lead in self:
            lead.score = scores.get(lead.id, 0)

    score = fields.Float(compute='_compute_score', store=True, group_operator="avg")
    score_ids = fields.Many2many('website.crm.score', 'crm_lead_score_rel', 'lead_id', 'score_id', string='Scoring Rules')
    assign_date = fields.Datetime(string='Auto Assign Date', help="Date when the lead has been assigned via the auto-assignation mechanism")

    def _get_key(self):
        return self.env['ir.config_parameter'].sudo().get_param('database.secret')

    def get_score_domain_cookies(self):
        return request.httprequest.host

    def _merge_scores(self, opportunities):
        # We needs to delete score from opportunity_id, to be sure that all rules will be re-evaluated.
        self.sudo().write({'score_ids': [(6, 0, [])]})
        if not self.env.context.get('assign_leads_to_salesteams'):
            self.env['website.crm.score'].assign_scores_to_leads(lead_ids=self.ids)

    def merge_dependences(self, opportunities):
        self._merge_scores(opportunities)

        # Call default merge function
        return super(Lead, self).merge_dependences(opportunities)

    @api.model
    def _onchange_user_values(self, user_id):
        """ returns new values when user_id has changed """
        if user_id and self._context.get('team_id'):
            team = self.env['crm.team'].browse(self._context['team_id'])
            if user_id in team.team_user_ids.mapped('user_id').ids:
                return {}
        return super(Lead, self)._onchange_user_values(user_id)

    # Overwritte ORM to add or remove the assign date
    @api.model
    def create(self, vals):
        if vals.get('user_id'):
            vals['assign_date'] = vals.get('user_id') and fields.datetime.now() or False
        return super(Lead, self).create(vals)

    def write(self, vals):
        if 'user_id' in vals:
            vals['assign_date'] = vals.get('user_id') and fields.datetime.now() or False
        return super(Lead, self).write(vals)
