# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    version = fields.Integer('Version', default=1)
    previous_bom_id = fields.Many2one('mrp.bom', 'Previous BoM')
    active = fields.Boolean('Production Ready')
    image_128 = fields.Image(related='product_tmpl_id.image_128', readonly=False)
    eco_ids = fields.One2many(
        'mrp.eco', 'new_bom_id', 'ECO to be applied')
    eco_count = fields.Integer('# ECOs', compute='_compute_eco_data')
    eco_inprogress_count = fields.Integer("# ECOs in progress", compute='_compute_eco_data')
    revision_ids = fields.Many2many('mrp.bom', compute='_compute_revision_ids')

    def _compute_eco_data(self):
        eco_inprogress_data = self.env['mrp.eco'].read_group([
            ('product_tmpl_id', 'in', self.mapped('product_tmpl_id').ids),
            ('state', '=', 'progress')],
            ['product_tmpl_id'], ['product_tmpl_id'])
        eco_data = self.env['mrp.eco'].read_group([
            ('bom_id', 'in', self.ids),
            ('stage_id.folded', '=', False)],
            ['bom_id'], ['bom_id'])
        result_inprogress = dict((data['product_tmpl_id'][0], data['product_tmpl_id_count']) for data in eco_inprogress_data)
        result = dict((data['bom_id'][0], data['bom_id_count']) for data in eco_data)
        for bom in self:
            bom.eco_count = result.get(bom.id, 0)
            bom.eco_inprogress_count = result_inprogress.get(bom.product_tmpl_id.id, 0)

    def _compute_revision_ids(self):
        for rec in self:
            previous_boms = self.env['mrp.bom']
            current = self
            while current.previous_bom_id:
                previous_boms |= current
                current = current.previous_bom_id
            rec.revision_ids = previous_boms.ids

    def apply_new_version(self):
        """ Put old BoM as deprecated - TODO: Set to stage that is production_ready """
        MrpEco = self.env['mrp.eco']
        for new_bom in self:
            new_bom.write({'active': True})
            # Move eco's into rebase state which is in progress state.
            ecos = MrpEco.search(['|',
                    ('bom_id', '=', new_bom.previous_bom_id.id),
                    ('current_bom_id', '=', new_bom.previous_bom_id.id),
                    ('new_bom_id', '!=', False),
                    ('new_bom_id', '!=', new_bom.id),
                    ('state', 'not in', ('done', 'new'))])
            ecos.write({'state': 'rebase', 'current_bom_id': new_bom.id})
            # Change old bom of eco which is in draft state.
            draft_ecos = MrpEco.search(['|',
                ('bom_id', '=', new_bom.previous_bom_id.id),
                ('current_bom_id', '=', new_bom.previous_bom_id.id),
                ('new_bom_id', '=', False)])
            draft_ecos.write({'bom_id': new_bom.id})
            # Deactivate previous revision of BoM
            new_bom.previous_bom_id.write({'active': False})
        return True

    def button_mrp_eco(self):
        self.ensure_one()
        action = self.env.ref('mrp_plm.mrp_eco_action_main').read()[0]
        action['domain'] = [('bom_id', '=', self.id)]
        action['context'] = {
            'default_bom_id': self.id,
            'default_product_tmpl_id': self.product_tmpl_id.id,
            'default_type': 'bom'
        }
        return action


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    def _prepare_rebase_line(self, eco, change_type, product_id, uom_id, operation_id=None, new_qty=0):
        self.ensure_one()
        return {
            'change_type': change_type,
            'product_id': product_id,
            'rebase_id': eco.id,
            'old_uom_id': self.product_uom_id.id,
            'new_uom_id': uom_id,
            'old_operation_id': self.operation_id.id,
            'new_operation_id': operation_id,
            'old_product_qty': 0.0 if change_type == 'add' else self.product_qty,
            'new_product_qty': new_qty,
            }

    def _create_or_update_rebase_line(self, ecos, operation, product_id, uom_id, operation_id=None, new_qty=0):
        self.ensure_one()
        BomChange = self.env['mrp.eco.bom.change']
        for eco in ecos:
            # When product exist in new bill of material update line otherwise add line in rebase changes.
            rebase_line = BomChange.search([
                ('product_id', '=', product_id),
                ('rebase_id', '=', eco.id)], limit=1)
            if rebase_line:
                # Update existing rebase line or unlink it.
                if (rebase_line.old_product_qty, rebase_line.old_uom_id.id, rebase_line.old_operation_id.id) != (new_qty, uom_id, operation_id):
                    if rebase_line.change_type == 'update':
                        rebase_line.write({'new_product_qty': new_qty, 'new_operation_id': operation_id, 'new_uom_id': uom_id})
                    else:
                        rebase_line_vals = self._prepare_rebase_line(eco, 'add', product_id, uom_id, operation_id, new_qty)
                        rebase_line.write(rebase_line_vals)
                else:
                    rebase_line.unlink()
            else:
                rebase_line_vals = self._prepare_rebase_line(eco, operation, product_id, uom_id, operation_id, new_qty)
                BomChange.create(rebase_line_vals)
            eco.state = 'rebase' if eco.bom_rebase_ids or eco.previous_change_ids else 'progress'
        return True

    def bom_line_change(self, vals, operation='update'):
        MrpEco = self.env['mrp.eco']
        for line in self:
            ecos = MrpEco.search([
                ('bom_id', '=', line.bom_id.id), ('state', 'in', ('progress', 'rebase')),
                ('type', 'in', ('bom', 'both'))
            ])
            if ecos:
                # Latest bom line (product, uom, operation_id, product_qty)
                product_id = vals.get('product_id', line.product_id.id)
                uom_id = vals.get('product_uom_id', line.product_uom_id.id)
                operation_id = vals.get('operation_id', line.operation_id.id)
                product_qty = vals.get('product_qty', line.product_qty)
                line._create_or_update_rebase_line(ecos, operation, product_id, uom_id, operation_id, product_qty)
        return True

    @api.model
    def create(self, vals):
        res = super(MrpBomLine, self).create(vals)
        res.bom_line_change(vals, operation='add')
        return res

    def write(self, vals):
        operation = 'update'
        if vals.get('product_id'):
            # It will create update rebase line with negative quantity.
            self.bom_line_change({'product_qty': 0.0}, operation)
            operation = 'add'
        self.bom_line_change(vals, operation)
        return super(MrpBomLine, self).write(vals)

    def unlink(self):
        # It will create update rebase line.
        self.bom_line_change({'product_qty': 0.0})
        return super(MrpBomLine, self).unlink()
