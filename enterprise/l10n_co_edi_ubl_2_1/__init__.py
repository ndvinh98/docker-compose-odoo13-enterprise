# -*- coding: utf-8 -*-
from . import models
from . import wizard

from odoo import api, SUPERUSER_ID


def _setup_tax_type(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    chart_template = env.ref('l10n_co.l10n_co_chart_template_generic', raise_if_not_found=False)
    if chart_template:
        companies = env['res.company'].search([('chart_template_id', '=', chart_template.id)])
        tax_templates = env['account.tax.template'].search([('chart_template_id', '=', chart_template.id), ('type_tax_use', '=', 'sale'), ('l10n_co_edi_type', '!=', False)])
        xml_ids = tax_templates.get_external_id()
        for company in companies:
            for tax_template in tax_templates:
                module, xml_id = xml_ids.get(tax_template.id).split('.')
                tax = env.ref('%s.%s_%s' % (module, company.id, xml_id), raise_if_not_found=False)
                if tax:
                    tax.l10n_co_edi_type = tax_template.l10n_co_edi_type
