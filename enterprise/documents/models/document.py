# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools import image_process
from ast import literal_eval
from dateutil.relativedelta import relativedelta
from collections import OrderedDict


class Document(models.Model):
    _name = 'documents.document'
    _description = 'Document'
    _inherit = ['mail.thread.cc', 'mail.activity.mixin']
    _order = 'id desc'

    # Attachment
    attachment_id = fields.Many2one('ir.attachment', auto_join=True, copy=False)
    attachment_name = fields.Char('Attachment Name', related='attachment_id.name', readonly=False)
    attachment_type = fields.Selection(string='Attachment Type', related='attachment_id.type', readonly=False)
    datas = fields.Binary(related='attachment_id.datas', related_sudo=True, readonly=False)
    file_size = fields.Integer(related='attachment_id.file_size', store=True)
    checksum = fields.Char(related='attachment_id.checksum')
    mimetype = fields.Char(related='attachment_id.mimetype', default='application/octet-stream')
    res_model = fields.Char('Resource Model', compute="_compute_res_record", inverse="_inverse_res_model", store=True)
    res_id = fields.Integer('Resource ID', compute="_compute_res_record", inverse="_inverse_res_id", store=True)
    res_name = fields.Char('Resource Name', related='attachment_id.res_name')
    index_content = fields.Text(related='attachment_id.index_content')
    description = fields.Text('Attachment Description', related='attachment_id.description', readonly=False)

    # Document
    name = fields.Char('Name', copy=True, store=True, compute='_compute_name', inverse='_inverse_name')
    active = fields.Boolean(default=True, string="Active")
    thumbnail = fields.Binary(readonly=1, store=True, attachment=True, compute='_compute_thumbnail')
    url = fields.Char('URL', index=True, size=1024, tracking=True)
    res_model_name = fields.Char(compute='_compute_res_model_name', index=True)
    type = fields.Selection([('url', 'URL'), ('binary', 'File'), ('empty', 'Request')],
                            string='Type', required=True, store=True, default='empty', change_default=True,
                            compute='_compute_type')
    favorited_ids = fields.Many2many('res.users', string="Favorite of")
    tag_ids = fields.Many2many('documents.tag', 'document_tag_rel', string="Tags")
    partner_id = fields.Many2one('res.partner', string="Contact", tracking=True)
    owner_id = fields.Many2one('res.users', default=lambda self: self.env.user.id, string="Owner",
                               tracking=True)
    available_rule_ids = fields.Many2many('documents.workflow.rule', compute='_compute_available_rules',
                                          string='Available Rules')
    lock_uid = fields.Many2one('res.users', string="Locked by")
    is_locked = fields.Boolean(compute="_compute_is_locked", string="Locked")
    create_share_id = fields.Many2one('documents.share', help='Share used to create this document')
    request_activity_id = fields.Many2one('mail.activity')

    # Folder
    folder_id = fields.Many2one('documents.folder',
                                string="Workspace",
                                ondelete="restrict",
                                tracking=True,
                                required=True,
                                index=True)
    company_id = fields.Many2one('res.company', string='Company', related='folder_id.company_id', readonly=True)
    group_ids = fields.Many2many('res.groups', string="Access Groups", readonly=True,
                                 help="This attachment will only be available for the selected user groups",
                                 related='folder_id.group_ids')

    _sql_constraints = [
        ('attachment_unique', 'unique (attachment_id)', "This attachment is already a document"),
    ]

    @api.depends('attachment_id.name')
    def _compute_name(self):
        for record in self:
            if record.attachment_name:
                record.name = record.attachment_name

    def _inverse_name(self):
        for record in self:
            if record.attachment_id:
                record.attachment_name = record.name

    @api.depends('attachment_id', 'attachment_id.res_model', 'attachment_id.res_id')
    def _compute_res_record(self):
        for record in self:
            attachment = record.attachment_id
            if attachment:
                record.res_model = attachment.res_model
                record.res_id = attachment.res_id

    def _inverse_res_id(self):
        for record in self:
            attachment = record.attachment_id.with_context(no_document=True)
            if attachment:
                attachment.res_id = record.res_id

    def _inverse_res_model(self):
        for record in self:
            attachment = record.attachment_id.with_context(no_document=True)
            if attachment:
                attachment.res_model = record.res_model

    @api.onchange('url')
    def _onchange_url(self):
        if self.url and not self.name:
            self.name = self.url.rsplit('/')[-1]

    @api.depends('checksum')
    def _compute_thumbnail(self):
        for record in self:
            try:
                record.thumbnail = image_process(record.datas, size=(80, 80), crop='center')
            except UserError:
                record.thumbnail = False

    @api.depends('attachment_type', 'url')
    def _compute_type(self):
        for record in self:
            record.type = 'empty'
            if record.attachment_id:
                record.type = 'binary'
            elif record.url:
                record.type = 'url'

    def _get_models(self, domain):
        """
        Return the names of the models to which the attachments are attached.

        :param domain: the domain of the read_group on documents.
        :return: a list of model data, the latter being a dict with the keys
            'id' (technical name),
            'name' (display name) and
            'count' (how many attachments with that domain).
        """
        not_a_file = []
        not_attached = []
        models = []
        groups = self.read_group(domain, ['res_model'], ['res_model'], lazy=True)
        for group in groups:
            res_model = group['res_model']
            if not res_model:
                not_a_file.append({
                    'id': res_model,
                    'name': _('Not a file'),
                    'count': group['res_model_count'],
                })
            elif res_model == 'documents.document':
                not_attached.append({
                    'id': res_model,
                    'name': _('Not attached'),
                    'count': group['res_model_count'],
                })
            else:
                models.append({
                    'id': res_model,
                    'name': self.env['ir.model']._get(res_model).display_name,
                    'count': group['res_model_count'],
                })
        return sorted(models, key=lambda m: m['name']) + not_attached + not_a_file

    @api.depends('res_model')
    def _compute_res_model_name(self):
        for record in self:
            if record.res_model:
                model = self.env['ir.model'].name_search(record.res_model, limit=1)
                if model:
                    record.res_model_name = model[0][1]
                else:
                    record.res_model_name = False
            else:
                record.res_model_name = False

    @api.depends('folder_id')
    def _compute_available_rules(self):
        """
        loads the rules that can be applied to the attachment.

        """
        self.available_rule_ids = False
        folder_ids = self.mapped('folder_id.id')
        rule_domain = [('domain_folder_id', 'parent_of', folder_ids)] if folder_ids else []
        # searching rules with sudo as rules are inherited from parent folders and should be available even
        # when they come from a restricted folder.
        rules = self.env['documents.workflow.rule'].sudo().search(rule_domain)
        for rule in rules:
            domain = []
            if rule.condition_type == 'domain':
                domain = literal_eval(rule.domain) if rule.domain else []
            else:
                if rule.criteria_partner_id:
                    domain = expression.AND([[['partner_id', '=', rule.criteria_partner_id.id]], domain])
                if rule.criteria_owner_id:
                    domain = expression.AND([[['owner_id', '=', rule.criteria_owner_id.id]], domain])
                if rule.create_model:
                    domain = expression.AND([[['type', '=', 'binary']], domain])
                if rule.required_tag_ids:
                    domain = expression.AND([[['tag_ids', 'in', rule.required_tag_ids.ids]], domain])
                if rule.excluded_tag_ids:
                    domain = expression.AND([[['tag_ids', 'not in', rule.excluded_tag_ids.ids]], domain])

            folder_domain = [['folder_id', 'child_of', rule.domain_folder_id.id]]
            subset = expression.AND([[['id', 'in', self.ids]], domain, folder_domain])
            document_ids = self.env['documents.document'].search(subset)
            for document in document_ids:
                document.available_rule_ids = [(4, rule.id, False)]

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """
        creates a new attachment from any email sent to the alias
        and adds the values defined in the share link upload settings
        to the custom values.
        """
        subject = msg_dict.get('subject', '')
        if custom_values is None:
            custom_values = {}
        defaults = {
            'name': "Mail: %s" % subject,
            'active': False,
        }
        defaults.update(custom_values)

        return super(Document, self).message_new(msg_dict, defaults)

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, *, message_type='notification', **kwargs):
        if message_type == 'email' and self.create_share_id:
            self = self.with_context(no_document=True)
        return super(Document, self).message_post(message_type=message_type, **kwargs)

    @api.model
    def _message_post_after_hook(self, message, msg_vals):
        """
        If the res model was an attachment and a mail, adds all the custom values of the share link
            settings to the attachments of the mail.

        """
        m2m_commands = msg_vals['attachment_ids']
        share = self.create_share_id
        if share:
            attachments = self.env['ir.attachment'].browse([x[1] for x in m2m_commands])
            for attachment in attachments:
                document = self.env['documents.document'].create({
                    'name': attachment.name,
                    'attachment_id': attachment.id,
                    'folder_id': share.folder_id.id,
                    'owner_id': share.owner_id.id if share.owner_id else share.create_uid.id,
                    'partner_id': share.partner_id.id if share.partner_id else False,
                    'tag_ids': [(6, 0, share.tag_ids.ids if share.tag_ids else [])],
                })
                attachment.write({
                    'res_model': 'documents.document',
                    'res_id': document.id,
                })
                document.message_post(body=msg_vals.get('body', ''), subject=self.name)
                if share.activity_option:
                    document.documents_set_activity(settings_record=share)

        return super(Document, self)._message_post_after_hook(message, msg_vals)

    def documents_set_activity(self, settings_record=None):
        """
        Generate an activity based on the fields of settings_record.

        :param settings_record: the record that contains the activity fields.
                    settings_record.activity_type_id (required)
                    settings_record.activity_summary
                    settings_record.activity_note
                    settings_record.activity_date_deadline_range
                    settings_record.activity_date_deadline_range_type
                    settings_record.activity_user_id
        """
        if settings_record and settings_record.activity_type_id:
            activity_vals = {
                'activity_type_id': settings_record.activity_type_id.id,
                'summary': settings_record.activity_summary or '',
                'note': settings_record.activity_note or '',
            }
            if settings_record.activity_date_deadline_range > 0:
                activity_vals['date_deadline'] = fields.Date.context_today(settings_record) + relativedelta(
                    **{settings_record.activity_date_deadline_range_type: settings_record.activity_date_deadline_range})

            if settings_record._fields.get('activity_user_id') and settings_record.activity_user_id:
                user = settings_record.activity_user_id
            elif settings_record._fields.get('user_id') and settings_record.user_id:
                user = settings_record.user_id
            elif settings_record._fields.get('owner_id') and settings_record.owner_id:
                user = settings_record.owner_id
            else:
                user = self.env.user
            if user:
                activity_vals['user_id'] = user.id
            self.activity_schedule(**activity_vals)

    def toggle_favorited(self):
        self.ensure_one()
        self.write({'favorited_ids': [(3 if self.env.user in self[0].favorited_ids else 4, self.env.user.id)]})

    def access_content(self):
        self.ensure_one()
        action = {
            'type': "ir.actions.act_url",
            'target': "new",
        }
        if self.url:
            action['url'] = self.url
        elif self.type == 'binary':
            action['url'] = '/documents/content/%s' % self.id
        return action

    def create_share(self):
        self.ensure_one()
        vals = {
            'type': 'ids',
            'document_ids': [(6, 0, self.ids)],
            'folder_id': self.folder_id.id,
        }
        return self.env['documents.share'].create_share(vals)

    def open_resource(self):
        self.ensure_one()
        if self.res_model and self.res_id:
            view_id = self.env[self.res_model].get_formview_id(self.res_id)
            return {
                'res_id': self.res_id,
                'res_model': self.res_model,
                'type': 'ir.actions.act_window',
                'views': [[view_id, 'form']],
            }

    def toggle_lock(self):
        """
        sets a lock user, the lock user is the user who locks a file for themselves, preventing data replacement
        and archive (therefore deletion) for any user but himself.

        Members of the group documents.group_document_manager and the superuser can unlock the file regardless.
        """
        self.ensure_one()
        if self.lock_uid:
            if self.env.user == self.lock_uid or self.env.is_admin() or self.user_has_groups(
                    'documents.group_document_manager'):
                self.lock_uid = False
        else:
            self.lock_uid = self.env.uid

    def _compute_is_locked(self):
        for record in self:
            record.is_locked = record.lock_uid and not (
                    self.env.user == record.lock_uid or
                    self.env.is_admin() or
                    self.user_has_groups('documents.group_document_manager'))


    @api.model
    def create(self, vals):
        keys = [key for key in vals if
                self._fields[key].related and self._fields[key].related[0] == 'attachment_id']
        attachment_dict = {key: vals.pop(key) for key in keys if key in vals}
        attachment = self.env['ir.attachment'].browse(vals.get('attachment_id'))

        if attachment and attachment_dict:
            attachment.write(attachment_dict)
        elif attachment_dict:
            attachment_dict.setdefault('name', vals.get('name', 'unnamed'))
            attachment = self.env['ir.attachment'].create(attachment_dict)
            vals['attachment_id'] = attachment.id
        new_record = super(Document, self).create(vals)

        # this condition takes precedence during forward-port.
        if (attachment and not attachment.res_id and (not attachment.res_model or attachment.res_model == 'documents.document')):
            attachment.with_context(no_document=True).write({'res_model': 'documents.document', 'res_id': new_record.id})
        return new_record

    def write(self, vals):
        attachment_id = vals.get('attachment_id')
        if attachment_id:
            self.ensure_one()
        for record in self:

            if record.type == 'empty' and ('datas' in vals or 'url' in vals):
                body = _("Document Request: %s Uploaded by: %s") % (record.name, self.env.user.name)
                record.message_post(body=body)

            if vals.get('datas') and not vals.get('attachment_id') and not record.attachment_id:
                res_model = vals.get('res_model', record.res_model or 'documents.document')
                res_id = vals.get('res_id') if vals.get('res_model') else record.res_id if record.res_model else record.id
                if res_model and res_model != 'documents.document' and not self.env[res_model].browse(res_id).exists():
                    record.res_model = res_model = 'documents.document'
                    record.res_id = res_id = record.id
                attachment = self.env['ir.attachment'].with_context(no_document=True).create({
                    'name': vals.get('name', record.name),
                    'res_model': res_model,
                    'res_id': res_id
                })
                record.attachment_id = attachment.id
                record._process_activities(attachment.id)

        # pops the datas and/or the mimetype key(s) to explicitly write them in batch on the ir.attachment
        # so the mimetype is properly set. The reason was because the related keys are not written in batch
        # and because mimetype is readonly on `ir.attachment` (which prevents writing through the related).
        attachment_dict = {key: vals.pop(key) for key in ['datas', 'mimetype'] if key in vals}

        write_result = super(Document, self).write(vals)
        if attachment_dict:
            self.mapped('attachment_id').write(attachment_dict)

        return write_result

    def _process_activities(self, attachment_id):
        self.ensure_one()
        if attachment_id and self.request_activity_id:
            feedback = _("Document Request: %s Uploaded by: %s") % (self.name, self.env.user.name)
            self.request_activity_id.action_feedback(feedback=feedback, attachment_ids=[attachment_id])

    def split_pdf(self, indices=None, remainder=False):
        self.ensure_one()
        if self.attachment_id:
            attachment_ids = self.attachment_id.split_pdf(indices=indices, remainder=remainder)
            for attachment in attachment_ids:
                document = self.copy()
                document.write({'attachment_id': attachment.id})

    @api.model
    def search_panel_select_range(self, field_name):
        if field_name == 'folder_id':
            fields = ['display_name', 'description', 'parent_folder_id']
            available_folders = self.env['documents.folder'].search([])
            folder_domain = expression.OR([[('parent_folder_id', 'parent_of', available_folders.ids)], [('id', 'in', available_folders.ids)]])
            # also fetches the ancestors of the available folders to display the complete folder tree for all available folders.
            DocumentFolder = self.env['documents.folder'].sudo().with_context(hierarchical_naming=False)
            return {
                'parent_field': 'parent_folder_id',
                'values': DocumentFolder.search_read(folder_domain, fields),
            }
        return super(Document, self).search_panel_select_range(field_name)

    def _get_processed_tags(self, domain, folder_id):
        """
        sets a group color to the tags based on the order of the facets (group_id)
        recomputed each time the search_panel fetches the tags as the colors depend on the order and
        amount of tag categories. If the amount of categories exceeds the amount of colors, the color
        loops back to the first one.
        """
        tags = self.env['documents.tag']._get_tags(domain, folder_id)
        facets = list(OrderedDict.fromkeys([tag['group_id'] for tag in tags]))
        facet_colors = self.env['documents.facet'].FACET_ORDER_COLORS
        for tag in tags:
            color_index = facets.index(tag['group_id']) % len(facet_colors)
            tag['group_hex_color'] = facet_colors[color_index]

        return tags

    @api.model
    def search_panel_select_multi_range(self, field_name, **kwargs):
        search_domain = kwargs.get('search_domain', [])
        category_domain = kwargs.get('category_domain', [])
        filter_domain = kwargs.get('filter_domain', [])

        if field_name == 'tag_ids':
            folder_id = category_domain[0][2] if len(category_domain) else []
            if folder_id:
                domain = expression.AND([
                    search_domain, category_domain, filter_domain,
                    [(field_name, '!=', False)],
                ])
                return self._get_processed_tags(domain, folder_id)
            else:
                return []

        elif field_name == 'res_model':
            domain = expression.AND([search_domain, category_domain])
            model_values = self._get_models(domain)

            if filter_domain:
                # fetch new counters
                domain = expression.AND([search_domain, category_domain, filter_domain])
                model_count = {
                    model['id']: model['count']
                    for model in self._get_models(domain)
                }
                # update result with new counters
                for model in model_values:
                    model['count'] = model_count.get(model['id'], 0)

            return model_values

        return super(Document, self).search_panel_select_multi_range(field_name, **kwargs)
