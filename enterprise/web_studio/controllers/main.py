# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json

from ast import literal_eval
from copy import deepcopy
from lxml import etree

import odoo
from odoo import http, _
from odoo.http import content_disposition, request
from odoo.exceptions import UserError, AccessError, ValidationError
from odoo.addons.web_studio.controllers import export
from odoo.tools import ustr, sql


class WebStudioController(http.Controller):

    @http.route('/web_studio/chatter_allowed', type='json', auth='user')
    def is_chatter_allowed(self, model):
        """ Returns True iff a chatter can be activated on the model's form views, i.e. if
            - it is a custom model (since we can make it inherit from mail.thread), or
            - it already inherits from mail.thread.
        """
        Model = request.env[model]
        return Model._custom or isinstance(Model, type(request.env['mail.thread']))

    @http.route('/web_studio/activity_allowed', type='json', auth='user')
    def is_activity_allowed(self, model):
        """ Returns True iff an activity view can be activated on the model's action, i.e. if
            - it is a custom model (since we can make it inherit from mail.thread), or
            - it already inherits from mail.thread.
        """
        Model = request.env[model]
        return Model._custom or isinstance(Model, type(request.env['mail.activity.mixin']))

    @http.route('/web_studio/get_studio_action', type='json', auth='user')
    def get_studio_action(self, action_name, model, view_id=None, view_type=None):
        view_type = 'tree' if view_type == 'list' else view_type  # list is stored as tree in db
        model = request.env['ir.model'].search([('model', '=', model)], limit=1)

        action = None
        if hasattr(self, '_get_studio_action_' + action_name):
            action = getattr(self, '_get_studio_action_' + action_name)(model, view_id=view_id, view_type=view_type)

        return action

    def _get_studio_action_acl(self, model, **kwargs):
        return {
            'name': _('Access Control Lists'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.model.access',
            'views': [[False, 'list'], [False, 'form']],
            'target': 'current',
            'domain': [],
            'context': {
                'default_model_id': model.id,
                'search_default_model_id': model.id,
            },
            'help': _("""<p class="o_view_nocontent_smiling_face">
                Add a new access control list
            </p>
            """),
        }

    def _get_studio_action_automations(self, model, **kwargs):
        return {
            'name': _('Automated Actions'),
            'type': 'ir.actions.act_window',
            'res_model': 'base.automation',
            'views': [[False, 'list'], [False, 'form']],
            'target': 'current',
            'domain': [],
            'context': {
                'default_model_id': model.id,
                'search_default_model_id': model.id,
            },
            'help': _(""" <p class="o_view_nocontent_smiling_face">
                Add a new automated action
            </p>
            """),
        }

    def _get_studio_action_filters(self, model, **kwargs):
        return {
            'name': _('Filter Rules'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.filters',
            'views': [[False, 'list'], [False, 'form']],
            'target': 'current',
            'domain': [],
            'context': {  # model_id is a Selection on ir.filters
                'default_model_id': model.model,
                'search_default_model_id': model.model,
            },
            'help': _(""" <p class="o_view_nocontent_smiling_face">
                Add a new filter
            </p>
            """),
        }

    def _get_studio_action_reports(self, model, **kwargs):
        return {
            'name': _('Reports'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.actions.report',
            'views': [[False, 'kanban'], [False, 'form']],
            'target': 'current',
            # One can edit only reports backed by persisting models
            'domain': [
                '&',
                ("model_id.transient", "=", False),
                ("model_id.abstract", "=", False),
                ("report_type", "not in", ['qweb-text'])
            ],
            'context': {
                'default_model': model.model,
                'search_default_model': model.model,
            },
            'help': _(""" <p class="o_view_nocontent_empty_report">
                Add a new report
            </p>
            """),
        }

    def _get_studio_action_translations(self, model, **kwargs):
        """ Open a view for translating the field(s) of the record (model, id). """
        domain = ['|', ('name', '=', model.model), ('name', 'ilike', model.model + ',')]

        # search view + its inheritancies
        views = request.env['ir.ui.view'].search([('model', '=', model.model)])
        domain = ['|', '&', ('name', '=', 'ir.ui.view,arch_db'), ('res_id', 'in', views.ids)] + domain

        def make_domain(fld, rec):
            name = "%s,%s" % (fld.model_name, fld.name)
            return ['&', ('res_id', '=', rec.id), ('name', '=', name)]

        def insert_missing(fld, rec):
            if not fld.translate:
                return []

            if fld.related:
                try:
                    # traverse related fields up to their data source
                    while fld.related:
                        rec, fld = fld.traverse_related(rec)
                    if rec:
                        return ['|'] + domain + make_domain(fld, rec)
                except AccessError:
                    return []

            assert fld.translate and rec._name == fld.model_name
            request.env['ir.translation'].insert_missing(fld, rec)
            return []

        # insert missing translations of views
        for view in views:
            for name, fld in view._fields.items():
                domain += insert_missing(fld, view)

        # insert missing translations of model, and extend domain for related fields
        record = request.env[model.model].search([], limit=1)
        if record:
            for name, fld in record._fields.items():
                domain += insert_missing(fld, record)

        action = {
            'name': _('Translate view'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.translation',
            'view_mode': 'tree',
            'views': [[request.env.ref('base.view_translation_dialog_tree').id, 'list']],
            'target': 'current',
            'domain': domain,
        }

        return action

    @http.route('/web_studio/create_new_menu', type='json', auth='user')
    def create_new_menu(self, app_name=False, menu_name=False, model_id=False, is_app=False, parent_id=None, icon=None):
        """ Create a new menu @menu_name, linked to a new action associated to the model_id
            @param model_id: if not set, the action associated to this menu is the home menu
                except if @is_app is True that will create a new model
            @param is_app: if True, create an extra menu (app, without parent)
            @param parent_id: the parent of the new menu.
                To be set if is_app is False.
            @param icon: the icon of the new app.
                It can either be:
                 - the ir.attachment id of the uploaded image
                 - if the icon has been created, an array containing: [icon_class, color, background_color]
                To be set if is_app is True.
        """
        model = None
        if model_id:
            model = request.env['ir.model'].browse(model_id)
        elif is_app:
            # create a new model
            model = request.env['ir.model'].studio_name_create(menu_name)

        # create the action
        if model:
            action = request.env['ir.actions.act_window'].create({
                'name': menu_name,
                'res_model': model.model,
                'help': """
                    <p class="o_view_nocontent_smiling_face">
                        This is your new action ; by default, it contains a list view and a form view.
                    </p>
                    <p>
                        You can start customizing these screens by clicking on the Studio icon on the
                        top right corner (you can also customize this help message there).
                    </p>
                """,
            })
            action_ref = 'ir.actions.act_window,' + str(action.id)
        else:
            action = request.env.ref('base.action_open_website')
            action_ref = 'ir.actions.act_url,' + str(action.id)

        if is_app:
            # create the menus (app menu + first submenu)
            menu_values = {
                'name': app_name,
                'child_id': [(0, 0, {
                    'name': menu_name,
                    'action': action_ref,
                })]
            }

            menu_values.update(self._get_icon_fields(icon))

            new_context = dict(request.context)
            new_context.update({'ir.ui.menu.full_list': True})  # allows to create a menu without action
            new_menu = request.env['ir.ui.menu'].with_context(new_context).create(menu_values)

        else:
            # create the submenu
            new_menu = request.env['ir.ui.menu'].create({
                'name': menu_name,
                'action': action_ref,
                'parent_id': parent_id,
            })

        return {
            'menu_id': new_menu.id,
            'action_id': action.id,
        }

    @http.route('/web_studio/edit_menu_icon', type='json', auth='user')
    def edit_menu_icon(self, menu_id, icon):
        values = self._get_icon_fields(icon)
        request.env['ir.ui.menu'].browse(menu_id).write(values)

    def _get_icon_fields(self, icon):
        """ Get icon related fields (depending on the @icon received). """
        if isinstance(icon, int):
            icon_id = request.env['ir.attachment'].browse(icon)
            if not icon_id:
                raise UserError(_('The icon is not linked to an attachment'))
            return {'web_icon_data': icon_id.datas}
        elif isinstance(icon, list) and len(icon) == 3:
            return {'web_icon': ','.join(icon)}
        else:
            raise UserError(_('The icon has not a correct format'))

    @http.route('/web_studio/set_background_image', type='json', auth='user')
    def set_background_image(self, attachment_id):
        attachment = request.env['ir.attachment'].browse(attachment_id)
        if attachment:
            request.env.company.background_image = attachment.datas

    @http.route('/web_studio/reset_background_image', type='json', auth='user')
    def reset_background_image(self):
        request.env.user.with_user(request.uid).company_id.background_image = None

    def create_new_field(self, values):
        """ Create a new field with given values.
            In some cases we have to convert "id" to "name" or "name" to "id"
            - "model" is the current model we are working on. In js, we only have his name.
              but we need his id to create the field of this model.
            - The relational widget doesn't provide any name, we only have the id of the record.
              This is why we need to search the name depending of the given id.
        """
        # Get current model
        model_name = values.pop('model_name')
        Model = request.env[model_name]
        # If the model is backed by a sql view
        # it doesn't make sense to add field, and won't work
        table_kind = sql.table_kind(request.env.cr, Model._table)
        if not table_kind or table_kind == 'v':
            raise UserError(_('The model %s doesn\'t support adding fields.') % Model._name)

        model = request.env['ir.model'].search([('model', '=', model_name)])

        values['model_id'] = model.id

        # Field type is called ttype in the database
        if values.get('type'):
            values['ttype'] = values.pop('type')

        # For many2one and many2many fields
        if values.get('relation_id'):
            values['relation'] = request.env['ir.model'].browse(values.pop('relation_id')).model
        # For related one2many fields
        if values.get('related') and values.get('ttype') == 'one2many':
            field_name = values.get('related').split('.')[-1]
            field = request.env['ir.model.fields'].search([
                ('name', '=', field_name),
                ('model', '=', values.pop('relational_model')),
            ])
            field.ensure_one()
            values.update(
                relation=field.relation,
                relation_field=field.relation_field,
            )
        # For one2many fields
        if values.get('relation_field_id'):
            field = request.env['ir.model.fields'].browse(values.pop('relation_field_id'))
            values.update(
                relation=field.model_id.model,
                relation_field=field.name,
            )
        # For selection fields
        if values.get('selection'):
            values['selection'] = ustr(values['selection'])

        if values.get('ttype') == 'many2many':
            # check for existing relation to avoid re-use
            values['relation_table'] = request.env['ir.model.fields']._get_next_relation(model_name, values.get('relation'))
        # Optional default value at creation
        default_value = values.pop('default_value', False)

        # Filter out invalid field names and create new field
        values = {
            k: v
            for k, v in values.items()
            if k in request.env['ir.model.fields']._fields
        }
        new_field = request.env['ir.model.fields'].create(values)

        if default_value:
            if new_field.ttype == 'selection':
                if default_value is True:
                    # take the first selection value as default one in this case
                    default_value = new_field.selection_ids[:1].value
            self.set_default_value(new_field.model, new_field.name, default_value)

        return new_field

    @http.route('/web_studio/add_view_type', type='json', auth='user')
    def add_view_type(self, action_type, action_id, res_model, view_type, args):
        view_type = 'tree' if view_type == 'list' else view_type  # list is stored as tree in db

        if view_type == 'activity':
            model = request.env['ir.model'].search([('model', '=', res_model)])
            if model.state == 'manual' and not model.is_mail_activity:
                # Activate mail.activity.mixin inheritance on the custom model
                model.write({'is_mail_activity': True})

        try:
            request.env[res_model].fields_view_get(view_type=view_type)
        except UserError:
            return False
        self.edit_action(action_type, action_id, args)
        return True

    @http.route('/web_studio/edit_action', type='json', auth='user')
    def edit_action(self, action_type, action_id, args):

        action_id = request.env[action_type].browse(action_id)
        if action_id:
            if 'groups_id' in args:
                args['groups_id'] = [(6, 0, args['groups_id'])]

            if 'view_mode' in args:
                args['view_mode'] = args['view_mode'].replace('list', 'tree')  # list is stored as tree in db

                # As view_id and view_ids have precedence on view_mode, we need to correctly set them
                if action_id.view_id or action_id.view_ids:
                    view_modes = args['view_mode'].split(',')

                    # add new view_mode
                    missing_view_modes = [x for x in view_modes if x not in [y.view_mode for y in action_id.view_ids]]
                    for view_mode in missing_view_modes:
                        vals = {
                            'act_window_id': action_id.id,
                            'view_mode': view_mode,
                        }
                        if action_id.view_id and action_id.view_id.type == view_mode:
                            # reuse the same view_id in the corresponding view_ids record
                            vals['view_id'] = action_id.view_id.id

                        request.env['ir.actions.act_window.view'].create(vals)

                    for view_id in action_id.view_ids:
                        if view_id.view_mode in view_modes:
                            # resequence according to new view_modes
                            view_id.sequence = view_modes.index(view_id.view_mode)
                        else:
                            # remove old view_mode
                            view_id.unlink()

            action_id.write(args)

        return True

    def _get_studio_view(self, view):
        domain = [('inherit_id', '=', view.id), ('name', '=', self._generate_studio_view_name(view))]
        return view.search(domain, order='priority desc, name desc, id desc', limit=1)

    def _set_studio_view(self, view, arch):
        studio_view = self._get_studio_view(view)
        if studio_view and len(arch):
            studio_view.arch_db = arch
        elif studio_view:
            studio_view.unlink()
        elif len(arch):
            self._create_studio_view(view, arch)

    def _generate_studio_view_name(self, view):
        return "Odoo Studio: %s customization" % (view.name)

    @http.route('/web_studio/get_studio_view_arch', type='json', auth='user')
    def get_studio_view_arch(self, model, view_type, view_id=False):
        view_type = 'tree' if view_type == 'list' else view_type  # list is stored as tree in db

        if not view_id:
            # TOFIX: it's possibly not the used view ; see fields_get_view
            # try to find the lowest priority matching ir.ui.view
            view_id = request.env['ir.ui.view'].default_view(request.env[model]._name, view_type)
        # We have to create a view with the default view if we want to customize it.
        view = self._get_or_create_default_view(model, view_type, view_id)
        studio_view = self._get_studio_view(view)

        return {
            'studio_view_id': studio_view and studio_view.id or False,
            'studio_view_arch': studio_view and studio_view.arch_db or "<data/>",
        }

    def _return_view(self, view, studio_view):
        ViewModel = request.env[view.model]
        fields_view = ViewModel.with_context(studio=True).fields_view_get(view.id, view.type)
        view_type = 'list' if view.type == 'tree' else view.type

        return {
            'fields_views': {view_type: fields_view},
            'fields': ViewModel.fields_get(),
            'studio_view_id': studio_view.id,
        }

    @http.route('/web_studio/restore_default_view', type='json', auth='user')
    def restore_default_view(self, view_id):
        view = request.env['ir.ui.view'].browse(view_id)
        self._set_studio_view(view, "")

        studio_view = self._get_studio_view(view)

        return self._return_view(view, studio_view)

    @http.route('/web_studio/edit_view', type='json', auth='user')
    def edit_view(self, view_id, studio_view_arch, operations=None):
        IrModelFields = request.env['ir.model.fields']
        view = request.env['ir.ui.view'].browse(view_id)

        parser = etree.XMLParser(remove_blank_text=True)
        if studio_view_arch == "":
            studio_view_arch = '<data/>'
        arch = etree.fromstring(studio_view_arch, parser=parser)
        model = view.model

        # Determine whether an operation is associated with
        # the creation of a binary field
        def create_binary_field(op):
            node = op.get('node')
            if node and node.get('tag') == 'field' and node.get('field_description'):
                ttype = node['field_description'].get('type')
                is_related = node['field_description'].get("related")
                is_image = node['attrs'].get('widget') == 'image'
                is_signature = node['attrs'].get('widget') == 'signature'
                return ttype == 'binary' and not is_image and not is_signature and not is_related
            return False

        # Every time the creation of a binary field is requested,
        # we also create an invisible char field meant to contain the filename.
        # The char field is then associated with the binary field
        # via the 'filename' attribute of the latter.
        for op in [op for op in operations if create_binary_field(op)]:
            filename = op['node']['field_description']['name'] + '_filename'

            # Create an operation adding an additional char field
            char_op = deepcopy(op)
            char_op['node']['field_description'].update({
                'name': filename,
                'type': 'char',
                'field_description': _('Filename for %s') % op['node']['field_description']['name'],
            })
            char_op['node']['attrs']['invisible'] = '1'
            operations.append(char_op)

            op['node']['attrs']['filename'] = filename

        for op in operations:
            # create a new field if it does not exist
            if 'node' in op:
                if op['node'].get('tag') == 'field' and op['node'].get('field_description'):
                    model = op['node']['field_description']['model_name']
                    # Check if field exists before creation
                    field = IrModelFields.search([
                        ('name', '=', op['node']['field_description']['name']),
                        ('model', '=', model),
                    ], limit=1)
                    if not field:
                        field = self.create_new_field(op['node']['field_description'])
                    op['node']['attrs']['name'] = field.name
                if op['node'].get('tag') == 'filter' and op['target']['tag'] == 'group' and op['node']['attrs'].get('create_group'):
                    op['node']['attrs'].pop('create_group')
                    create_group_op = {
                        'node': {
                            'tag': 'group',
                            'attrs': {
                                'name': 'studio_group_by',
                            }
                        },
                        'empty': True,
                        'target': {
                            'tag': 'search',
                        },
                        'position': 'inside',
                    }
                    self._operation_add(arch, create_group_op, model)
            # set a more specific xpath (with templates//) for the kanban view
            if view.type == 'kanban':
                if op.get('target') and op['target'].get('tag') == 'field':
                    op['target']['tag'] = 'templates//field'
                    if op['target'].get('extra_nodes'):
                        for target in op['target']['extra_nodes']:
                            target['tag'] = 'templates//' + target['tag']

            # call the right operation handler
            getattr(self, '_operation_%s' % (op['type']))(arch, op, model)

        # Save or create changes into studio view, identifiable by xmlid
        # Example for view id 42 of model crm.lead: web-studio_crm.lead-42
        new_arch = etree.tostring(arch, encoding='unicode', pretty_print=True)
        self._set_studio_view(view, new_arch)

        # Normalize the view
        studio_view = self._get_studio_view(view)
        try:
            normalized_view = studio_view.normalize()
            self._set_studio_view(view, normalized_view)
        except ValidationError:  # Element '<...>' cannot be located in parent view
            # If the studio view is not applicable after normalization, let's
            # just ignore the normalization step, it's better to have a studio
            # view that is not optimized than to prevent the user from making
            # the change he would like to make.
            self._set_studio_view(view, new_arch)

        return self._return_view(view, studio_view)

    @http.route('/web_studio/rename_field', type='json', auth='user')
    def rename_field(self, studio_view_id, studio_view_arch, model, old_name, new_name):
        studio_view = request.env['ir.ui.view'].browse(studio_view_id)

        # a field cannot be renamed if it appears in a view ; we thus reset the
        # studio view before all operations to be able to rename the field
        studio_view.arch_db = studio_view_arch

        field_id = request.env['ir.model.fields']._get(model, old_name)
        field_id.write({'name': new_name})

        if field_id.ttype == 'binary' and not field_id.related:
            # during the binary field creation, another char field containing
            # the filename has been created (see @edit_view). To avoid creating
            # the field twice, it is also renamed
            filename_field_id = request.env['ir.model.fields']._get(model, old_name + '_filename')
            if filename_field_id:
                filename_field_id.write({'name': new_name + '_filename'})

    def _create_studio_view(self, view, arch):
        # We have to play with priorities. Consider the following:
        # View Base: <field name="x"/><field name="y"/>
        # View Standard inherits Base: <field name="x" position="after"><field name="z"/></field>
        # View Custo inherits Base: <field name="x" position="after"><field name="x2"/></field>
        # We want x,x2,z,y, because that's what we did in studio, but the order of xpath
        # resolution is sequence,name, not sequence,id. Because "Custo" < "Standard", it
        # would first resolve in x,x2,y, then resolve "Standard" with x,z,x2,y as result.
        return request.env['ir.ui.view'].create({
            'type': view.type,
            'model': view.model,
            'inherit_id': view.id,
            'mode': 'extension',
            'priority': 99,
            'arch': arch,
            'name': self._generate_studio_view_name(view),
        })

    @http.route('/web_studio/edit_field', type='json', auth='user')
    def edit_field(self, model_name, field_name, values):
        field = request.env['ir.model.fields'].search([('model', '=', model_name), ('name', '=', field_name)])

        if field.ttype == 'selection' and 'selection' in values:
            selection_values = [False] + [x[0] for x in literal_eval(values['selection'])]
            records_count = request.env[model_name].search_count([(field_name, 'not in', selection_values)])
            if records_count:
                raise UserError(
                    _("""You have %s records that have a selection value different than the ones you are defining. Please modify those records first.""") % records_count
                )

        field.write(values)

        # remove default value if the value is not acceptable anymore
        if field.ttype == 'selection':
            current_default = request.env['ir.default'].get(model_name, field_name, company_id=True)
            if current_default:
                selection_values = literal_eval(field.selection)
                if current_default not in [x[0] for x in selection_values]:
                    request.env['ir.default'].discard_values(model_name, field_name, [current_default])

    @http.route('/web_studio/edit_view_arch', type='json', auth='user')
    def edit_view_arch(self, view_id, view_arch):
        view = request.env['ir.ui.view'].browse(view_id)

        if view:
            view.write({'arch': view_arch})
            ViewModel = request.env[view.model]
            try:
                fields_view = ViewModel.with_context(studio=True).fields_view_get(view.id, view.type)
                view_type = 'list' if view.type == 'tree' else view.type
                return {
                    'fields_views': {
                        view_type: fields_view,
                    },
                    'fields': ViewModel.fields_get(),
                }
            except Exception:
                return False

    @http.route('/web_studio/export', type='http', auth='user')
    def export(self, token):
        """ Exports a zip file containing the 'studio_customization' module
            gathering all customizations done with Studio (customizations of
            existing apps and freshly created apps).
        """
        studio_module = request.env['ir.module.module'].get_studio_module()
        data = request.env['ir.model.data'].search([('studio', '=', True)])
        content = export.generate_archive(studio_module, data)

        return request.make_response(content, headers=[
            ('Content-Disposition', content_disposition('customizations.zip')),
            ('Content-Type', 'application/zip'),
            ('Content-Length', len(content)),
        ], cookies={'fileToken': token})

    @http.route('/web_studio/create_default_view', type='json', auth='user')
    def create_default_view(self, model, view_type, attrs):
        attrs['string'] = "Default %s view for %s" % (view_type, model)
        arch = self._get_default_view(view_type, attrs)
        request.env['ir.ui.view'].create({
            'type': view_type,
            'model': model,
            'arch': arch,
            'name': attrs['string'],
        })

    def _get_default_view(self, view_type, attrs):
        arch = etree.Element(view_type, attrs)
        return etree.tostring(arch, encoding='unicode', pretty_print=True, method='html')

    def _get_or_create_default_view(self, model, view_type, view_id=False):
        View = request.env['ir.ui.view']
        # If we have no view_id to inherit from, it's because we are adding
        # fields to the default view of a new model. We will materialize the
        # default view as a true view so we can keep using our xpath mechanism.
        if view_id:
            view = View.browse(view_id)
        else:
            arch = request.env[model].fields_view_get(view_id, view_type)['arch']
            view = View.create({
                'type': view_type,
                'model': model,
                'arch': arch,
                'name': "Default %s view for %s" % (view_type, model),
            })
        return view

    def _node_to_expr(self, node):
        if node.get('xpath_info') and not node.get('subview_xpath'):
            # Format of expr is /form/tag1[]/tag2[]/[...]/tag[]
            expr = ''.join(['/%s[%s]' % (parent['tag'], parent['indice']) for parent in node.get('xpath_info')])
        else:
            # Format of expr is //tag[@attr1_name=attr1_value][@attr2_name=attr2_value][...]
            expr = '//' + node['tag']
            for k, v in node.get('attrs', {}).items():
                if k == 'class':
                    # Special case for classes which usually contain multiple values
                    expr += '[contains(@%s,\'%s\')]' % (k, v)
                else:
                    expr += '[@%s=\'%s\']' % (k, v)

            # Avoid matching nodes in sub views.
            # Example with field as node:
            # A field should be defined only once in a view but in some cases,
            # a view can be composed by some other views where a field with
            # the same name may exist.
            # Here, we want to generate xpath based on the nodes in the parent view only.
            if not node.get('subview_xpath'):
                expr = expr + '[not(ancestor::field)]'

        # If we receive a more specific xpath because we are editing an inline
        # view, we add it in front of the generated xpath.
        if node.get('subview_xpath'):
            xpath = node.get('subview_xpath')
            if node.get('isSubviewAttr'):
                expr = xpath
            # Hack to check if the last subview xpath element is not the same than expr
            # E.g when we add a field in an empty subview list the expr computed
            # by studio will be only '/tree' but this is useless since the
            # subview xpath already specify this element. So in this case,
            # we don't add the expr computed by studio.
            elif len(xpath) - len(expr) != xpath.find(expr):
                expr = xpath + expr
        return expr

    # Create a new xpath node based on an operation
    # TODO: rename it in master
    def _get_xpath_node(self, arch, operation):
        expr = self._node_to_expr(operation['target'])
        position = operation['position']

        return etree.SubElement(arch, 'xpath', {
            'expr': expr,
            'position': position
        })

    def _operation_remove(self, arch, operation, model=None):
        expr = self._node_to_expr(operation['target'])

        # We have to create a brand new xpath to remove this node from the view.
        etree.SubElement(arch, 'xpath', {
            'expr': expr,
            'position': 'replace'
        })
        # Sometimes, we have to delete more stuff than just a single tag. Those nodes
        # should be passed as a list in 'extra_nodes' key within the target node.
        if operation['target'].get('extra_nodes'):
            for target in operation['target']['extra_nodes']:
                expr = self._node_to_expr(target)
                etree.SubElement(arch, 'xpath', {
                    'expr': expr,
                    'position': 'replace'
                })

    def _operation_add(self, arch, operation, model):
        node = operation['node']
        xpath_node = self._get_xpath_node(arch, operation)

        # Take a xml_node and put columns on it:
        # If the xml_node is not a group, this function will create a group node
        # to add two columns on it.
        def add_columns(xml_node, title=False):
            # Get the random key generated is JS.
            # Expected value: 'studio_<tag_name>_<random_key>
            name = 'studio_group_' + xml_node.get('name').split('_')[2]

            if xml_node.tag != 'group':
                xml_node_group = etree.SubElement(xml_node, 'group', {'name': name})
            else:
                xml_node_group = xml_node

            xml_node_page_left = etree.SubElement(xml_node_group, 'group', {'name': name + '_left'})
            xml_node_page_right = etree.SubElement(xml_node_group, 'group', {'name': name + '_right'})
            if title:
                xml_node_page_left.attrib['string'] = _('Left Title')
                xml_node_page_right.attrib['string'] = _('Right Title')

        # Create the actual node inside the xpath. It needs to be the first
        # child of the xpath to respect the order in which they were added.
        xml_node = etree.Element(node['tag'], node.get('attrs'))
        if node['tag'] == 'notebook':
            name = 'studio_page_' + node['attrs']['name'].split('_')[2]
            xml_node_page = etree.Element('page', {'string': 'New Page', 'name': name})
            add_columns(xml_node_page)
            xml_node.insert(0, xml_node_page)
        elif node['tag'] == 'page':
            add_columns(xml_node)
        elif node['tag'] == 'group':
            if 'empty' not in operation:
                add_columns(xml_node, title=True)
        elif node['tag'] == 'button':
            # To create a stat button, we need
            #   - a many2one field (1) that points to this model
            #   - a field (2) that counts the number of records associated with the current record
            #   - an action to jump in (3) with the many2one field (1) as domain/context
            #
            # (1) [button_field] the many2one field
            # (2) [button_count_field] is a non-stored computed field (to always have the good value in the stat button, if access rights)
            # (3) [button_action] an act_window action to jump in the related model
            button_field = request.env['ir.model.fields'].browse(node['field'])
            button_count_field, button_action = self._get_or_create_fields_for_button(model, button_field, node['string'])

            # the XML looks like <button> <field/> </button : a element `field` needs to be inserted inside the button
            xml_node_field = etree.Element('field', {'widget': 'statinfo', 'name': button_count_field.name, 'string': node['string'] or button_count_field.field_description})
            xml_node.insert(0, xml_node_field)

            xml_node.attrib['type'] = 'action'
            xml_node.attrib['name'] = str(button_action.id)
        else:
            xml_node.text = node.get('text')
        xpath_node.insert(0, xml_node)

    def _get_or_create_fields_for_button(self, model, field, button_name):
        """ Returns the button_count_field and the button_action link to a stat button.
            @param field: a many2one field
        """

        if field.ttype != 'many2one' or field.relation != model:
            raise UserError(_('The related field of a button has to be a many2one to %s.' % model))

        model = request.env['ir.model'].search([('model', '=', model)], limit=1)

        # There is a counter on the button ; as the related field is a many2one, we need
        # to create a new computed field that counts the number of records in the one2many
        button_count_field_name = 'x_%s__%s_count' % (field.name, field.model.replace('.', '_'))[0:63]
        button_count_field = request.env['ir.model.fields'].search([('name', '=', button_count_field_name), ('model_id', '=', model.id)])
        if not button_count_field:
            compute_function = """
                    results = self.env['%(model)s'].read_group([('%(field)s', 'in', self.ids)], ['%(field)s'], ['%(field)s'])
                    dic = {}
                    for x in results: dic[x['%(field)s'][0]] = x['%(field)s_count']
                    for record in self: record['%(count_field)s'] = dic.get(record.id, 0)
                """ % {
                    'model': field.model,
                    'field': field.name,
                    'count_field': button_count_field_name,
                }
            button_count_field = request.env['ir.model.fields'].create({
                'name': button_count_field_name,
                'field_description': '%s count' % field.field_description,
                'model': model.model,
                'model_id': model.id,
                'ttype': 'integer',
                'store': False,
                'compute': compute_function.replace('    ', ''),  # remove indentation for safe_eval
            })

        # The action could already exist but we don't want to recreate one each time
        button_action_domain = "[('%s', '=', active_id)]" % (field.name)
        button_action_context = "{'search_default_%s': active_id,'default_%s': active_id}" % (field.name, field.name)
        button_action = request.env['ir.actions.act_window'].search([
            ('name', '=', button_name), ('res_model', '=', field.model),
            ('domain', '=', button_action_domain), ('context', '=', button_action_context),
        ])
        if not button_action:
            # Link the button with an associated act_window
            button_action = request.env['ir.actions.act_window'].create({
                'name': button_name,
                'res_model': field.model,
                'view_mode': 'tree,form',
                'domain': button_action_domain,
                'context': button_action_context,
            })

        return button_count_field, button_action

    def _operation_move(self, arch, operation, model=None):
        xpath_node = self._get_xpath_node(arch, operation)
        xml_node = etree.Element('xpath', {
            'expr': self._node_to_expr(operation['node']),
            'position': 'move',
        })
        xpath_node.append(xml_node)

    # Create or update node for each attribute
    def _operation_attributes(self, arch, operation, model=None):
        ir_model_data = request.env['ir.model.data']
        new_attrs = operation['new_attrs']

        if 'groups' in new_attrs:
            eval_attr = []
            for many2many_value in new_attrs['groups']:
                group_xmlid = ir_model_data.search([
                    ('model', '=', 'res.groups'),
                    ('res_id', '=', many2many_value)])
                if not group_xmlid:
                    raise UserError(_(
                        "Only groups with an external ID can be used here. Please choose another " +
                        "group or assign manually an external ID to this group."
                    ))
                eval_attr.append(group_xmlid.complete_name)
            eval_attr = ",".join(eval_attr)
            new_attrs['groups'] = eval_attr

        if new_attrs.get('options'):
            options = json.loads(new_attrs['options'])
            if 'color_field' in options:
                field_name = operation['node']['attrs']['name']
                field_id = request.env['ir.model.fields'].search([('model', '=', model), ('name', '=', field_name)])
                related_model_id = request.env['ir.model'].search([('model', '=', field_id.relation)])

                if 'color' in related_model_id.field_id.mapped('name'):
                    options['color_field'] = 'color'
                else:
                    if 'x_color' not in related_model_id.field_id.mapped('name'):
                        request.env['ir.model.fields'].create({
                            'model': related_model_id.name,
                            'model_id': related_model_id.id,
                            'name': 'x_color',
                            'field_description': 'Color',
                            'ttype': 'integer',
                        })
                    options['color_field'] = 'x_color'
                new_attrs['options'] = json.dumps(options)


        xpath_node = self._get_xpath_node(arch, operation)

        for key, new_attr in new_attrs.items():
            xml_node = etree.Element('attribute', {'name': key})
            xml_node.text = str(new_attr)
            xpath_node.insert(0, xml_node)

            # change the field description when changing the field label (for custom fields)
            if key == 'string' and operation.get('node', {}).get('tag') == 'field':
                field_name = operation.get('node', {}).get('attrs', {}).get('name')
                field_id = request.env['ir.model.fields'].search([('model', '=', model), ('name', '=', field_name)])
                if field_name.startswith('x_') and field_id and field_id.field_description != new_attr:
                    field_id.write({'field_description': new_attr})

    def _operation_buttonbox(self, arch, operation, model=None):
        studio_view_arch = arch  # The actual arch is the studio view arch
        # Get the arch of the form view with inherited views applied
        arch = request.env[model].fields_view_get(view_type='form')['arch']
        parser = etree.XMLParser(remove_blank_text=True)
        arch = etree.fromstring(arch, parser=parser)

        # Create xpath to put the buttonbox as the first child of the sheet
        if arch.find('sheet'):
            sheet_node = arch.find('sheet')
            if list(sheet_node):
                # Check if children exists
                xpath_node = etree.SubElement(studio_view_arch, 'xpath', {
                    'expr': '//sheet/*[1]',
                    'position': 'before'
                })
            else:
                xpath_node = etree.SubElement(studio_view_arch, 'xpath', {
                    'expr': '//sheet',
                    'position': 'inside'
                })
            # Create and insert the buttonbox node inside the xpath node
            buttonbox_node = etree.Element('div', {'name': 'button_box', 'class': 'oe_button_box'})
            xpath_node.append(buttonbox_node)

    def _operation_chatter(self, arch, operation, model=None):
        def _get_remove_field_op(arch, field_name):
            return {
                'type': 'remove',
                'target': {
                    'tag': 'field',
                    'attrs': {
                        'name': field_name,
                    },
                }
            }

        if not self.is_chatter_allowed(operation['model']):
            # Chatter can only be activated form models that (can) inherit from mail.thread
            return

        # From this point, the model is either a custom model or inherits from mail.thread
        model = request.env['ir.model'].search([('model', '=', operation['model'])])
        if model.state == 'manual' and not model.is_mail_thread:
            # Activate mail.thread inheritance on the custom model
            model.write({'is_mail_thread': True})
        if model.state == 'manual' and not model.is_mail_activity:
            # Activate mail.activity inheritance on the custom model
            model.write({'is_mail_activity': True})

        # Remove message_ids, activity_ids and message_follower_ids if already defined in form view
        if operation['remove_message_ids']:
            self._operation_remove(arch, _get_remove_field_op(arch, 'message_ids'))
        if operation['remove_follower_ids']:
            self._operation_remove(arch, _get_remove_field_op(arch, 'message_follower_ids'))
        if operation['remove_activity_ids']:
            self._operation_remove(arch, _get_remove_field_op(arch, 'activity_ids'))

        xpath_node = etree.SubElement(arch, 'xpath', {
            'expr': '//sheet',
            'position': 'after',
        })
        chatter_node = etree.Element('div', {'class': 'oe_chatter'})
        follower_node = etree.Element('field', {'name': 'message_follower_ids', 'widget': 'mail_followers'})
        activity_node = etree.Element('field', {'name': 'activity_ids', 'widget': 'mail_activity'})
        thread_node = etree.Element('field', {'name': 'message_ids', 'widget': 'mail_thread'})
        chatter_node.append(follower_node)
        chatter_node.append(activity_node)
        chatter_node.append(thread_node)
        xpath_node.append(chatter_node)

    def _operation_kanban_dropdown(self, arch, operation, model):
        """ Insert a dropdown and its corresponding needs in an kanban view arch.
            Implied modifications:
                - create an integer field x_color in the model if it doesn't exist
                - add the field x_color in the view
                - add a dropdown section in the view
                - modify the kanban class to use `oe_kanban_color_`
        """
        model_id = request.env['ir.model'].search([('model', '=', model)])
        if not model_id:
            return

        color_field_name = 'x_color'
        if not request.env['ir.model.fields'].search([('model_id', '=', model_id.id), ('name', '=', color_field_name), ('ttype', '=', 'integer')]):
            # create a field if it doesn't exist in the model
            request.env['ir.model.fields'].create({
                'model': model,
                'model_id': model_id.id,
                'name': color_field_name,
                'field_description': 'Color',
                'ttype': 'integer',
            })

        # add the field at the beginning
        etree.SubElement(arch, 'xpath', {
            'expr': 'templates',
            'position': 'before',
        }).append(etree.Element('field', {'name': color_field_name}))

        # add the dropdown before the rest
        dropdown_node = etree.fromstring("""
            <div class="o_dropdown_kanban dropdown" name="kanban_dropdown">
                <a class="dropdown-toggle o-no-caret btn" data-toggle="dropdown" href="#" aria-label="Dropdown menu" title="Dropdown menu" role="button">
                    <span class="fa fa-bars fa-lg"/>
                </a>
                <div class="dropdown-menu" role="menu">
                    <t t-if="widget.editable"><a type="edit" class="dropdown-item">Edit</a></t>
                    <t t-if="widget.deletable"><a type="delete" class="dropdown-item">Delete</a></t>
                    <ul class="oe_kanban_colorpicker" data-field="%(field)s"/>
                </div>
            </div>
        """ % {'field': color_field_name})
        etree.SubElement(arch, 'xpath', {
            'expr': '//div/*[1]',
            'position': 'before',
        }).append(dropdown_node)

        # set the corresponding color attribute on the kanban record
        xpath_node = etree.SubElement(arch, 'xpath', {
            'expr': '//div',
            'position': 'attributes',
        })
        xml_node = xpath_node.find('attribute[@name="%s"]' % ('color'))
        if xml_node is None:
            xml_node = etree.Element('attribute', {'name': 'color'})
            xml_node.text = color_field_name
            xpath_node.insert(0, xml_node)
        else:
            xml_node.text = color_field_name

    def _operation_kanban_image(self, arch, operation, model):
        """ Insert a image and its corresponding needs in an kanban view arch
            Implied modifications:
                - add the field in the view
                - add a section (kanban_right) in the view
                - add the field with `kanban_image` in this section
        """
        model_id = request.env['ir.model'].search([('model', '=', model)])
        if not model_id:
            raise UserError(_('The model %s does not exist.') % model)

        if not operation.get('field'):
            raise UserError(_('Please specify a field.'))

        field_id = request.env['ir.model.fields'].search([
            ('model', '=', model),
            ('name', '=', operation['field'])
        ])
        if not field_id:
            raise UserError(_('The field %s does not exist.') % operation['field'])

        # add field at the beginning
        etree.SubElement(arch, 'xpath', {
            'expr': 'templates',
            'position': 'before',
        }).append(etree.Element('field', {'name': field_id.name}))

        # add the image inside the view
        etree.SubElement(arch, 'xpath', {
            'expr': '//div',
            'position': 'inside',
        }).append(
            etree.fromstring("""
                <div class="oe_kanban_bottom_right">
                    <img
                        t-att-src="kanban_image('%(model)s', 'image_128', record.%(field)s.raw_value)"
                        t-att-title="record.%(field)s.value"
                        class="oe_kanban_avatar o_image_24_cover float-right"
                    />
                </div>
            """ % {'model': field_id.relation, 'field': field_id.name})
        )

    def _operation_kanban_set_cover(self, arch, operation, model):
        """ Insert a menu in dropdown to set cover image in a kanban view.
            Implied modifications:
                - adds the given m2o field in the view (may create new field
                  'x_studio_cover_image_id' if there's no compatible field)
                - adds an option inside dropdown section in the view
                - adds an field having widget `attachment_image` in the view
        """
        model_id = request.env['ir.model'].search([('model', '=', model)])
        if not model_id:
            raise UserError(_('The model %s does not exist.') % model)
        if operation.get('field'):
            field_id = request.env['ir.model.fields'].search([
                ('model', '=', model),
                ('name', '=', operation['field'])
            ])
            if not field_id:
                raise UserError(_('The field %s does not exist.') % operation['field'])
        else:
            att_model = request.env['ir.model'].search([('model', '=', 'ir.attachment')])
            field_id = request.env['ir.model.fields'].search([
                ('model', '=', model_id.model),
                ('name', '=', 'x_studio_cover_image_id'),
                ('ttype', '=', 'many2one')
            ])
            # create a field many2one x_studio_cover_image_id if it doesn't exist in the model
            if not field_id:
                field_id = request.env['ir.model.fields'].create({
                    'model': model_id.model,
                    'model_id': model_id.id,
                    'relation': att_model.model,
                    'name': 'x_studio_cover_image_id',
                    'field_description': 'Cover Image',
                    'ttype': 'many2one',
                    'domain': '[("res_model", "=", "%s"), ("res_id", "=", "%s"), ("mimetype", "ilike", "image")]' % (model_id.model, model_id.id)
                })

        # add link inside the dropdown
        etree.SubElement(arch, 'xpath', {
            'expr': '//div[hasclass("dropdown-menu")]//a',
            'position': 'before',
        }).append(
            etree.fromstring("""
                <a data-type="set_cover" href="#" data-field="%s" class="dropdown-item oe_kanban_action oe_kanban_action_a" >
                    Set Cover Image
                </a>
            """ % (field_id.name))
        )
        studio_view_arch = arch
        arch = request.env[model]._fields_view_get(view_type='kanban')['arch']
        parser = etree.XMLParser(remove_blank_text=True)
        arch = etree.fromstring(arch, parser=parser)

        # try to find the best place to put the cover
        possible_hooks = [
            {'expr': '//div[hasclass("o_kanban_record_body")]', 'position' : 'inside'},
            {'expr': '//div[hasclass("o_kanban_record_bottom")]', 'position' : 'before'},
            {'expr': '//div[hasclass("oe_kanban_details")]', 'position' : 'inside'},
            {'expr': '//div', 'position': 'inside'},
        ]
        for hook in possible_hooks:
            if len(arch.xpath(hook['expr'])):
                break

        xpath_node = etree.SubElement(studio_view_arch, 'xpath', hook)
        xpath_node.append(etree.fromstring("""
                <field t-if="record.%s.value" name="%s" widget="attachment_image"/>
            """ % (field_id.name, field_id.name)))

    def _operation_kanban_priority(self, arch, operation, model):
        """ Insert a priority and its corresponding needs in an kanban view arch
            Implied modifications:
                - create a selection field x_priority in the model if it doesn't exist
                - add a section (kanban_left) in the view
                - add the field x_priority with the widget priority in this section
        """
        model_id = request.env['ir.model'].search([('model', '=', model)])
        if not model_id:
            raise UserError(_('The model %s does not exist.') % model)

        if operation.get('field'):
            field_id = request.env['ir.model.fields'].search([
                ('model', '=', model),
                ('name', '=', operation['field'])
            ])
            if not field_id:
                raise UserError(_('The field %s does not exist.') % operation['field'])

        else:
            field_id = request.env['ir.model.fields'].search([
                ('model_id', '=', model_id.id),
                ('name', '=', 'x_priority'),
                ('ttype', '=', 'selection')
            ])
            # create a field selection x_priority if it doesn't exist in the model
            if not field_id:
                field_id = request.env['ir.model.fields'].create({
                    'model': model,
                    'model_id': model_id.id,
                    'name': 'x_priority',
                    'field_description': 'Priority',
                    'ttype': 'selection',
                    'selection': "[('0', 'Low'), ('1', 'Normal'), ('2', 'High')]",
                })

        # add priority inside the view
        etree.SubElement(arch, 'xpath', {
            'expr': '//div',
            'position': 'inside',
        }).append(
            etree.fromstring("""
                <div class="oe_kanban_bottom_left">
                    <field name="%s" widget="priority"/>
                </div>
            """ % (field_id.name))
        )

    def _operation_statusbar(self, arch, operation, model=None):
        """ Create and insert a header as the first child of the form. """
        xpath_node = etree.SubElement(arch, 'xpath', {
            'expr': '//form/*[1]',
            'position': 'before'
        })
        xpath_node.append(etree.Element('header'))

    @http.route('/web_studio/get_email_alias', type='json', auth='user')
    def get_email_alias(self, model_name):
        """ Returns the email alias associated to the model @model_name if both exist
        """
        result = {'alias_domain': request.env['ir.config_parameter'].get_param('mail.catchall.domain')}
        model = request.env['ir.model'].search([('model', '=', model_name)], limit=1)
        if model:
            email_alias = request.env['mail.alias'].search([('alias_model_id', '=', model.id)], limit=1)
            if email_alias:
                result['email_alias'] = email_alias.alias_name
        return result

    @http.route('/web_studio/set_email_alias', type='json', auth='user')
    def set_email_alias(self, model_name, value):
        """ Set the email alias associated to the model @model_name
             - if there is no email alias, it will be created
             - if there is one and the value is empty, it will be unlinked
        """
        model = request.env['ir.model'].search([('model', '=', model_name)], limit=1)
        if model:
            email_alias = request.env['mail.alias'].search([('alias_model_id', '=', model.id)], limit=1)
            if email_alias:
                if value:
                    email_alias.alias_name = value
                else:
                    email_alias.unlink()
            else:
                request.env['mail.alias'].create({
                    'alias_model_id': model.id,
                    'alias_name': value,
                })

    @http.route('/web_studio/get_default_value', type='json', auth='user')
    def get_default_value(self, model_name, field_name):
        """ Return the default value associated to the given field. """
        return {
            'default_value': request.env['ir.default'].get(model_name, field_name, company_id=True)
        }

    @http.route('/web_studio/set_default_value', type='json', auth='user')
    def set_default_value(self, model_name, field_name, value):
        """ Set the default value associated to the given field. """
        request.env['ir.default'].set(model_name, field_name, value, company_id=True)

    @http.route('/web_studio/create_inline_view', type='json', auth='user')
    def create_inline_view(self, model, view_id, field_name, subview_type, subview_xpath):
        view = request.env['ir.ui.view'].browse(view_id)
        studio_view = self._get_studio_view(view)
        if not studio_view:
            studio_view = self._create_studio_view(view, '<data/>')
        parser = etree.XMLParser(remove_blank_text=True)
        arch = etree.fromstring(studio_view.arch_db, parser=parser)
        expr = "//field[@name='%s']" % field_name
        if subview_xpath:
            expr = subview_xpath + expr
        position = 'inside'
        xpath_node = arch.find('xpath[@expr="%s"][@position="%s"]' % (expr, position))
        if xpath_node is None:  # bool(node) == False if node has no children
            xpath_node = etree.SubElement(arch, 'xpath', {
                'expr': expr,
                'position': position
            })
        inline_view = request.env[model]._fields_view_get(view_type=subview_type)
        view_arch = inline_view['arch']
        xml_node = self._inline_view_filter_nodes(etree.fromstring(view_arch))
        xpath_node.insert(0, xml_node)
        studio_view.arch_db = etree.tostring(arch, encoding='utf-8', pretty_print=True)
        return studio_view.arch_db

    def _inline_view_filter_nodes(self, inline_view_etree):
        """
        Filters out from a standard view some nodes that are
        irrelevant in an inline view (like the chatter)

        @param {Etree} inline_view_etree: the arch of the view
        @return {Etree}
        """
        unwanted_xpath = [
            "*[hasclass('oe_chatter')]",
            "*[hasclass('o_attachment_preview')]",
        ]
        for path in unwanted_xpath:
            for node in inline_view_etree.xpath(path):
                inline_view_etree.remove(node)

        return inline_view_etree
