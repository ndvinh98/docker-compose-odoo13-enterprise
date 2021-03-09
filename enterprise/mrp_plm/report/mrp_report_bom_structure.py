# -*- coding: utf-8 -*-

from odoo import models


class ReportBomStructure(models.AbstractModel):
    _inherit = 'report.mrp.report_bom_structure'

    def _get_bom(self, bom_id=False, product_id=False, line_qty=False, line_id=False, level=False):
        res = super(ReportBomStructure, self)._get_bom(bom_id, product_id, line_qty, line_id, level)
        res['version'] = res['bom'] and res['bom'].version or ''
        res['ecos'] = self.env['mrp.eco'].search_count([('product_tmpl_id', '=', res['product'].product_tmpl_id.id), ('state', '!=', 'done')]) or ''
        return res

    def _add_version_and_ecos(self, components):
        for line in components:
            prod_id = line.get('prod_id')
            child_bom = line.get('child_bom')
            ecos = version = False
            if prod_id:
                prod_id = self.env['product.product'].browse(prod_id)
                ecos = self.env['mrp.eco'].search_count([('product_tmpl_id', '=', prod_id.product_tmpl_id.id), ('state', '!=', 'done')]) or ''
            if child_bom:
                child_bom = self.env['mrp.bom'].browse(child_bom)
                version = child_bom and child_bom.version or ''
            line['ecos'] = ecos
            line['version'] = version
        return True

    def _get_bom_lines(self, bom, bom_quantity, product, line_id, level):
        components, total = super(ReportBomStructure, self)._get_bom_lines(bom, bom_quantity, product, line_id, level)
        self._add_version_and_ecos(components)
        return components, total

    def _get_pdf_line(self, bom_id, product_id=False, qty=1, child_bom_ids=[], unfolded=False):
        data = super(ReportBomStructure, self)._get_pdf_line(bom_id, product_id, qty, child_bom_ids, unfolded)
        self._add_version_and_ecos(data['lines'])
        return data
