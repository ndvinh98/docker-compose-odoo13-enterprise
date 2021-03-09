# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api


class WorkflowActionRule(models.Model):
    _name = "documents.workflow.rule"
    _description = "A set of condition and actions which will be available to all attachments matching the conditions"

    domain_folder_id = fields.Many2one('documents.folder', string="Workspace", required=True, ondelete='cascade')
    name = fields.Char(required=True, string="Rule name", translate=True)
    note = fields.Char(string="Tooltip")
    sequence = fields.Integer('Sequence', default=10)

    # Conditions
    condition_type = fields.Selection([
        ('criteria', "Criteria"),
        ('domain', "Domain"),
    ], default='criteria', string="Condition type")

    # Domain
    domain = fields.Char()

    # Criteria
    criteria_partner_id = fields.Many2one('res.partner', string="Contact")
    criteria_owner_id = fields.Many2one('res.users', string="Owner")
    required_tag_ids = fields.Many2many('documents.tag', 'required_tag_ids_rule_table', string="Required Tags")
    excluded_tag_ids = fields.Many2many('documents.tag', 'excluded_tag_ids_rule_table', string="Excluded Tags")
    limited_to_single_record = fields.Boolean(string="One record limit", compute='_compute_limited_to_single_record')

    # Actions
    partner_id = fields.Many2one('res.partner', string="Set Contact")
    user_id = fields.Many2one('res.users', string="Set Owner")
    tag_action_ids = fields.One2many('documents.workflow.action', 'workflow_rule_id', string='Set Tags')
    folder_id = fields.Many2one('documents.folder', string="Move to Workspace")
    has_business_option = fields.Boolean(compute='_get_business')
    create_model = fields.Selection([], string="Create")

    # Activity
    remove_activities = fields.Boolean(string='Mark all as Done')
    activity_option = fields.Boolean(string='Schedule Activity')
    activity_type_id = fields.Many2one('mail.activity.type', string="Activity type")
    activity_summary = fields.Char('Summary')
    activity_date_deadline_range = fields.Integer(string='Due Date In')
    activity_date_deadline_range_type = fields.Selection([
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months'),
    ], string='Due type', default='days')
    activity_note = fields.Html(string="Activity Note")
    activity_user_id = fields.Many2one('res.users', string='Responsible')

    @api.onchange('domain_folder_id')
    def _on_domain_folder_id_change(self):
        if self.domain_folder_id != self.required_tag_ids.mapped('folder_id'):
            self.required_tag_ids = False
        if self.domain_folder_id != self.excluded_tag_ids.mapped('folder_id'):
            self.excluded_tag_ids = False

    def _get_business(self):
        """
        Checks if the workflow rule has available create models to display the option.
        Implemented by the bridge models if the rule should only be available for a single record.
        """
        for record in self:
            record.has_business_option = len(self._fields['create_model'].selection)

    def _compute_limited_to_single_record(self):
        """
        Overwritten by bridge modules to define whether the rule is only available for one record at a time.
        """
        self.update({'limited_to_single_record': False})

    def create_record(self, documents=None):
        """
        implemented by each link module to define specific fields for the new business model (create_values)

        When creating/copying/writing an ir.attachment with a res_model and a res_id, add no_document=True
        to the context to prevent the automatic creation of a document.

        :param documents: the list of the documents of the selection
        :return: the action dictionary that will be called after the workflow action is done or True.
        """

        return True

    def apply_actions(self, document_ids):
        """
        called by the front-end Document Inspector to apply the actions to the selection of ID's.

        :param document_ids: the list of documents to apply the action.
        :return: if the action was to create a new business object, returns an action to open the view of the
                newly created object, else returns True.
        """
        documents = self.env['documents.document'].browse(document_ids)

        # partner/owner/share_link/folder changes
        document_dict = {}
        if self.user_id:
            document_dict['owner_id'] = self.user_id.id
        if self.partner_id:
            document_dict['partner_id'] = self.partner_id.id
        if self.folder_id:
            document_dict['folder_id'] = self.folder_id.id

        documents.write(document_dict)

        for document in documents:
            if self.remove_activities:
                document.activity_ids.action_feedback(
                    feedback="completed by rule: %s. %s" % (self.name, self.note or '')
                )

            # tag and facet actions
            for tag_action in self.tag_action_ids:
                tag_action.execute_tag_action(document)

        if self.activity_option and self.activity_type_id:
            documents.documents_set_activity(settings_record=self)

        if self.create_model:
            return self.create_record(documents=documents)

        return True


class WorkflowTagAction(models.Model):
    _name = "documents.workflow.action"
    _description = "Document Workflow Tag Action"

    workflow_rule_id = fields.Many2one('documents.workflow.rule', ondelete='cascade')

    action = fields.Selection([
        ('add', "Add"),
        ('replace', "Replace by"),
        ('remove', "Remove"),
    ], default='add', required=True)

    facet_id = fields.Many2one('documents.facet', string="Category")
    tag_id = fields.Many2one('documents.tag', string="Tag")

    def execute_tag_action(self, document):
        if self.action == 'add' and self.tag_id.id:
            return document.write({'tag_ids': [(4, self.tag_id.id, False)]})
        elif self.action == 'replace' and self.facet_id.id:
            faceted_tags = self.env['documents.tag'].search([('facet_id', '=', self.facet_id.id)])
            if faceted_tags.ids:
                for tag in faceted_tags:
                    document.write({'tag_ids': [(3, tag.id, False)]})
            return document.write({'tag_ids': [(4, self.tag_id.id, False)]})
        elif self.action == 'remove':
            if self.tag_id.id:
                return document.write({'tag_ids': [(3, self.tag_id.id, False)]})
            elif self.facet_id:
                faceted_tags = self.env['documents.tag'].search([('facet_id', '=', self.facet_id.id)])
                for tag in faceted_tags:
                    return document.write({'tag_ids': [(3, tag.id, False)]})
