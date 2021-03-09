# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import unicodedata
import uuid
import re

from odoo import api, fields, models
from odoo.tools import ustr


def sanitize_for_xmlid(s):
    """ Transforms a string to a name suitable for use in an xmlid.
        Strips leading and trailing spaces, converts unicode chars to ascii,
        lowers all chars, replaces spaces with underscores and truncates the
        resulting string to 20 characters.
        :param s: str
        :rtype: str
    """
    s = ustr(s)
    uni = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')

    slug_str = re.sub('[\W]', ' ', uni).strip().lower()
    slug_str = re.sub('[-\s]+', '_', slug_str)
    return slug_str[:20]


class Base(models.AbstractModel):
    _inherit = 'base'

    def create_studio_model_data(self, name):
        """ We want to keep track of created records with studio
            (ex: model, field, view, action, menu, etc.).
            An ir.model.data is created whenever a record of one of these models
            is created, tagged with studio.
        """
        IrModelData = self.env['ir.model.data']

        # Check if there is already an ir.model.data for the given resource
        data = IrModelData.search([
            ('model', '=', self._name), ('res_id', '=', self.id)
        ])
        if data:
            data.write({})  # force a write to set the 'studio' and 'noupdate' flags to True
        else:
            module = self.env['ir.module.module'].get_studio_module()
            IrModelData.create({
                'name': '%s_%s' % (sanitize_for_xmlid(name), uuid.uuid4()),
                'model': self._name,
                'res_id': self.id,
                'module': module.name,
            })


class IrModel(models.Model):
    _name = 'ir.model'
    _inherit = ['studio.mixin', 'ir.model']

    abstract = fields.Boolean(compute='_compute_abstract',
                              store=False,
                              help="Wheter this model is abstract",
                              search='_search_abstract')

    def _compute_abstract(self):
        for record in self:
            record.abstract = self.env[record.model]._abstract

    def _search_abstract(self, operator, value):
        abstract_models = [
            model._name
            for model in self.env.values()
            if model._abstract
        ]
        dom_operator = 'in' if (operator, value) in [('=', True), ('!=', False)] else 'not in'

        return [('model', dom_operator, abstract_models)]

    @api.model
    def studio_name_create(self, name):
        model_name = 'x_' + sanitize_for_xmlid(name)
        return self.create({
            'name': name,
            'model': model_name,
        })

    @api.model
    def create(self, vals):
        res = super(IrModel, self).create(vals)

        # Create a simplified form view and access rights for the created model
        # if we are in studio, but not if we are currently installing the module
        # (i.e. importing it from Studio), because those data are already
        # defined in the module (as Studio generates them automatically)
        if self._context.get('studio') and not self._context.get('install_mode'):
            # Create a simplified form view to prevent getting the default one containing all model's fields
            self.env['ir.ui.view'].create_simplified_form_view(res.model)

            # Give read access to the created model to Employees by default and all access to System
            # Note: a better solution may be to create groups at the app creation but the model is created
            # before the app and for other models we need to have info about the app.
            self.env['ir.model.access'].create({
                'name': vals.get('name', '') + ' group_system',
                'model_id': res.id,
                'group_id': self.env.ref('base.group_system').id,
                'perm_read': True,
                'perm_write': True,
                'perm_create': True,
                'perm_unlink': True,
            })
            self.env['ir.model.access'].create({
                'name': vals.get('name', '') + ' group_user',
                'model_id': res.id,
                'group_id': self.env.ref('base.group_user').id,
                'perm_read': True,
                'perm_write': False,
                'perm_create': False,
                'perm_unlink': False,
            })
        return res


class IrModelField(models.Model):
    _name = 'ir.model.fields'
    _inherit = ['studio.mixin', 'ir.model.fields']

    def name_get(self):
        if self.env.context.get('studio'):
            return [(field.id, "%s (%s)" % (field.field_description, field.model_id.name)) for field in self]
        return super(IrModelField, self).name_get()


    @api.model
    def _get_next_relation(self, model_name, comodel_name):
        """Prevent using the same m2m relation table when adding the same field.

        If the same m2m field was already added on the model, the user is in fact
        trying to add another relation - not the same one. We need to create another
        relation table.
        """
        result = super()._custom_many2many_names(model_name, comodel_name)[0]
        # check if there's already a m2m field from model_name to comodel_name;
        # if yes, check the relation table and add a sequence to it - we want to
        # be able to mirror these fields on the other side in the same order
        base = result
        attempt = 0
        existing_m2m = self.search([
            ('model', '=', model_name),
            ('relation', '=', comodel_name),
            ('relation_table', '=', result)
        ])
        while existing_m2m:
            attempt += 1
            result = '%s_%s' % (base, attempt)
            existing_m2m = self.search([
                ('model', '=', model_name),
                ('relation', '=', comodel_name),
                ('relation_table', '=', result)
            ])
        return result


class IrModelAccess(models.Model):
    _name = 'ir.model.access'
    _inherit = ['studio.mixin', 'ir.model.access']
