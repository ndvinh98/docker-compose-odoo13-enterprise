# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.osv import expression


class IrActionsReport(models.Model):
    _name = 'ir.actions.report'
    _inherit = ['studio.mixin', 'ir.actions.report']

    @api.model
    def render_qweb_html(self, docids, data=None):
        if data and data.get('full_branding'):
            self = self.with_context(full_branding=True)
        if data and data.get('studio') and self.report_type == 'qweb-pdf':
            data['report_type'] = 'pdf'
        return super(IrActionsReport, self).render_qweb_html(docids, data)

    def copy_report_and_template(self):
        new = self.copy()
        view = self.env['ir.ui.view'].search([
            ('type', '=', 'qweb'),
            ('key', '=', new.report_name),
        ], limit=1)
        view.ensure_one()
        new_view = view.with_context(lang=None).copy_qweb_template()
        copy_no = int(new_view.key.split('_copy_').pop())

        new.write({
            'xml_id': '%s_copy_%s' % (new.xml_id, copy_no),
            'name': '%s copy(%s)' % (new.name, copy_no),
            'report_name': '%s_copy_%s' % (new.report_name, copy_no),
            'report_file': new_view.key,  # TODO: are we sure about this?
        })

    @api.model
    def _get_rendering_context_model(self):
        # If the report is a copy of another report, and this report is using a custom model to render its html,
        # we must use the custom model of the original report.
        report_model_name = 'report.%s' % self.report_name
        report_model = self.env.get(report_model_name)

        if report_model is None:
            parts = report_model_name.split('_copy_')
            if not all(part.isdecimal() for part in parts[1:]):
                return report_model
            report_model_name = parts[0]
            report_model = self.env.get(report_model_name)

        return report_model

    def associated_view(self):
        action_data = super(IrActionsReport, self).associated_view()
        domain = expression.normalize_domain(action_data['domain'])

        view_name = self.report_name.split('.')[1].split('_copy_')[0]

        domain = expression.OR([
            domain,
            ['&', ('name', 'ilike', view_name), ('type', '=', 'qweb')]
        ])

        action_data['domain'] = domain
        return action_data
