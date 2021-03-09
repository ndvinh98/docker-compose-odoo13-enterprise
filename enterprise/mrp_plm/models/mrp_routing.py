# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class MrpRouting(models.Model):
    _inherit = 'mrp.routing'

    version = fields.Integer('Version', default=1)
    previous_routing_id = fields.Many2one('mrp.routing', 'Previous Routing')
    revision_ids = fields.Many2many('mrp.routing', compute='_compute_revision_ids')
    eco_ids = fields.One2many('mrp.eco', 'new_routing_id', 'ECOs')
    eco_count = fields.Integer('# ECOs', compute='_compute_eco_data')

    def _compute_revision_ids(self):
        for rec in self:
            previous_routings = self.env['mrp.routing']
            current = self
            while current.previous_routing_id:
                previous_routings |= current
                current = current.previous_routing_id
            rec.revision_ids = previous_routings.ids

    def _compute_eco_data(self):
        for rec in self:
            rec.eco_count = len(rec.eco_ids)

    def apply_new_version(self):
        """ Put old routing as deprecated - TODO Set to stage that is production_ready """
        self.write({'active': True})
        self.mapped('previous_routing_id').write({'active': False})
