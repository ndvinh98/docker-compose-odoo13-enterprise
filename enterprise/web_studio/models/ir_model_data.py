# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class IrModelData(models.Model):
    _inherit = 'ir.model.data'

    studio = fields.Boolean(help='Checked if it has been edited with Studio.')

    @api.model
    def create(self, vals):
        if self._context.get('studio'):
            vals['studio'] = True
        return super(IrModelData, self).create(vals)

    def write(self, vals):
        """ When editing an ir.model.data with Studio, we put it in noupdate to
                avoid the customizations to be dropped when upgrading the module.
        """
        if self._context.get('studio'):
            vals['noupdate'] = True
            vals['studio'] = True
        return super(IrModelData, self).write(vals)

    def _build_update_xmlids_query(self, sub_rows, update):
        '''Override of the base method to include the `studio` attribute for studio module imports.'''
        if self._context.get('studio'):
            rowf = "(%s, %s, %s, %s, %s, now() at time zone 'UTC', now() at time zone 'UTC', 't')"
            return """
                INSERT INTO ir_model_data (module, name, model, res_id, noupdate, date_init, date_update, studio)
                VALUES {rows}
                ON CONFLICT (module, name)
                DO UPDATE SET date_update=(now() at time zone 'UTC'), noupdate='t' {where}
            """.format(
                rows=", ".join([rowf] * len(sub_rows)),
                where="WHERE NOT ir_model_data.noupdate" if update else "",
            )
        else:
            return super(IrModelData, self)._build_update_xmlids_query(sub_rows, update)
