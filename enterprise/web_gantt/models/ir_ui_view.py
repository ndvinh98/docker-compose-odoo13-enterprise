# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class View(models.Model):
    _inherit = 'ir.ui.view'

    def _postprocess_access_rights(self, model, node):
        """ Compute and set on node access rights based on view type. Specific
        views can add additional specific rights like creating columns for
        many2one-based grouping views. """
        node = super(View, self)._postprocess_access_rights(model, node)

        Model = self.env[model]
        is_base_model = self.env.context.get('base_model_name', model) == model

        if node.tag in ('gantt'):
            for action, operation in (('create', 'create'), ('edit', 'write')):
                if (not node.get(action) and
                        not Model.check_access_rights(operation, raise_exception=False) or
                        not self._context.get(action, True) and is_base_model):
                    node.set(action, 'false')

        return node
