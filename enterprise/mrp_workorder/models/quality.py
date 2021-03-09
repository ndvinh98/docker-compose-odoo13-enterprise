# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class TestType(models.Model):
    _inherit = "quality.point.test_type"

    allow_registration = fields.Boolean(search='_get_domain_from_allow_registration',
            store=False, default=False)

    def _get_domain_from_allow_registration(self, operator, value):
        if value:
            return []
        else:
            return [('technical_name', 'not in', ['register_byproducts', 'register_consumed_materials', 'print_label'])]


class MrpRouting(models.Model):
    _inherit = "mrp.routing"

    def action_mrp_workorder_show_steps(self):
        self.ensure_one()
        picking_type_id = self.env['stock.picking.type'].search([('code', '=', 'mrp_operation')], limit=1).id
        action = self.env.ref('mrp_workorder.action_mrp_workorder_show_steps').read()[0]
        ctx = dict(self._context, default_picking_type_id=picking_type_id, default_company_id=self.company_id.id)
        action.update({'context': ctx})
        return action

class QualityPoint(models.Model):
    _inherit = "quality.point"

    code = fields.Selection(related='picking_type_id.code', readonly=False)  # TDE FIXME: necessary ?
    operation_id = fields.Many2one(
        'mrp.routing.workcenter', 'Step', check_company=True)
    routing_id = fields.Many2one(related='operation_id.routing_id', readonly=False)
    test_type_id = fields.Many2one(
        'quality.point.test_type',
        domain="[('allow_registration', '=', operation_id and code == 'mrp_operation')]")
    test_report_type = fields.Selection([('pdf', 'PDF'), ('zpl', 'ZPL')], string="Report Type", default="pdf", required=True)
    worksheet = fields.Selection([
        ('noupdate', 'Do not update page'),
        ('scroll', 'Scroll to specific page')], string="Worksheet",
        default="noupdate")
    worksheet_page = fields.Integer('Worksheet Page')
    # Used with type register_consumed_materials the product raw to encode.
    component_id = fields.Many2one('product.product', 'Product To Register', check_company=True)

    @api.onchange('product_tmpl_id')
    def onchange_product_tmpl_id(self):
        if self.picking_type_id.code != 'mrp_operation':
            return super().onchange_product_tmpl_id()

    @api.onchange('product_id', 'product_tmpl_id', 'picking_type_id', 'test_type_id')
    def _onchange_product(self):
        bom_ids = self.env['mrp.bom'].search([('product_tmpl_id', '=', self.product_tmpl_id.id)])
        component_ids = set([])
        if self.test_type == 'register_consumed_materials':
            for bom in bom_ids:
                boms_done, lines_done = bom.explode(self.product_id, 1.0)
                component_ids |= {l[0].product_id.id for l in lines_done}
        if self.test_type == 'register_byproducts':
            for bom in bom_ids:
                component_ids |= {byproduct.product_id.id for byproduct in bom.byproduct_ids}
        routing_ids = bom_ids.mapped('routing_id.id')
        if self.picking_type_id.code == 'mrp_operation':
            return {
                'domain': {
                    'operation_id': [('routing_id', 'in', routing_ids), '|', ('company_id', '=', self.company_id.id), ('company_id', '=', False)],
                    'component_id': [('id', 'in', list(component_ids)), '|', ('company_id', '=', self.company_id.id), ('company_id', '=', False)],
                    'product_tmpl_id': [('bom_ids', '!=', False), ('bom_ids.routing_id', '!=', False), '|', ('company_id', '=', self.company_id.id), ('company_id', '=', False)],
                    'product_id': [('variant_bom_ids', '!=', False), ('variant_bom_ids.routing_id', '!=', False), '|', ('company_id', '=', self.company_id.id), ('company_id', '=', False)],
                }
            }


class QualityAlert(models.Model):
    _inherit = "quality.alert"

    workorder_id = fields.Many2one('mrp.workorder', 'Operation', check_company=True)
    workcenter_id = fields.Many2one('mrp.workcenter', 'Work Center', check_company=True)
    production_id = fields.Many2one('mrp.production', "Production Order", check_company=True)

class QualityCheck(models.Model):
    _inherit = "quality.check"

    workorder_id = fields.Many2one(
        'mrp.workorder', 'Operation', check_company=True)
    workcenter_id = fields.Many2one('mrp.workcenter', related='workorder_id.workcenter_id', store=True, readonly=True)  # TDE: necessary ?
    production_id = fields.Many2one(
        'mrp.production', 'Production Order', check_company=True)

    # For components registration
    parent_id = fields.Many2one(
        'quality.check', 'Parent Quality Check', check_company=True)
    component_id = fields.Many2one(
        'product.product', 'Component', check_company=True)
    component_uom_id = fields.Many2one('uom.uom', compute='_compute_component_uom', readonly=True)
    workorder_line_id = fields.Many2one(
        'mrp.workorder.line', 'Workorder Line', check_company=True)
    qty_done = fields.Float('Done', default=1.0, digits='Product Unit of Measure')
    finished_lot_id = fields.Many2one(
        'stock.production.lot', 'Finished Product Lot',
        domain="[('product_id', '=', product_id), ('company_id', '=', company_id)]")

    # Computed fields
    title = fields.Char('Title', compute='_compute_title')
    result = fields.Char('Result', compute='_compute_result')
    quality_state_for_summary = fields.Char('Status Summary', compute='_compute_result')

    # Used to group the steps belonging to the same production
    # We use a float because it is actually filled in by the produced quantity at the step creation.
    finished_product_sequence = fields.Float('Finished Product Sequence Number')

    @api.model_create_multi
    def create(self, values):
        points = self.env['quality.point'].search([
            ('id', 'in', [value.get('point_id') for value in values]),
            ('component_id', '!=', False)
        ])
        for value in values:
            if not value.get('component_id') and value.get('point_id'):
                point = points.filtered(lambda p: p.id == value.get('point_id'))
                if point:
                    value['component_id'] = point.component_id.id
        return super(QualityCheck, self).create(values)

    @api.depends('component_id', 'workorder_id')
    def _compute_component_uom(self):
        for check in self:
            move = check.workorder_id.move_raw_ids.filtered(lambda move: move.product_id == check.component_id)
            check.component_uom_id = move.product_uom

    def _compute_title(self):
        for check in self:
            if check.point_id:
                check.title = check.point_id.title
            else:
                check.title = '{} "{}"'.format(check.test_type_id.display_name, check.component_id.name)

    @api.depends('point_id', 'quality_state', 'component_id', 'component_uom_id', 'lot_id', 'qty_done')
    def _compute_result(self):
        for check in self:
            state = check.quality_state
            check.quality_state_for_summary = _('Done') if state != 'none' else _('To Do')
            if check.quality_state == 'none':
                check.result = ''
            else:
                check.result = check._get_check_result()

    def _get_check_result(self):
        if self.test_type in ('register_consumed_materials', 'register_byproducts') and self.lot_id:
            return '{} - {}, {} {}'.format(self.component_id.name, self.lot_id.name, self.qty_done, self.component_uom_id.name)
        elif self.test_type in ('register_consumed_materials', 'register_byproducts') and self.qty_done > 0:
            return '{}, {} {}'.format(self.component_id.name, self.qty_done, self.component_uom_id.name)
        else:
            return ''
