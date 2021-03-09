# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import json

from lxml import etree
from odoo import http, _
from odoo.http import request
from odoo.addons.web_studio.controllers import main
from odoo.exceptions import ValidationError, UserError


class WebStudioReportController(main.WebStudioController):

    @http.route('/web_studio/create_new_report', type='json', auth='user')
    def create_new_report(self, model_name, layout):

        if layout == 'web.basic_layout':
            arch_document = etree.fromstring("""
                <t t-name="studio_report_document">
                    <div class="page"/>
                </t>
                """)
        else:
            arch_document = etree.fromstring("""
                <t t-name="studio_report_document">
                    <t t-call="%(layout)s">
                        <div class="page"/>
                    </t>
                </t>
                """ % {'layout': layout})

        view_document = request.env['ir.ui.view'].create({
            'name': 'studio_report_document',
            'type': 'qweb',
            'arch': etree.tostring(arch_document, encoding='utf-8', pretty_print=True),
        })

        new_view_document_xml_id = view_document.get_external_id()[view_document.id]
        view_document.name = '%s_document' % new_view_document_xml_id
        view_document.key = '%s_document' % new_view_document_xml_id

        if layout == 'web.basic_layout':
            arch = etree.fromstring("""
                <t t-name="studio_main_report">
                    <t t-foreach="docs" t-as="doc">
                        <t t-call="%(layout)s">
                            <t t-call="%(document)s_document"/>
                            <p style="page-break-after: always;"/>
                        </t>
                    </t>
                </t>
            """ % {'layout': layout, 'document': new_view_document_xml_id})
        else:
            arch = etree.fromstring("""
                <t t-name="studio_main_report">
                    <t t-call="web.html_container">
                        <t t-foreach="docs" t-as="doc">
                            <t t-call="%(document)s_document"/>
                        </t>
                    </t>
                </t>
            """ % {'document': new_view_document_xml_id})

        view = request.env['ir.ui.view'].create({
            'name': 'studio_main_report',
            'type': 'qweb',
            'arch': etree.tostring(arch, encoding='utf-8', pretty_print=True),
        })
        # FIXME: When website is installed, we need to set key as xmlid to search on a valid domain
        # See '_view_obj' in 'website/model/ir.ui.view'
        view.name = new_view_document_xml_id
        view.key = new_view_document_xml_id

        model = request.env['ir.model'].search([('model', '=', model_name)])
        report = request.env['ir.actions.report'].create({
            'name': _('%s Report') % model.name,
            'model': model.model,
            'report_type': 'qweb-pdf',
            'report_name': view.name,
        })
        # make it available in the print menu
        report.create_action()

        return {
            'id': report.id,
        }

    @http.route('/web_studio/print_report', type='json', auth='user')
    def print_report(self, report_name, record_id):
        report = request.env['ir.actions.report']._get_report_from_name(report_name)
        return report.report_action(record_id)

    @http.route('/web_studio/edit_report', type='json', auth='user')
    def edit_report(self, report_id, values):
        report = request.env['ir.actions.report'].browse(report_id)
        if report:
            if 'attachment_use' in values:
                if values['attachment_use']:
                    values['attachment'] = "'%s'" % report.name
                else:
                    # disable saving as attachment altogether
                    values['attachment'] = False
            if 'groups_id' in values:
                values['groups_id'] = [(6, 0, values['groups_id'])]
            if 'display_in_print' in values:
                if values['display_in_print']:
                    report.create_action()
                else:
                    report.unlink_action()
                values.pop('display_in_print')
            report.write(values)

        return report.read()

    @http.route('/web_studio/read_paperformat', type='json', auth='user')
    def read_paperformat(self, report_id):
        report = request.env['ir.actions.report'].browse(report_id)
        return report.get_paperformat().read()

    @http.route('/web_studio/get_widgets_available_options', type='json', auth='user')
    def get_widgets_available_options(self):
        fields = dict()
        records = request.env['ir.model'].search([('model', 'like', 'ir.qweb.field.%')])
        for record in records:
            fields[record.model[14:]] = request.env[record.model].get_available_options()
        return fields

    @http.route('/web_studio/get_report_views', type='json', auth='user')
    def get_report_views(self, report_name, record_id):
        loaded = set()
        views = {}

        def get_report_view(key):
            view = request.env['ir.ui.view'].search([
                ('key', '=', key),
                ('type', '=', 'qweb'),
                ('mode', '=', 'primary'),
            ], limit=1)
            if not view:
                raise UserError(_("No view found for the given report!"))
            return view

        def process_template_groups(element):
            """ `get_template` only returns the groups names but we also need
                need their id and display name in Studio to edit them (many2many
                tags widget). These data are thus added on the node.
                This processing is quite similar to what has been done on views.
            """
            for node in element.iter():
                if node.get('groups'):
                    request.env['ir.ui.view'].set_studio_groups(node)

        def load_arch(view_name):
            if view_name in loaded:
                return
            loaded.add(view_name)

            view = get_report_view(view_name)
            studio_view = self._get_studio_view(view)
            element, document = request.env['ir.qweb'].get_template(view.id, {"full_branding": True})

            process_template_groups(element)

            views[view.id] = {
                'arch': etree.tostring(element),
                'key': view.key,
                'studio_arch': studio_view.arch_db or "<data/>",
                'studio_view_id': studio_view.id,
                'view_id': view.id,
            }

            for node in element.getroottree().findall("//*[@t-call]"):
                tcall = node.get("t-call")
                if '{' in tcall:
                    # this t-call value is dynamic (e.g. t-call="{{company.tmp}})
                    # so its corresponding view cannot be read
                    # this template won't be returned to the Editor so it won't
                    # be customizable
                    continue
                load_arch(tcall)

            return view.id

        load_arch(report_name)
        main_view_id = get_report_view(report_name).id
        report_html = self._test_report(report_name, record_id)

        return {
            'report_html': report_html and report_html[0],
            'main_view_id': main_view_id,
            'views': views,
        }

    @http.route('/web_studio/edit_report_view', type='json', auth='user')
    def edit_report_view(self, report_name, report_views, record_id, operations=None):
        # a report can be composed of multiple views (with t-call) ; we might
        # thus need to apply operations on multiple views

        # create groups of operations by view
        groups = {}
        ops = []
        for op in operations:
            ops += op.get('inheritance', [op])
        for op in ops:
            if str(op['view_id']) not in groups:
                groups[str(op['view_id'])] = []
            groups[str(op['view_id'])].append(op)

        parser = etree.XMLParser(remove_blank_text=True)
        for group_view_id in groups:
            view = request.env['ir.ui.view'].browse(int(group_view_id))
            if view.key in request.env['ir.ui.view'].TEMPLATE_VIEWS_BLACKLIST:
                raise ValidationError(_("You cannot modify this view, it is part of the generic layout"))
            arch = etree.fromstring(report_views[group_view_id]['studio_arch'], parser=parser)

            for op in groups[group_view_id]:
                if not op.get('type'):
                    # apply changes
                    content = etree.fromstring(op['content'], etree.HTMLParser())
                    for node in content[0]:
                        etree.SubElement(arch, 'xpath', {
                            'expr': op['xpath'],
                            'position': op['position'],
                        }).append(node)
                else:
                    # call the right operation handler
                    op['position'] = op['type']
                    op['target'] = {
                        'xpath_info': [{
                            'tag': g.split('[')[0],
                            'indice': g.split('[')[1][:-1] if '[' in g else 1
                        } for g in op['xpath'].split('/')[1:]]
                    }
                    getattr(self, '_operation_%s' % (op['type']))(arch, op)

            # Save or create changes into studio view, identifiable by xmlid
            # Example for view id 42 of model crm.lead: web-studio_crm.lead-42
            new_arch = etree.tostring(arch, encoding='unicode', pretty_print=True)
            self._set_studio_view(view, new_arch)

            # Normalize the view
            # studio_view = self._get_studio_view(view)
            # try:
            #     normalized_view = studio_view.normalize()
            #     self._set_studio_view(view, normalized_view)
            # except ValidationError:  # Element '<...>' cannot be located in parent view
            #     # If the studio view is not applicable after normalization, let's
            #     # just ignore the normalization step, it's better to have a studio
            #     # view that is not optimized than to prevent the user from making
            #     # the change he would like to make.
            #     self._set_studio_view(view, new_arch)

        # in case of undo, there could be no operation anymore for a view so
        # the view thus need to be reset
        intact_view_ids = report_views.keys() - groups.keys()
        for view_id in intact_view_ids:
            intact_view = request.env['ir.ui.view'].browse(int(view_id))
            studio_view = self._get_studio_view(intact_view)
            if studio_view:
                studio_view.arch_db = report_views[view_id]['studio_arch']

        result = self.get_report_views(report_name, record_id)

        return result

    @http.route('/web_studio/edit_report_view_arch', type='json', auth='user')
    def edit_report_view_arch(self, report_name, record_id, view_id, view_arch):
        view = request.env['ir.ui.view'].browse(view_id)
        view.write({'arch': view_arch})
        # TODO: we might need to keep studio_arch as it was before the changes
        result = self.get_report_views(report_name, record_id)
        return result

    @http.route('/web_studio/edit_report/test_load_assets', type='json', auth='user')
    def edit_report_test_load_css(self):
        Qweb = request.env['ir.qweb']
        Attachment = request.env['ir.attachment']

        html = Qweb.render('web.report_layout', values={
            'studio': True,
        })
        root = etree.fromstring(html).getroottree()
        links = [link.get('href') for link in root.findall("//link")]
        link_ids = [int(link.replace('/web/content/', '').split('-', 1)[0]) for link in links]
        css = {a.name: base64.b64decode(a.datas) for a in Attachment.browse(link_ids)}

        return {
            "css": css
        }

    def _test_report(self, report_name, record_id):
        # render the report to catch a rendering error
        report = request.env['ir.actions.report']._get_report_from_name(report_name)
        try:
            return report.render_qweb_html([record_id], {
                'full_branding': True,
                'studio': True,
            })
        except Exception as err:
            # the report could not be rendered which probably means the last
            # operation was incorrect
            return [{
                "error": err,
                "message": str(err),
            }]
