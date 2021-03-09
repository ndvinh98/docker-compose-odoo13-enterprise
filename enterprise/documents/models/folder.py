# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class DocumentFolder(models.Model):
    _name = 'documents.folder'
    _description = 'Documents Workspace'
    _parent_name = 'parent_folder_id'
    _order = 'sequence'

    @api.constrains('parent_folder_id')
    def _check_parent_folder_id(self):
        if not self._check_recursion():
            raise ValidationError(_('You cannot create recursive folders.'))

    @api.model
    def default_get(self, fields):
        res = super(DocumentFolder, self).default_get(fields)
        if self._context.get('folder_id'):
            res['parent_folder_id'] = self._context.get('folder_id')

        return res

    def name_get(self):
        name_array = []
        hierarchical_naming = self.env.context.get('hierarchical_naming', True)
        for record in self:
            if hierarchical_naming and record.parent_folder_id:
                name_array.append((record.id, "%s / %s" % (record.parent_folder_id.name, record.name)))
            else:
                name_array.append((record.id, record.name))
        return name_array

    company_id = fields.Many2one('res.company', 'Company',
                                 help="This workspace will only be available to the selected company")
    parent_folder_id = fields.Many2one('documents.folder',
                                       string="Parent Workspace",
                                       ondelete="cascade",
                                       help="A workspace will inherit the tags of its parent workspace")
    name = fields.Char(required=True, translate=True)
    description = fields.Html(string="Description", translate=True)
    children_folder_ids = fields.One2many('documents.folder', 'parent_folder_id', string="Sub workspaces")
    document_ids = fields.One2many('documents.document', 'folder_id', string="Documents")
    sequence = fields.Integer('Sequence', default=10)
    share_link_ids = fields.One2many('documents.share', 'folder_id', string="Share Links")
    facet_ids = fields.One2many('documents.facet', 'folder_id',
                                string="Tag Categories",
                                help="Tag categories defined for this workspace")
    group_ids = fields.Many2many('res.groups',
        string="Write Groups", help='Groups able to see the workspace and read/create/edit its documents.')
    read_group_ids = fields.Many2many('res.groups', 'documents_folder_read_groups',
        string="Read Groups", help='Groups able to see the workspace and read its documents without create/edit rights.')

    user_specific = fields.Boolean(string="Own Documents Only",
                                   help="Limit Read Groups to the documents of which they are owner.")

    #stat buttons
    action_count = fields.Integer('Action Count', compute='_compute_action_count')
    document_count = fields.Integer('Document Count', compute='_compute_document_count')

    def _compute_action_count(self):
        read_group_var = self.env['documents.workflow.rule'].read_group(
            [('domain_folder_id', 'in', self.ids)],
            fields=['domain_folder_id'],
            groupby=['domain_folder_id'])

        action_count_dict = dict((d['domain_folder_id'][0], d['domain_folder_id_count']) for d in read_group_var)
        for record in self:
            record.action_count = action_count_dict.get(record.id, 0)

    def action_see_actions(self):
        domain = [('domain_folder_id', '=', self.id)]
        return {
            'name': _('Actions'),
            'domain': domain,
            'res_model': 'documents.workflow.rule',
            'type': 'ir.actions.act_window',
            'views': [(False, 'list'), (False, 'form')],
            'view_mode': 'tree,form',
            'context': "{'default_domain_folder_id': %s}" % self.id
        }

    def _compute_document_count(self):
        read_group_var = self.env['documents.document'].read_group(
            [('folder_id', 'in', self.ids)],
            fields=['folder_id'],
            groupby=['folder_id'])

        document_count_dict = dict((d['folder_id'][0], d['folder_id_count']) for d in read_group_var)
        for record in self:
            record.document_count = document_count_dict.get(record.id, 0)

    def action_see_documents(self):
        domain = [('folder_id', '=', self.id)]
        return {
            'name': _('Documents'),
            'domain': domain,
            'res_model': 'documents.document',
            'type': 'ir.actions.act_window',
            'views': [(False, 'list'), (False, 'form')],
            'view_mode': 'tree,form',
            'context': "{'default_folder_id': %s}" % self.id
        }
