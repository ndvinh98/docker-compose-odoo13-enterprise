# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.osv import expression


class TagsCategories(models.Model):
    _name = "documents.facet"
    _description = "Category"
    _order = "sequence, name"

    # the colors to be used to represent the display order of the facets (tag categories), the colors
    # depend on the order and amount of fetched categories
    # currently used in the searchPanel and the kanban view and should match across the two.
    FACET_ORDER_COLORS = ['#F06050', '#6CC1ED', '#F7CD1F', '#814968', '#30C381', '#D6145F', '#475577', '#F4A460',
                          '#EB7E7F', '#2C8397']

    folder_id = fields.Many2one('documents.folder', string="Workspace", ondelete="cascade")
    name = fields.Char(required=True, translate=True)
    tag_ids = fields.One2many('documents.tag', 'facet_id')
    tooltip = fields.Char(help="Text shown when hovering on this tag category or its tags", string="Tooltip")
    sequence = fields.Integer('Sequence', default=10)

    _sql_constraints = [
        ('name_unique', 'unique (folder_id, name)', "Facet already exists in this folder"),
    ]


class Tags(models.Model):
    _name = "documents.tag"
    _description = "Tag"
    _order = "sequence, name"

    folder_id = fields.Many2one('documents.folder', string="Workspace", related='facet_id.folder_id', store=True,
                                readonly=False)
    facet_id = fields.Many2one('documents.facet', string="Category", ondelete='cascade', required=True)
    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer('Sequence', default=10)

    _sql_constraints = [
        ('facet_name_unique', 'unique (facet_id, name)', "Tag already exists for this facet"),
    ]

    def name_get(self):
        names = []
        if self._context.get('simple_name'):
            return super(Tags, self).name_get()
        for record in self:
            names.append((record.id, "%s > %s" % (record.facet_id.name, record.name)))
        return names

    @api.model
    def _get_tags(self, domain, folder_id):
        """
        fetches the tag and facet ids for the document selector (custom left sidebar of the kanban view)
        """
        documents = self.env['documents.document'].search(domain)
        # folders are searched with sudo() so we fetch the tags and facets from all the folder hierarchy (as tags
        # and facets are inherited from ancestor folders).
        folders = self.env['documents.folder'].sudo().search([('parent_folder_id', 'parent_of', folder_id)])
        self.flush(['sequence', 'name', 'facet_id'])
        self.env['documents.facet'].flush(['sequence', 'name', 'tooltip'])
        query = """
            SELECT  facet.sequence AS group_sequence,
                    facet.id AS group_id,
                    facet.tooltip AS group_tooltip,
                    documents_tag.sequence AS sequence,
                    documents_tag.id AS id,
                    COUNT(rel.documents_document_id) AS count
            FROM documents_tag
                JOIN documents_facet facet ON documents_tag.facet_id = facet.id
                    AND facet.folder_id = ANY(%s)
                LEFT JOIN document_tag_rel rel ON documents_tag.id = rel.documents_tag_id
                    AND rel.documents_document_id = ANY(%s)
            GROUP BY facet.sequence, facet.name, facet.id, facet.tooltip, documents_tag.sequence, documents_tag.name, documents_tag.id
            ORDER BY facet.sequence, facet.name, facet.id, facet.tooltip, documents_tag.sequence, documents_tag.name, documents_tag.id
        """
        params = [
            list(folders.ids),
            list(documents.ids),  # using Postgresql's ANY() with a list to prevent empty list of documents
        ]
        self.env.cr.execute(query, params)
        result = self.env.cr.dictfetchall()

        # Translating result
        groups = self.env['documents.facet'].browse({r['group_id'] for r in result})
        group_names = {group['id']: group['name'] for group in groups}

        tags = self.env['documents.tag'].browse({r['id'] for r in result})
        tags_names = {tag['id']: tag['name'] for tag in tags}

        for r in result:
            r['group_name'] = group_names.get(r['group_id'])
            r['name'] = tags_names.get(r['id'])

        return result
