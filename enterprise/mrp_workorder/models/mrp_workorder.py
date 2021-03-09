# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
from odoo.tools import float_compare, float_round


class MrpProductionWorkorder(models.Model):
    _name = 'mrp.workcenter'
    _inherit = 'mrp.workcenter'

    def action_work_order(self):
        if not self.env.context.get('desktop_list_view', False):
            action = self.env.ref('mrp_workorder.mrp_workorder_action_tablet').read()[0]
            return action
        else:
            return super(MrpProductionWorkorder, self).action_work_order()


class MrpProductionWorkcenterLine(models.Model):
    _name = 'mrp.workorder'
    _inherit = ['mrp.workorder', 'barcodes.barcode_events_mixin']

    check_ids = fields.One2many('quality.check', 'workorder_id')
    skipped_check_ids = fields.One2many('quality.check', 'workorder_id', domain=[('quality_state', '=', 'none')])
    finished_product_check_ids = fields.Many2many('quality.check', compute='_compute_finished_product_check_ids')
    quality_check_todo = fields.Boolean(compute='_compute_check')
    quality_check_fail = fields.Boolean(compute='_compute_check')
    quality_alert_ids = fields.One2many('quality.alert', 'workorder_id')
    quality_alert_count = fields.Integer(compute="_compute_quality_alert_count")

    current_quality_check_id = fields.Many2one(
        'quality.check', "Current Quality Check", store=True, check_company=True)

    # QC-related fields
    allow_producing_quantity_change = fields.Boolean('Allow Changes to Producing Quantity', default=True)
    component_id = fields.Many2one('product.product', related='current_quality_check_id.component_id')
    component_tracking = fields.Selection(related='component_id.tracking', string="Is Component Tracked", readonly=False)
    component_remaining_qty = fields.Float('Remaining Quantity for Component', compute='_compute_component_data', digits='Product Unit of Measure')
    component_uom_id = fields.Many2one('uom.uom', compute='_compute_component_data', string="Component UoM")
    control_date = fields.Datetime(related='current_quality_check_id.control_date', readonly=False)
    is_first_step = fields.Boolean('Is First Step')
    is_last_step = fields.Boolean('Is Last Step')
    is_last_lot = fields.Boolean('Is Last lot', compute='_compute_is_last_lot')
    is_last_unfinished_wo = fields.Boolean('Is Last Work Order To Process', compute='_compute_is_last_unfinished_wo', store=False)
    lot_id = fields.Many2one(related='current_quality_check_id.lot_id', readonly=False)
    workorder_line_id = fields.Many2one(related='current_quality_check_id.workorder_line_id', readonly=False)
    note = fields.Html(related='current_quality_check_id.note')
    skip_completed_checks = fields.Boolean('Skip Completed Checks', readonly=True)
    quality_state = fields.Selection(related='current_quality_check_id.quality_state', string="Quality State", readonly=False)
    qty_done = fields.Float(related='current_quality_check_id.qty_done', readonly=False)
    test_type_id = fields.Many2one('quality.point.test_type', 'Test Type', related='current_quality_check_id.test_type_id')
    test_type = fields.Char(related='test_type_id.technical_name')
    user_id = fields.Many2one(related='current_quality_check_id.user_id', readonly=False)
    worksheet_page = fields.Integer('Worksheet page')
    picture = fields.Binary(related='current_quality_check_id.picture', readonly=False)
    component_qty_to_do = fields.Float(compute='_compute_component_qty_to_do')

    @api.onchange('qty_producing')
    def _onchange_qty_producing(self):
        super(MrpProductionWorkcenterLine, self)._onchange_qty_producing()
        # retrieve qty_to_consume on the workorder line updated by onchange
        workorder_line = self.current_quality_check_id.workorder_line_id
        self.qty_done = workorder_line.new(origin=workorder_line).qty_to_consume

    @api.depends('qty_done', 'component_remaining_qty')
    def _compute_component_qty_to_do(self):
        for wo in self:
            wo.component_qty_to_do = wo.qty_done - wo.component_remaining_qty

    @api.depends('qty_producing', 'qty_remaining')
    def _compute_is_last_lot(self):
        for wo in self:
            precision = wo.production_id.product_uom_id.rounding
            wo.is_last_lot = float_compare(wo.qty_producing, wo.qty_remaining, precision_rounding=precision) >= 0

    @api.depends('production_id.workorder_ids')
    def _compute_is_last_unfinished_wo(self):
        for wo in self:
            other_wos = wo.production_id.workorder_ids - wo
            other_states = other_wos.mapped(lambda w: w.state == 'done')
            wo.is_last_unfinished_wo = all(other_states)

    @api.depends('check_ids')
    def _compute_finished_product_check_ids(self):
        for wo in self:
            wo.finished_product_check_ids = wo.check_ids.filtered(lambda c: c.finished_product_sequence == wo.qty_produced)

    @api.depends('state', 'quality_state', 'current_quality_check_id', 'qty_producing',
                 'component_tracking', 'test_type', 'component_id',
                 'move_finished_ids.state', 'move_finished_ids.product_id',
                 'move_raw_ids.state', 'move_raw_ids.product_id',
                 )
    def _compute_component_data(self):
        self.component_remaining_qty = False
        self.component_uom_id = False
        for wo in self.filtered(lambda w: w.state not in ('done', 'cancel')):
            if wo.test_type in ('register_byproducts', 'register_consumed_materials') and wo.quality_state == 'none':
                move = wo.current_quality_check_id.workorder_line_id.move_id
                lines = wo._workorder_line_ids().filtered(lambda l: l.move_id == move)
                completed_lines = lines.filtered(lambda l: l.lot_id) if wo.component_id.tracking != 'none' else lines
                wo.component_remaining_qty = self._prepare_component_quantity(move, wo.qty_producing) - sum(completed_lines.mapped('qty_done'))
                wo.component_uom_id = lines[:1].product_uom_id

    def action_back(self):
        self.ensure_one()
        if self.is_user_working and self.working_state != 'blocked':
            self.button_pending()

    def action_cancel(self):
        self.mapped('check_ids').filtered(lambda c: c.quality_state == 'none').sudo().unlink()
        return super(MrpProductionWorkcenterLine, self).action_cancel()

    def action_generate_serial(self):
        self.ensure_one()
        self.finished_lot_id = self.env['stock.production.lot'].create({
            'product_id': self.product_id.id,
            'company_id': self.company_id.id,
        })

    def action_print(self):
        if self.product_id.uom_id.category_id.measure_type == 'unit':
            qty = int(self.qty_producing)
        else:
            qty = 1

        quality_point_id = self.current_quality_check_id.point_id
        report_type = quality_point_id.test_report_type

        if self.product_id.tracking == 'none':
            if report_type == 'zpl':
                xml_id = 'stock.label_barcode_product_product'
            else:
                xml_id = 'product.report_product_product_barcode'
            res = self.env.ref(xml_id).report_action([self.product_id.id] * qty)
        else:
            if self.finished_lot_id:
                if report_type == 'zpl':
                    xml_id = 'stock.label_lot_template'
                else:
                    xml_id = 'stock.action_report_lot_label'
                res = self.env.ref(xml_id).report_action([self.finished_lot_id.id] * qty)
            else:
                raise UserError(_('You did not set a lot/serial number for '
                                'the final product'))

        res['id'] = self.env.ref(xml_id).id

        # The button goes immediately to the next step
        self._next()
        return res

    def _refresh_wo_lines(self):
        res = super(MrpProductionWorkcenterLine, self)._refresh_wo_lines()
        for workorder in self:
            for check in workorder.check_ids:
                if check.quality_state == 'none' and not check.workorder_line_id and check.component_id:
                    assigned_to_check_moves = workorder.check_ids.mapped('workorder_line_id').mapped('move_id')
                    if check.test_type == 'register_consumed_materials':
                        move = workorder.move_raw_ids.filtered(lambda move: move.state not in ('done', 'cancel') and move.product_id == check.component_id and move not in assigned_to_check_moves)
                    else:
                        move = workorder.move_finished_ids.filtered(lambda move: move.state not in ('done', 'cancel') and move.product_id == check.component_id and move not in assigned_to_check_moves)
                    check.write(workorder._defaults_from_workorder_lines(move, check.test_type))
        return res

    def _create_subsequent_checks(self):
        """ When processing a step with regiter a consumed material
        that's a lot we will some times need to create a new
        intermediate check.
        e.g.: Register 2 product A tracked by SN. We will register one
        with the current checks but we need to generate a second step
        for the second SN. Same for lot if the user wants to use more
        than one lot.
        """
        # Create another quality check if necessary
        parent_id = self.current_quality_check_id
        if parent_id.parent_id:
            parent_id = parent_id.parent_id
        subsequent_substeps = self.env['quality.check'].search([('parent_id', '=', parent_id.id), ('id', '>', self.current_quality_check_id.id)])
        if not subsequent_substeps:
            # Split current workorder line.
            rounding = self.workorder_line_id.product_uom_id.rounding
            if float_compare(self.workorder_line_id.qty_done, self.workorder_line_id.qty_to_consume, precision_rounding=rounding) < 0:
                self.workorder_line_id.copy(default={'qty_done': 0, 'qty_to_consume': self.workorder_line_id.qty_to_consume - self.workorder_line_id.qty_done})
                self.workorder_line_id.write({'qty_to_consume': self.workorder_line_id.qty_done})
            # Check if it exists a workorder line not used. If it could not find
            # one, create it without prefilled values.
            elif not self._defaults_from_workorder_lines(self.workorder_line_id.move_id, self.test_type):
                moves = self.env['stock.move']
                workorder_line_values = {}
                if self.test_type == 'register_byproducts':
                    moves |= self.move_finished_ids.filtered(lambda m: m.state not in ('done', 'cancel') and m.product_id == self.component_id)
                    workorder_line_values['finished_workorder_id'] = self.id
                else:
                    moves = self.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel') and m.product_id == self.component_id)
                    workorder_line_values['raw_workorder_id'] = self.id
                workorder_line_values.update({
                    'move_id': moves[:1].id,
                    'product_id': self.component_id.id,
                    'product_uom_id': moves[:1].product_uom.id,
                    'qty_done': 0.0,
                })
                self.env['mrp.workorder.line'].create(workorder_line_values)
            # Creating quality checks
            quality_check_data = {
                'workorder_id': self.id,
                'product_id': self.product_id.id,
                'company_id': self.company_id.id,
                'parent_id': parent_id.id,
                'finished_product_sequence': self.qty_produced,
            }
            if self.current_quality_check_id.point_id:
                quality_check_data.update({
                    'point_id': self.current_quality_check_id.point_id.id,
                    'team_id': self.current_quality_check_id.point_id.team_id.id,
                })
            else:
                quality_check_data.update({
                    'component_id': self.current_quality_check_id.component_id.id,
                    'test_type_id': self.current_quality_check_id.test_type_id.id,
                    'team_id': self.current_quality_check_id.team_id.id,
                })
            move = parent_id.workorder_line_id.move_id
            quality_check_data.update(self._defaults_from_workorder_lines(move, self.current_quality_check_id.test_type))
            self.env['quality.check'].create(quality_check_data)

    def _generate_lines_values(self, move, qty_to_consume):
        """ In case of non tracked component without 'register component' step,
        we need to fill the qty_done at this step"""
        lines = super(MrpProductionWorkcenterLine, self)._generate_lines_values(move, qty_to_consume)
        steps = self._get_quality_points(lines)
        for line in lines:
            if line['product_id'] in steps.mapped('component_id.id') or move.has_tracking != 'none':
                line['qty_done'] = 0
        return lines

    def _update_workorder_lines(self):
        res = super(MrpProductionWorkcenterLine, self)._update_workorder_lines()
        if res['to_update']:
            steps = self._get_quality_points([{'product_id': record.product_id.id} for record in res['to_update'].keys()])
            for line, values in res['to_update'].items():
                if line.product_id in steps.mapped('component_id') or line.move_id.has_tracking != 'none':
                    values['qty_done'] = 0
        return res

    def _get_quality_points(self, iterator):
        steps = self.env['quality.point'].search([
            ('test_type', 'in', ('register_byproducts', 'register_consumed_materials')),
            ('component_id', 'in', [values.get('product_id', False) for values in iterator]),
            ('operation_id', 'in', self.production_id.routing_id.operation_ids.ids),
            '|',
                ('product_id', '=', self.product_id.id),
                '&',
                    ('product_id', '=', False),
                    ('product_tmpl_id', '=', self.product_id.product_tmpl_id.id),
        ])
        return steps

    def _next(self, continue_production=False):
        """ This function:
        - first: fullfill related move line with right lot and validated quantity.
        - second: Generate new quality check for remaining quantity and link them to the original check.
        - third: Pass to the next check or return a failure message.
        """
        self.ensure_one()
        rounding = self.product_uom_id.rounding
        if float_compare(self.qty_producing, 0, precision_rounding=rounding) <= 0\
                or float_compare(self.qty_producing, self.qty_remaining, precision_rounding=rounding) > 0:
            raise UserError(_('Please ensure the quantity to produce is nonnegative and does not exceed the remaining quantity.'))
        elif self.test_type in ('register_byproducts', 'register_consumed_materials'):
            # Form validation
            # in case we use continue production instead of validate button.
            # We would like to consume 0 and leave lot_id blank to close the consumption
            if self.component_tracking != 'none' and not self.lot_id and self.qty_done != 0:
                raise UserError(_('Please enter a Lot/SN.'))
            if float_compare(self.qty_done, 0, precision_rounding=rounding) < 0:
                raise UserError(_('Please enter a positive quantity.'))

            # Get the move lines associated with our component
            self.component_remaining_qty -= float_round(self.qty_done, precision_rounding=self.workorder_line_id.product_uom_id.rounding or rounding)
            # Write the lot and qty to the move line
            self.workorder_line_id.write({'lot_id': self.lot_id.id, 'qty_done': float_round(self.qty_done, precision_rounding=self.workorder_line_id.product_uom_id.rounding or rounding)})

            if continue_production:
                self._create_subsequent_checks()
            elif float_compare(self.component_remaining_qty, 0, precision_rounding=rounding) < 0 and\
                    self.consumption == 'strict':
                # '< 0' as it's not possible to click on validate if qty_done < component_remaining_qty
                raise UserError(_('You should consume the quantity of %s defined in the BoM. If you want to consume more or less components, change the consumption setting on the BoM.') % self.component_id[0].name)

        if self.test_type == 'picture' and not self.picture:
            raise UserError(_('Please upload a picture.'))

        if self.test_type not in ('measure', 'passfail'):
            self.current_quality_check_id.do_pass()

        if self.skip_completed_checks:
            self._change_quality_check(increment=1, children=1, checks=self.skipped_check_ids)
        else:
            self._change_quality_check(increment=1, children=1)

    def action_skip(self):
        self.ensure_one()
        rounding = self.product_uom_id.rounding
        if float_compare(self.qty_producing, 0, precision_rounding=rounding) <= 0 or\
                float_compare(self.qty_producing, self.qty_remaining, precision_rounding=rounding) > 0:
            raise UserError(_('Please ensure the quantity to produce is nonnegative and does not exceed the remaining quantity.'))
        if self.skip_completed_checks:
            self._change_quality_check(increment=1, children=1, checks=self.skipped_check_ids)
        else:
            self._change_quality_check(increment=1, children=1)

    def action_first_skipped_step(self):
        self.ensure_one()
        self.skip_completed_checks = True
        self._change_quality_check(position=0, children=1, checks=self.skipped_check_ids)

    def action_previous(self):
        self.ensure_one()
        self._change_quality_check(increment=-1, children=1)

    # Technical function to change the current quality check.
    #
    # params:
    #     children - boolean - Whether to account for 'children' quality checks, which are generated on-the-fly
    #     position - integer - Goes to step <position>, after reordering
    #     checks - list - If provided, consider only checks in <checks>
    #     goto - integer - Goes to quality_check with id=<goto>
    #     increment - integer - Change quality check relatively to the current one, after reordering
    def _change_quality_check(self, **params):
        self.ensure_one()
        check_id = None
        # Determine the list of checks to consider
        checks = params['checks'] if 'checks' in params else self.check_ids
        if not params.get('children'):
            checks = checks.filtered(lambda c: not c.parent_id)
        # We need to make sure the current quality check is in our list
        # when we compute position relatively to the current quality check.
        if 'increment' in params or 'checks' in params and self.current_quality_check_id not in checks:
            checks |= self.current_quality_check_id
        # Restrict to checks associated with the current production
        checks = checks.filtered(lambda c: c.finished_product_sequence == self.qty_produced)
        # As some checks are generated on the fly,
        # we need to ensure that all 'children' steps are grouped together.
        # Missing steps are added at the end.
        def sort_quality_checks(check):
            # Useful tuples to compute the order
            parent_point_sequence = (check.parent_id.point_id.sequence, check.parent_id.point_id.id)
            point_sequence = (check.point_id.sequence, check.point_id.id)
            # Parent quality checks are sorted according to the sequence number of their associated quality point,
            # with chronological order being the tie-breaker.
            if check.point_id and not check.parent_id:
                score = (0, 0) + point_sequence + (0, 0)
            # Children steps follow their parents, honouring their quality point sequence number,
            # with chronological order being the tie-breaker.
            elif check.point_id:
                score = (0, 0) + parent_point_sequence + point_sequence
            # Checks without points go at the end and are ordered chronologically
            elif not check.parent_id:
                score = (check.id, 0, 0, 0, 0, 0)
            # Children without points follow their respective parents, in chronological order
            else:
                score = (check.parent_id.id, check.id, 0, 0, 0, 0)
            return score
        ordered_check_ids = checks.sorted(key=sort_quality_checks).ids
        # We manually add a final 'Summary' step
        # which is not associated with a specific quality_check (hence the 'False' id).
        ordered_check_ids.append(False)
        # Determine the quality check we are switching to
        if 'increment' in params:
            current_id = self.current_quality_check_id.id
            position = ordered_check_ids.index(current_id)
            check_id = self.current_quality_check_id.id
            if position + params['increment'] in range(0, len(ordered_check_ids)):
                position += params['increment']
                check_id = ordered_check_ids[position]
        elif params.get('position') in range(0, len(ordered_check_ids)):
            position = params['position']
            check_id = ordered_check_ids[position]
        elif params.get('goto') in ordered_check_ids:
            check_id = params['goto']
            position = ordered_check_ids.index(check_id)
        # Change the quality check and the worksheet page if necessary
        if check_id is not None:
            next_check = self.env['quality.check'].browse(check_id)
            change_worksheet_page = position != len(ordered_check_ids) - 1 and next_check.point_id.worksheet == 'scroll'
            checks = self.check_ids.filtered(lambda c: c.finished_product_sequence == self.qty_produced)
            self.write({
                'allow_producing_quantity_change': True if params.get('position') == 0 and all(c.quality_state == 'none' for c in checks) else False,
                'current_quality_check_id': check_id,
                'is_first_step': position == 0,
                'is_last_step': check_id == False,
                'worksheet_page': next_check.point_id.worksheet_page if change_worksheet_page else self.worksheet_page,
            })

    def _defaults_from_workorder_lines(self, move, test_type):
        # Check if a workorder line is not filled for this workorder. If it
        # happens select it in order to create quality_check
        self.ensure_one()
        if test_type == 'register_byproducts':
            available_workorder_lines = self.finished_workorder_line_ids.filtered(lambda wl: not wl.qty_done and wl.move_id == move)
        else:
            available_workorder_lines = self.raw_workorder_line_ids.filtered(lambda wl: not wl.qty_done and wl.move_id == move)
        if available_workorder_lines:
            workorder_line = available_workorder_lines.sorted()[0]
            return {
                'workorder_line_id': workorder_line.id,
                'lot_id': workorder_line.lot_id.id,
                # Prefill with 1.0 if it's an extra workorder line.
                'qty_done': workorder_line.qty_to_consume or 1.0
            }
        return {}

    def action_menu(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.workorder',
            'views': [[self.env.ref('mrp_workorder.mrp_workorder_view_form_tablet_menu').id, 'form']],
            'name': _('Menu'),
            'target': 'new',
            'res_id': self.id,
        }

    def _compute_check(self):
        for workorder in self:
            todo = False
            fail = False
            for check in workorder.check_ids:
                if check.quality_state == 'none':
                    todo = True
                elif check.quality_state == 'fail':
                    fail = True
                if fail and todo:
                    break
            workorder.quality_check_fail = fail
            workorder.quality_check_todo = todo

    def _compute_quality_alert_count(self):
        for workorder in self:
            workorder.quality_alert_count = len(workorder.quality_alert_ids)

    def _create_checks(self):
        for wo in self:
            # Track components which have a control point
            processed_move = self.env['stock.move']

            production = wo.production_id
            points = self.env['quality.point'].search([('operation_id', '=', wo.operation_id.id),
                                                       ('picking_type_id', '=', production.picking_type_id.id),
                                                       ('company_id', '=', wo.company_id.id),
                                                       '|', ('product_id', '=', production.product_id.id),
                                                       '&', ('product_id', '=', False), ('product_tmpl_id', '=', production.product_id.product_tmpl_id.id)])

            move_raw_ids = wo.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
            move_finished_ids = wo.move_finished_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
            values_to_create = []
            for point in points:
                # Check if we need a quality control for this point
                if point.check_execute_now():
                    moves = self.env['stock.move']
                    values = {
                        'workorder_id': wo.id,
                        'point_id': point.id,
                        'team_id': point.team_id.id,
                        'company_id': wo.company_id.id,
                        'product_id': production.product_id.id,
                        # Two steps are from the same production
                        # if and only if the produced quantities at the time they were created are equal.
                        'finished_product_sequence': wo.qty_produced,
                    }
                    if point.test_type == 'register_byproducts':
                        moves = move_finished_ids.filtered(lambda m: m.product_id == point.component_id)
                    elif point.test_type == 'register_consumed_materials':
                        moves = move_raw_ids.filtered(lambda m: m.product_id == point.component_id)
                    else:
                        values_to_create.append(values)
                    # Create 'register ...' checks
                    for move in moves:
                        check_vals = values.copy()
                        check_vals.update(wo._defaults_from_workorder_lines(move, point.test_type))
                        values_to_create.append(check_vals)
                    processed_move |= moves

            # Generate quality checks associated with unreferenced components
            moves_without_check = ((move_raw_ids | move_finished_ids) - processed_move).filtered(lambda move: move.has_tracking != 'none')
            quality_team_id = self.env['quality.alert.team'].search([], limit=1).id
            for move in moves_without_check:
                values = {
                    'workorder_id': wo.id,
                    'product_id': production.product_id.id,
                    'company_id': wo.company_id.id,
                    'component_id': move.product_id.id,
                    'team_id': quality_team_id,
                    # Two steps are from the same production
                    # if and only if the produced quantities at the time they were created are equal.
                    'finished_product_sequence': wo.qty_produced,
                }
                if move in move_raw_ids:
                    test_type = self.env.ref('mrp_workorder.test_type_register_consumed_materials')
                if move in move_finished_ids:
                    test_type = self.env.ref('mrp_workorder.test_type_register_byproducts')
                values.update({'test_type_id': test_type.id})
                values.update(wo._defaults_from_workorder_lines(move, test_type.technical_name))
                values_to_create.append(values)

            self.env['quality.check'].create(values_to_create)
            # Set default quality_check
            wo.skip_completed_checks = False
            wo._change_quality_check(position=0)

    def _get_byproduct_move_to_update(self):
        moves = super(MrpProductionWorkcenterLine, self)._get_byproduct_move_to_update()
        return moves.filtered(lambda m: m.product_id.tracking == 'none')

    def record_production(self):
        self.ensure_one()
        if any([(x.quality_state == 'none') for x in self.check_ids]):
            raise UserError(_('You still need to do the quality checks!'))
        if (self.production_id.product_id.tracking != 'none') and not self.finished_lot_id and self.move_raw_ids:
            raise UserError(_('You should provide a lot for the final product'))
        if self.check_ids:
            # Check if you can attribute the lot to the checks
            if (self.production_id.product_id.tracking != 'none') and self.finished_lot_id:
                self.check_ids.filtered(lambda check: not check.finished_lot_id).write({
                    'finished_lot_id': self.finished_lot_id.id
                })
        res = super(MrpProductionWorkcenterLine, self).record_production()
        rounding = self.product_uom_id.rounding
        if float_compare(self.qty_producing, 0, precision_rounding=rounding) > 0:
            self._create_checks()
        return res

    # --------------------------
    # Buttons from quality.check
    # --------------------------

    def open_tablet_view(self):
        self.ensure_one()
        if not self.is_user_working and self.working_state != 'blocked' and self.state in ('ready', 'progress'):
            self.button_start()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.workorder',
            'views': [[self.env.ref('mrp_workorder.mrp_workorder_view_form_tablet').id, 'form']],
            'res_id': self.id,
            'target': 'fullscreen',
            'flags': {
                'withControlPanel': False,
                'form_view_initial_mode': 'edit',
            },
        }

    def action_next(self):
        self.ensure_one()
        return self._next()

    def action_continue(self):
        self.ensure_one()
        self._next(continue_production=True)

    def action_open_manufacturing_order(self):
        action = self.do_finish()
        try:
            self.production_id.button_mark_done()
        except (UserError, ValidationError) as e:
            # log next activity on MO with error message
            self.env['mail.activity'].create({
                'res_id': self.production_id.id,
                'res_model_id': self.env['ir.model']._get(self.production_id._name).id,
                'activity_type_id': self.env.ref('mail.mail_activity_data_warning').id,
                'summary': ('The %s could not be closed') % (self.production_id.name),
                'note': e.name,
                'user_id': self.env.user.id,
            })
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'mrp.production',
                'views': [[self.env.ref('mrp.mrp_production_form_view').id, 'form']],
                'res_id': self.production_id.id,
                'target': 'main',
            }
        return action

    def do_finish(self):
        self.record_production()
        # workorder tree view action should redirect to the same view instead of workorder kanban view when WO mark as done.
        if self.env.context.get('active_model') == self._name:
            action = self.env.ref('mrp.action_mrp_workorder_production_specific').read()[0]
            action['context'] = {'search_default_production_id': self.production_id.id}
            action['target'] = 'main'
        else:
            # workorder tablet view action should redirect to the same tablet view with same workcenter when WO mark as done.
            action = self.env.ref('mrp_workorder.mrp_workorder_action_tablet').read()[0]
            action['context'] = {
                'form_view_initial_mode': 'edit',
                'no_breadcrumbs': True,
                'search_default_workcenter_id': self.workcenter_id.id
            }
        action['domain'] = [('state', 'not in', ['done', 'cancel', 'pending'])]
        return action

    def on_barcode_scanned(self, barcode):
        # qty_done field for serial numbers is fixed
        if self.component_tracking != 'serial':
            if not self.lot_id:
                # not scanned yet
                self.qty_done = 1
            elif self.lot_id.name == barcode:
                self.qty_done += 1
            else:
                return {
                    'warning': {
                        'title': _("Warning"),
                        'message': _("You are using components from another lot. \nPlease validate the components from the first lot before using another lot.")
                    }
                }

        lot = self.env['stock.production.lot'].search([('name', '=', barcode)])

        if self.component_tracking:
            if not lot:
                # create a new lot
                # create in an onchange is necessary here ("new" cannot work here)
                lot = self.env['stock.production.lot'].with_context(active_mo_id=self.production_id.id).create({
                    'name': barcode,
                    'product_id': self.component_id.id,
                    'company_id': self.company_id.id,
                })
            self.lot_id = lot
        elif self.production_id.product_id.tracking and self.production_id.product_id.tracking != 'none':
            if not lot:
                lot = self.env['stock.production.lot'].create({
                    'name': barcode,
                    'product_id': self.product_id.id,
                    'company_id': self.company_id.id,
                })
            self.finished_lot_id = lot


class MrpWorkorderLine(models.Model):
    _inherit = 'mrp.workorder.line'

    check_ids = fields.One2many('quality.check', 'workorder_line_id', 'Associated step')

    def _unreserve_order(self):
        """ Delete or modify first the workorder line not linked to a check."""
        order = super(MrpWorkorderLine, self)._unreserve_order()
        return (self.check_ids,) + order

    def write(self, values):
        """ Using `record_production` may change the `qty_producing` on the following
        workorder if the production is not totally done, and so changing the
        `qty_to_consume` on some workorder lines.
        Using the `change.production.qty` wizard may also impact those `qty_to_consume`.
        We make this override to keep the `qty_done` field of the not yet processed
        quality checks inline with their associated workorder line `qty_to_consume`."""
        res = super(MrpWorkorderLine, self).write(values)
        if 'qty_to_consume' in values:
            for line in self:
                if line.check_ids.quality_state == 'none' and line.check_ids.qty_done != line.qty_to_consume:
                    # In case some lines are deleted or some quantities updated
                    line.check_ids.qty_done = line.qty_to_consume
        return res
