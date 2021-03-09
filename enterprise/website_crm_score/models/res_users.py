# -*- coding: utf-8 -*-

from odoo import api, fields, models


class Users(models.Model):
    _name = 'res.users'
    _inherit = ['res.users']

    def init(self):
        # Migration script to automatically create `team.user` records
        # according to the teams and salesmen configuration in the regular crm.
        # This is necessary:
        #  - So the user doesn't have to reconfigure his team when installing
        #    this module after having configured his teams in the regular crm
        #  - As the below computed field `sale_team_id` isn't recomputed on
        #    installation as the column is already in the `res_users` table
        res = self._cr.execute("""
            INSERT INTO team_user(user_id, team_id, active)
            SELECT id, sale_team_id, 't'
            FROM res_users u
            WHERE
                sale_team_id IS NOT NULL AND
                NOT exists(SELECT 1 FROM team_user WHERE user_id = u.id and team_id = u.sale_team_id)
            """)

    team_user_ids = fields.One2many(
        'team.user', 'user_id',
        string="Sales Records")
    # redefinition of the field defined in sales_team. The field is now computed
    # based on the new modeling introduced in this module. It is stored to avoid
    # breaking the member_ids inverse field. As the relationship between users
    # and sales team is a one2many / many2one relationship we take the first of
    # the team.user record to find the user's sales team.
    sale_team_id = fields.Many2one(
        'crm.team', 'User Sales Team',
        related='team_user_ids.team_id', readonly=False,
        store=True)
