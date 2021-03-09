# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api


class StudioMixin(models.AbstractModel):
    """ Mixin that overrides the create and write methods to properly generate
        ir.model.data entries flagged with Studio for the corresponding resources.
        Doesn't create an ir.model.data if the record is part of a module being
        currently installed as the ir.model.data will be created automatically
        afterwards.
    """
    _name = 'studio.mixin'
    _description = 'Studio Mixin'

    @api.model
    def create(self, vals):
        res = super(StudioMixin, self).create(vals)

        if self._context.get('studio') and not self._context.get('install_mode'):
            res._compute_display_name()
            res.create_studio_model_data(res.display_name)

        return res

    def write(self, vals):
        res = super(StudioMixin, self).write(vals)

        if self._context.get('studio') and not self._context.get('install_mode'):
            for record in self:
                record.create_studio_model_data(record.display_name)

        return res
