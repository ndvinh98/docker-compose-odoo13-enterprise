# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
from lxml import etree
import json
from textwrap import dedent

from odoo.addons.base.models.qweb import QWeb
from odoo import models

class IrQWeb(models.AbstractModel, QWeb):
    """
    allows to render reports with full branding on every node, including the context available
    to evaluate every node. The context is composed of all the variables available at this point
    in the report, and their type.
    """
    _inherit = 'ir.qweb'

    def get_template(self, template, options):
        element, document = super(IrQWeb, self).get_template(template, options)
        if options.get('full_branding'):
            view_id = self.env['ir.ui.view']._view_obj(template).id
            if not view_id:
                raise ValueError("Template '%s' undefined" % template)

            root = element.getroottree()
            basepath = len('/'.join(root.getpath(root.xpath('//*[@t-name]')[0]).split('/')[0:-1]))
            for node in element.iter(tag=etree.Element):
                node.set('data-oe-id', str(view_id))
                node.set('data-oe-xpath', root.getpath(node)[basepath:])
        return (element, document)

    def _get_template_cache_keys(self):
        keys = super(IrQWeb, self)._get_template_cache_keys()
        keys.append('full_branding')
        return keys

    def render(self, template, values=None, **options):
        if values is None:
            values = {}
        values['json'] = json
        return super(IrQWeb, self).render(template, values=values, **options)

    def _is_static_node(self, el, options):
        return not options.get('full_branding') and super(IrQWeb, self)._is_static_node(el, options)

    def _compile_all_attributes(self, el, options, attr_already_created=False):
        body = []
        if options.get('full_branding'):
            attr_already_created = True

            body = [
                # t_attrs = OrderedDict()
                ast.Assign(
                    targets=[ast.Name(id='t_attrs', ctx=ast.Store())],
                    value=ast.Call(
                        func=ast.Name(id='OrderedDict', ctx=ast.Load()),
                        args=[],
                        keywords=[], starargs=None, kwargs=None
                    )
                ),
            ] + ast.parse(dedent("""
                t_attrs['data-oe-context'] = values['json'].dumps({
                    key: type(values[key]).__name__
                    for key in values.keys()
                    if  key
                        and key != 'true'
                        and key != 'false'
                        and not key.startswith('_')
                        and ('_' not in key or key.rsplit('_', 1)[0] not in values or key.rsplit('_', 1)[1] not in ['even', 'first', 'index', 'last', 'odd', 'parity', 'size', 'value'])
                        and (type(values[key]).__name__ not in ['LocalProxy', 'function', 'method', 'Environment', 'module', 'type'])
                })
                """)).body

        return body + super(IrQWeb, self)._compile_all_attributes(el, options, attr_already_created=attr_already_created)
