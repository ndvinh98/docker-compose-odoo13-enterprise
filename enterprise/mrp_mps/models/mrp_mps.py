# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict, namedtuple
from math import log10

from odoo import api, fields, models, _
from odoo.tools.date_utils import add, subtract
from odoo.tools.float_utils import float_round
from odoo.osv.expression import OR, AND
from collections import OrderedDict


class MrpProductionSchedule(models.Model):
    _name = 'mrp.production.schedule'
    _order = 'warehouse_id, sequence'
    _description = 'Schedule the production of Product in a warehouse'

    @api.model
    def _default_warehouse_id(self):
        return self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)

    forecast_ids = fields.One2many('mrp.product.forecast', 'production_schedule_id',
        'Forecasted quantity at date')
    company_id = fields.Many2one('res.company', 'Company',
        default=lambda self: self.env.company)
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_tmpl_id = fields.Many2one('product.template', related="product_id.product_tmpl_id", readonly=True)
    product_uom_id = fields.Many2one('uom.uom', string='Product UoM',
        related='product_id.uom_id')
    sequence = fields.Integer(related='product_id.sequence', store=True)
    warehouse_id = fields.Many2one('stock.warehouse', 'Production Warehouse',
        required=True, default=lambda self: self._default_warehouse_id())

    forecast_target_qty = fields.Float('Safety Stock Target')
    min_to_replenish_qty = fields.Float('Minimum to Replenish')
    max_to_replenish_qty = fields.Float('Maximum to Replenish', default=1000)

    _sql_constraints = [
        ('warehouse_product_ref_uniq', 'unique (warehouse_id, product_id)', 'The combination of warehouse and product must be unique !'),
    ]

    def action_open_actual_demand_details(self, date_str, date_start, date_stop):
        """ Open the picking list view for the actual demand for the current
        schedule.

        :param date_str: period name for the forecast sellected
        :param date_start: select incoming moves after this date
        :param date_stop: select incoming moves before this date
        :return: action values that open the picking list
        :rtype: dict
        """
        self.ensure_one()
        domain_confirm, domain_done = self._get_moves_domain(date_start, date_stop, 'outgoing')
        domain = OR([domain_confirm, domain_done])
        moves = self.env['stock.move'].search_read(domain, ['picking_id'])
        picking_ids = [p['picking_id'][0] for p in moves if p['picking_id']]
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'views': [(False, 'list'), (False, 'form')],
            'view_mode': 'list,form',
            'name': _('Actual Demand %s %s (%s - %s)') % (self.product_id.display_name, date_str, date_start, date_stop),
            'target': 'current',
            'domain': [('id', 'in', picking_ids)],
        }

    def action_open_actual_replenishment_details(self, date_str, date_start, date_stop):
        """ Open the actual replenishment details.

        :param date_str: period name for the forecast sellected
        :param date_start: select incoming moves and RFQ after this date
        :param date_stop: select incoming moves and RFQ before this date
        :return: action values that open the forecast details wizard
        :rtype: dict
        """
        domain_confirm, domain_done = self._get_moves_domain(date_start, date_stop, 'incoming')
        move_ids = self.env['stock.move'].search(OR([domain_confirm, domain_done])).ids

        rfq_domain = self._get_rfq_domain(date_start, date_stop)
        purchase_order_line_ids = self.env['purchase.order.line'].search(rfq_domain).ids
        name = _('Actual Replenishment %s %s (%s - %s)') % (self.product_id.display_name, date_str, date_start, date_stop)

        context = {
            'default_move_ids': move_ids,
            'default_purchase_order_line_ids': purchase_order_line_ids,
            'action_name': name,
        }
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'view_mode': 'form',
            'res_model': 'mrp.mps.forecast.details',
            'views': [(False, 'form')],
            'target': 'new',
            'context': context
        }

    def action_replenish(self, based_on_lead_time=False):
        """ Run the procurement for production schedule in self. Once the
        procurements are launched, mark the forecast as launched (only used
        for state 'to_relaunch')

        :param based_on_lead_time: 2 replenishment options exists in MPS.
        based_on_lead_time means that the procurement for self will be launched
        based on lead times.
        e.g. period are daily and the product have a manufacturing period
        of 5 days, then it will try to run the procurements for the 5 first
        period of the schedule.
        If based_on_lead_time is False then it will run the procurement for the
        first period that need a replenishment
        """
        production_schedule_states = self.get_production_schedule_view_state()
        production_schedule_states = {mps['id']: mps for mps in production_schedule_states}
        procurements = []
        forecasts_values = []
        forecasts_to_set_as_launched = self.env['mrp.product.forecast']
        for production_schedule in self:
            production_schedule_state = production_schedule_states[production_schedule.id]
            # Check for kit. If a kit and its component are both in the MPS we want to skip the
            # the kit procurement but instead only refill the components not in MPS
            bom = self.env['mrp.bom']._bom_find(
                product=production_schedule.product_id, company_id=production_schedule.company_id.id,
                bom_type='phantom')
            product_ratio = []
            if bom:
                dummy, bom_lines = bom.explode(production_schedule.product_id, 1)
                product_ids = [l[0].product_id.id for l in bom_lines]
                product_ids_with_forecast = self.env['mrp.production.schedule'].search([
                    ('company_id', '=', production_schedule.company_id.id),
                    ('warehouse_id', '=', production_schedule.warehouse_id.id),
                    ('product_id', 'in', product_ids)
                ]).product_id.ids
                product_ratio += [
                    (l[0], l[0].product_qty * l[1]['qty'])
                    for l in bom_lines if l[0].product_id.id not in product_ids_with_forecast
                ]

            # Cells with values 'to_replenish' means that they are based on
            # lead times. There is at maximum one forecast by schedule with
            # 'forced_replenish', it's the cell that need a modification with
            #  the smallest start date.
            replenishment_field = based_on_lead_time and 'to_replenish' or 'forced_replenish'
            forecasts_to_replenish = filter(lambda f: f[replenishment_field], production_schedule_state['forecast_ids'])
            for forecast in forecasts_to_replenish:
                existing_forecasts = production_schedule.forecast_ids.filtered(lambda p:
                    p.date >= forecast['date_start'] and p.date <= forecast['date_stop']
                )
                extra_values = production_schedule._get_procurement_extra_values(forecast)
                quantity = forecast['replenish_qty'] - forecast['incoming_qty']
                if not bom:
                    procurements.append(self.env['procurement.group'].Procurement(
                        production_schedule.product_id,
                        quantity,
                        production_schedule.product_uom_id,
                        production_schedule.warehouse_id.lot_stock_id,
                        production_schedule.product_id.name,
                        'MPS', production_schedule.company_id, extra_values
                    ))
                else:
                    for bom_line, qty_ratio in product_ratio:
                        procurements.append(self.env['procurement.group'].Procurement(
                            bom_line.product_id,
                            quantity * qty_ratio,
                            bom_line.product_uom_id,
                            production_schedule.warehouse_id.lot_stock_id,
                            bom_line.product_id.name,
                            'MPS', production_schedule.company_id, extra_values
                        ))

                if existing_forecasts:
                    forecasts_to_set_as_launched |= existing_forecasts
                else:
                    forecasts_values.append({
                        'forecast_qty': 0,
                        'date': forecast['date_stop'],
                        'procurement_launched': True,
                        'production_schedule_id': production_schedule.id
                    })
        if procurements:
            self.env['procurement.group'].with_context(skip_lead_time=True).run(procurements)

        forecasts_to_set_as_launched.write({
            'procurement_launched': True,
        })
        if forecasts_values:
            self.env['mrp.product.forecast'].create(forecasts_values)

    @api.model
    def get_mps_view_state(self, domain=False):
        """ Return the global information about MPS and a list of production
        schedules values with the domain.

        :param domain: domain for mrp.production.schedule
        :return: values used by the client action in order to render the MPS.
            - dates: list of period name
            - production_schedule_ids: list of production schedules values
            - manufacturing_period: list of periods (days, months or years)
            - company_id: user current company
            - groups: company settings that hide/display different rows
        :rtype: dict
        """
        productions_schedules = self.env['mrp.production.schedule'].search(domain or [])
        productions_schedules_states = productions_schedules.get_production_schedule_view_state()
        company_groups = self.env.company.read([
            'mrp_mps_show_starting_inventory',
            'mrp_mps_show_demand_forecast',
            'mrp_mps_show_indirect_demand',
            'mrp_mps_show_actual_demand',
            'mrp_mps_show_to_replenish',
            'mrp_mps_show_actual_replenishment',
            'mrp_mps_show_safety_stock',
            'mrp_mps_show_available_to_promise',
        ])
        return {
            'dates': self.env.company._date_range_to_str(),
            'production_schedule_ids': productions_schedules_states,
            'manufacturing_period': self.env.company.manufacturing_period,
            'company_id': self.env.company.id,
            'groups': company_groups,
        }

    def get_production_schedule_view_state(self):
        """ Prepare and returns the fields used by the MPS client action.
        For each schedule returns the fields on the model. And prepare the cells
        for each period depending the manufacturing period set on the company.
        The forecast cells contains the following information:
        - forecast_qty: Demand forecast set by the user
        - date_start: First day of the current period
        - date_stop: Last day of the current period
        - replenish_qty: The quantity to replenish for the current period. It
        could be computed or set by the user.
        - replenish_qty_updated: The quantity to replenish has been set manually
        by the user.
        - starting_inventory_qty: During the first period, the quantity
        available. After, the safety stock from previous period.
        - incoming_qty: The incoming moves and RFQ for the specified product and
        warehouse during the current period.
        - outgoing_qty: The outgoing moves quantity.
        - indirect_demand_qty: On manufacturing a quantity to replenish could
        require a need for a component in another schedule. e.g. 2 product A in
        order to create 1 product B. If the replenish quantity for product B is
        10, it will need 20 product A.
        - safety_stock_qty:
        starting_inventory_qty - forecast_qty - indirect_demand_qty + replenish_qty
        """
        company_id = self.env.company
        date_range = company_id._get_date_range()

        # We need to get the schedule that impact the schedules in self. Since
        # the state is not saved, it needs to recompute the quantity to
        # replenish of finished products. It will modify the indirect
        # demand and replenish_qty of schedules in self.
        schedules_to_compute = self.env['mrp.production.schedule'].browse(self.get_impacted_schedule()) | self

        # Dependencies between schedules
        indirect_demand_trees = schedules_to_compute._get_indirect_demand_tree()

        indirect_ratio_mps = schedules_to_compute._get_indirect_demand_ratio_mps(indirect_demand_trees)

        # Get the schedules that do not depends from other in first position in
        # order to compute the schedule state only once.
        indirect_demand_order = schedules_to_compute._get_indirect_demand_order(indirect_demand_trees)
        indirect_demand_qty = defaultdict(float)
        incoming_qty, incoming_qty_done = self._get_incoming_qty(date_range)
        outgoing_qty, outgoing_qty_done = self._get_outgoing_qty(date_range)
        read_fields = [
            'forecast_target_qty',
            'min_to_replenish_qty',
            'max_to_replenish_qty',
            'product_id',
        ]
        if self.env.user.has_group('stock.group_stock_multi_warehouses'):
            read_fields.append('warehouse_id')
        if self.env.user.has_group('uom.group_uom'):
            read_fields.append('product_uom_id')
        production_schedule_states = schedules_to_compute.read(read_fields)
        production_schedule_states_by_id = {mps['id']: mps for mps in production_schedule_states}
        for production_schedule in indirect_demand_order:
            # Bypass if the schedule is only used in order to compute indirect
            # demand.
            rounding = production_schedule.product_id.uom_id.rounding
            lead_time = production_schedule._get_lead_times()
            production_schedule_state = production_schedule_states_by_id[production_schedule['id']]
            if production_schedule in self:
                procurement_date = add(fields.Date.today(), days=lead_time)
                precision_digits = max(0, int(-(log10(production_schedule.product_uom_id.rounding))))
                production_schedule_state['precision_digits'] = precision_digits
                production_schedule_state['forecast_ids'] = []

            starting_inventory_qty = production_schedule.product_id.with_context(warehouse=production_schedule.warehouse_id.id).qty_available
            if len(date_range):
                starting_inventory_qty -= incoming_qty_done.get((date_range[0], production_schedule.product_id, production_schedule.warehouse_id), 0.0)
                starting_inventory_qty += outgoing_qty_done.get((date_range[0], production_schedule.product_id, production_schedule.warehouse_id), 0.0)

            for date_start, date_stop in date_range:
                forecast_values = {}
                key = ((date_start, date_stop), production_schedule.product_id, production_schedule.warehouse_id)
                existing_forecasts = production_schedule.forecast_ids.filtered(lambda p: p.date >= date_start and p.date <= date_stop)
                if production_schedule in self:
                    forecast_values['date_start'] = date_start
                    forecast_values['date_stop'] = date_stop
                    forecast_values['incoming_qty'] = float_round(incoming_qty.get(key, 0.0) + incoming_qty_done.get(key, 0.0), precision_rounding=rounding)
                    forecast_values['outgoing_qty'] = float_round(outgoing_qty.get(key, 0.0) + outgoing_qty_done.get(key, 0.0), precision_rounding=rounding)

                forecast_values['indirect_demand_qty'] = float_round(indirect_demand_qty.get(key, 0.0), precision_rounding=rounding)
                replenish_qty_updated = False
                if existing_forecasts:
                    forecast_values['forecast_qty'] = float_round(sum(existing_forecasts.mapped('forecast_qty')), precision_rounding=rounding)
                    forecast_values['replenish_qty'] = float_round(sum(existing_forecasts.mapped('replenish_qty')), precision_rounding=rounding)

                    # Check if the to replenish quantity has been manually set or
                    # if it needs to be computed.
                    replenish_qty_updated = any(existing_forecasts.mapped('replenish_qty_updated'))
                    forecast_values['replenish_qty_updated'] = replenish_qty_updated
                else:
                    forecast_values['forecast_qty'] = 0.0

                if not replenish_qty_updated:
                    replenish_qty = production_schedule._get_replenish_qty(starting_inventory_qty - forecast_values['forecast_qty'] - forecast_values['indirect_demand_qty'])
                    forecast_values['replenish_qty'] = float_round(replenish_qty, precision_rounding=rounding)
                    forecast_values['replenish_qty_updated'] = False

                forecast_values['starting_inventory_qty'] = float_round(starting_inventory_qty, precision_rounding=rounding)
                forecast_values['safety_stock_qty'] = float_round(starting_inventory_qty - forecast_values['forecast_qty'] - forecast_values['indirect_demand_qty'] + forecast_values['replenish_qty'], precision_rounding=rounding)

                if production_schedule in self:
                    production_schedule_state['forecast_ids'].append(forecast_values)
                starting_inventory_qty = forecast_values['safety_stock_qty']
                if not forecast_values['replenish_qty']:
                    continue
                # Set the indirect demand qty for children schedules.
                for (product, ratio) in indirect_ratio_mps[(production_schedule.warehouse_id, production_schedule.product_id)].items():
                    related_date = max(subtract(date_start, days=lead_time), fields.Date.today())
                    index = next(i for i, (dstart, dstop) in enumerate(date_range) if related_date <= dstart or (related_date >= dstart and related_date <= dstop))
                    related_key = (date_range[index], product, production_schedule.warehouse_id)
                    indirect_demand_qty[related_key] += ratio * forecast_values['replenish_qty']

            if production_schedule in self:
                # The state is computed after all because it needs the final
                # quantity to replenish.
                forecasts_state = production_schedule._get_forecasts_state(production_schedule_states_by_id, date_range, procurement_date)
                forecasts_state = forecasts_state[production_schedule.id]
                for index, forecast_state in enumerate(forecasts_state):
                    production_schedule_state['forecast_ids'][index].update(forecast_state)

                # The purpose is to hide indirect demand row if the schedule do not
                # depends from another.
                has_indirect_demand = any(forecast['indirect_demand_qty'] != 0 for forecast in production_schedule_state['forecast_ids'])
                production_schedule_state['has_indirect_demand'] = has_indirect_demand
        return [p for p in production_schedule_states if p['id'] in self.ids]

    def get_impacted_schedule(self, domain=False):
        """ When the user modify the demand forecast on a schedule. The new
        replenish quantity is computed from schedules that use the product in
        self as component (no matter at which BoM level). It will also modify
        the replenish quantity on self that will impact the schedule that use
        the product in self as a finished product.

        :param domain: filter supplied and supplying schedules with the domain
        :return ids of supplied and supplying schedules
        :rtype list
        """
        if not domain:
            domain = []

        def _used_in_bom(products, related_products):
            """ Bottom up from bom line to finished products in order to get
            all the finished products that use 'products' as component.
            """
            if not products:
                return related_products
            boms = products.bom_line_ids.mapped('bom_id')
            products = boms.mapped('product_id') | boms.mapped('product_tmpl_id.product_variant_ids')
            products -= related_products
            related_products |= products
            return _used_in_bom(products, related_products)

        supplying_mps = self.env['mrp.production.schedule'].search(
            AND([domain, [
                ('warehouse_id', 'in', self.mapped('warehouse_id').ids),
                ('product_id', 'in', _used_in_bom(self.mapped('product_id'), self.env['product.product']).ids)
            ]]))

        def _use_boms(products, related_products):
            """ Explore bom line from products's BoMs in order to get components
            used.
            """
            if not products:
                return related_products
            boms = products.bom_ids | products.mapped('product_variant_ids.bom_ids')
            products = boms.mapped('bom_line_ids.product_id')
            products -= related_products
            related_products |= products
            return _use_boms(products, related_products)

        supplied_mps = self.env['mrp.production.schedule'].search(
            AND([domain, [
                ('warehouse_id', 'in', self.mapped('warehouse_id').ids),
                ('product_id', 'in', _use_boms(self.mapped('product_id'), self.env['product.product']).ids)
            ]]))
        return (supplying_mps | supplied_mps).ids

    def remove_replenish_qty(self, date_index):
        """ Remove the quantity to replenish on the forecast cell.

        param date_index: index of the period used to find start and stop date
        where the manual replenish quantity should be remove.
        """
        date_start, date_stop = self.company_id._get_date_range()[date_index]
        forecast_ids = self.forecast_ids.filtered(lambda f:
            f.date >= date_start and f.date <= date_stop)
        forecast_ids.write({
            'replenish_qty': 0.0,
            'replenish_qty_updated': False,
        })
        return True

    def set_forecast_qty(self, date_index, quantity):
        """ Save the forecast quantity:

        params quantity: The new total forecasted quantity
        params date_index: The manufacturing period
        """
        # Get the last date of current period
        self.ensure_one()
        date_start, date_stop = self.company_id._get_date_range()[date_index]
        existing_forecast = self.forecast_ids.filtered(lambda f:
            f.date >= date_start and f.date <= date_stop)
        quantity = float_round(float(quantity), precision_rounding=self.product_uom_id.rounding)
        quantity_to_add = quantity - sum(existing_forecast.mapped('forecast_qty'))
        if existing_forecast:
            new_qty = existing_forecast[0].forecast_qty + quantity_to_add
            new_qty = float_round(new_qty, precision_rounding=self.product_uom_id.rounding)
            existing_forecast[0].write({'forecast_qty': new_qty})
        else:
            existing_forecast.create({
                'forecast_qty': quantity,
                'date': date_stop,
                'replenish_qty': 0,
                'production_schedule_id': self.id
            })
        return True

    def set_replenish_qty(self, date_index, quantity):
        """ Save the replenish quantity and mark the cells as manually updated.

        params quantity: The new quantity to replenish
        params date_index: The manufacturing period
        """
        # Get the last date of current period
        self.ensure_one()
        date_start, date_stop = self.company_id._get_date_range()[date_index]
        existing_forecast = self.forecast_ids.filtered(lambda f:
            f.date >= date_start and f.date <= date_stop)
        quantity = float_round(float(quantity), precision_rounding=self.product_uom_id.rounding)
        quantity_to_add = quantity - sum(existing_forecast.mapped('replenish_qty'))
        if existing_forecast:
            new_qty = existing_forecast[0].replenish_qty + quantity_to_add
            new_qty = float_round(new_qty, precision_rounding=self.product_uom_id.rounding)
            existing_forecast[0].write({
                'replenish_qty': new_qty,
                'replenish_qty_updated': True
            })
        else:
            existing_forecast.create({
                'forecast_qty': 0,
                'date': date_stop,
                'replenish_qty': quantity,
                'replenish_qty_updated': True,
                'production_schedule_id': self.id
            })
        return True

    def _get_procurement_extra_values(self, forecast_values):
        """ Extra values that could be added in the vals for procurement.

        return values pass to the procurement run method.
        rtype dict
        """
        return {
            'date_planned': forecast_values['date_start'],
            'warehouse_id': self.warehouse_id,
        }

    def _get_forecasts_state(self, production_schedule_states, date_range, procurement_date):
        """ Return the state for each forecast cells.
        - to_relaunch: A procurement has been launched for the same date range
        but a replenish modification require a new procurement.
        - to_correct: The actual replenishment is greater than planned, the MPS
        should be updated in order to match reality.
        - launched: Nothing todo. Either the cell is in the lead time range but
        the forecast match the actual replenishment. Or a foreced replenishment
        happens but the forecast and the actual demand still the same.
        - to_launch: The actual replenishment is lower than forecasted.

        It also add a tag on cell in order to:
        - to_replenish: The cell is to launch and it needs to be runned in order
        to arrive on time due to lead times.
        - forced_replenish: Cell to_launch or to_relaunch with the smallest
        period

        param production_schedule_states: schedules with a state to compute
        param date_range: list of period where a state should be computed
        param procurement_date: today + lead times for products in self
        return: the state for each time slot in date_range for each schedule in
        production_schedule_states
        rtype: dict
        """
        forecasts_state = defaultdict(list)
        for production_schedule in self:
            forecast_values = production_schedule_states[production_schedule.id]['forecast_ids']
            forced_replenish = True
            for index, (date_start, date_stop) in enumerate(date_range):
                forecast_state = {}
                forecast_value = forecast_values[index]
                existing_forecasts = production_schedule.forecast_ids.filtered(lambda p: p.date >= date_start and p.date <= date_stop)
                procurement_launched = any(existing_forecasts.mapped('procurement_launched'))

                replenish_qty = forecast_value['replenish_qty']
                incoming_qty = forecast_value['incoming_qty']
                if incoming_qty < replenish_qty and procurement_launched:
                    state = 'to_relaunch'
                elif incoming_qty > replenish_qty:
                    state = 'to_correct'
                elif incoming_qty == replenish_qty and (date_start <= procurement_date or procurement_launched):
                    state = 'launched'
                else:
                    state = 'to_launch'
                forecast_state['state'] = state

                forecast_state['forced_replenish'] = False
                forecast_state['to_replenish'] = False

                procurement_qty = replenish_qty - incoming_qty
                if forecast_state['state'] not in ('launched', 'to_correct') and procurement_qty > 0:
                    if date_start <= procurement_date:
                        forecast_state['to_replenish'] = True
                    if forced_replenish:
                        forecast_state['forced_replenish'] = True
                        forced_replenish = False

                forecasts_state[production_schedule.id].append(forecast_state)
        return forecasts_state

    def _get_lead_times(self):
        """ Get the lead time for each product in self. The lead times are
        based on rules lead times + produce delay or supplier info delay.
        """
        def _get_rule_lead_time(lead_time, product, location):
            rule = self.env['procurement.group']._get_rule(product, location, {})
            if not rule:
                return lead_time

            lead_time += rule.delay
            if rule.action == 'manufacture':
                lead_time += product.produce_delay
            if rule.action == 'buy':
                company_lead_time = self.env.company.po_lead
                supplier_lead_time = product.seller_ids and product.seller_ids[0].delay or 0
                lead_time += (company_lead_time + supplier_lead_time)
            if rule.procure_method == 'make_to_stock':
                return lead_time
            else:
                return _get_rule_lead_time(lead_time, product, rule.location_src_id)

        return _get_rule_lead_time(0, self.product_id, self.warehouse_id.lot_stock_id)

    def _get_replenish_qty(self, after_forecast_qty):
        """ Modify the quantity to replenish depending the min/max and targeted
        quantity for safety stock.

        param after_forecast_qty: The quantity to replenish in order to reach a
        safety stock of 0.
        return: quantity to replenish
        rtype: float
        """
        optimal_qty = self.forecast_target_qty - after_forecast_qty

        if optimal_qty > self.max_to_replenish_qty:
            replenish_qty = self.max_to_replenish_qty
        elif optimal_qty < self.min_to_replenish_qty:
            replenish_qty = self.min_to_replenish_qty
        else:
            replenish_qty = optimal_qty

        return replenish_qty

    def _get_incoming_qty(self, date_range):
        """ Get the incoming quantity from RFQ and existing moves.

        param: list of time slots used in order to group incoming quantity.
        return: a dict with as key a production schedule and as values a list
        of incoming quantity for each date range.
        """
        incoming_qty = defaultdict(float)
        incoming_qty_done = defaultdict(float)
        after_date = date_range[0][0]
        before_date = date_range[-1][1]
        # Get quantity in RFQ
        rfq_domain = self._get_rfq_domain(after_date, before_date)
        rfq_lines = self.env['purchase.order.line'].search(rfq_domain, order='date_planned')

        index = 0
        for line in rfq_lines:
            # Skip to the next time range if the planned date is not in the
            # current time interval.
            while not (date_range[index][0] <= line.date_planned.date() and
                    date_range[index][1] >= line.date_planned.date()):
                index += 1
            quantity = line.product_uom._compute_quantity(line.product_qty, line.product_id.uom_id)
            incoming_qty[date_range[index], line.product_id, line.order_id.picking_type_id.warehouse_id] += quantity

        # Get quantity on incoming moves
        # TODO: issue since it will use one search by move. Should use a
        # read_group with a group by location.
        domain_moves_confirmed, domain_moves_done = self._get_moves_domain(after_date, before_date, 'incoming')
        stock_moves_confirmed = self.env['stock.move'].search(domain_moves_confirmed, order='date_expected')
        stock_moves_done = self.env['stock.move'].search(domain_moves_done, order='date')
        index = 0
        for move in stock_moves_confirmed:
            # Skip to the next time range if the planned date is not in the
            # current time interval.
            while not (date_range[index][0] <= move.date_expected.date() and
                    date_range[index][1] >= move.date_expected.date()):
                index += 1
            key = (date_range[index], move.product_id, move.location_dest_id.get_warehouse())
            incoming_qty[key] += move.product_qty

        index = 0
        for move in stock_moves_done:
            # Skip to the next time range if the planned date is not in the
            # current time interval.
            while not (date_range[index][0] <= move.date.date() and
                    date_range[index][1] >= move.date.date()):
                index += 1
            key = (date_range[index], move.product_id, move.location_dest_id.get_warehouse())
            incoming_qty_done[key] += move.product_qty

        return incoming_qty, incoming_qty_done

    def _get_indirect_demand_order(self, indirect_demand_trees):
        """ return a new order for record in self. The order returned ensure
        that the indirect demand from a record in the set could only be modified
        by a record before it. The purpose of this function is to define the
        states of multiple schedules only once by schedule and avoid to
        recompute a state because its indirect demand was a depend from another
        schedule.
        """
        product_ids = self.mapped('product_id')

        def _get_pre_order(node):
            order_list = []
            if node.product in product_ids:
                order_list.append(node.product)
            for child in node.children:
                order_list += _get_pre_order(child)
            return order_list

        product_order_by_tree = []
        for node in indirect_demand_trees:
            product_order_by_tree += _get_pre_order(node)

        product_order = OrderedDict()
        for product in reversed(product_order_by_tree):
            if product not in product_order:
                product_order[product] = True

        mps_order_by_product = defaultdict(lambda: self.env['mrp.production.schedule'])
        for mps in self:
            mps_order_by_product[mps.product_id] |= mps

        mps_order = self.env['mrp.production.schedule']
        for product in reversed(product_order.keys()):
            mps_order |= mps_order_by_product[product]
        return mps_order

    def _get_indirect_demand_ratio_mps(self, indirect_demand_trees):
        """ Return {(warehouse, product): {product: ratio}} dict containing the indirect ratio
        between two products.
        """
        by_warehouse_mps = defaultdict(lambda: self.env['mrp.production.schedule'])
        for mps in self:
            by_warehouse_mps[mps.warehouse_id] |= mps

        result = defaultdict(lambda: defaultdict(float))
        for warehouse_id, other_mps in by_warehouse_mps.items():
            other_mps_product_ids = other_mps.mapped('product_id')
            subtree_visited = set()

            def _dfs_ratio_search(current_node, ratio, node_indirect=False):
                for child in current_node.children:
                    if child.product in other_mps_product_ids:
                        result[(warehouse_id, node_indirect and node_indirect.product or current_node.product)][child.product] += ratio * child.ratio
                        if child.product in subtree_visited:  # Don't visit the same subtree twice
                            continue
                        subtree_visited.add(child.product)
                        _dfs_ratio_search(child, 1.0, node_indirect=False)
                    else:  # Hidden Bom => continue DFS and set node_indirect
                        _dfs_ratio_search(child, child.ratio * ratio, node_indirect=current_node)

            for tree in indirect_demand_trees:
                _dfs_ratio_search(tree, tree.ratio)

        return result

    def _get_indirect_demand_tree(self):
        """ Get the tree architecture for all the BoM and BoM line that are
        related to production schedules in self. The purpose of the tree:
        - Easier traversal than with BoM and BoM lines.
        - Allow to determine the schedules evaluation order. (compute the
        schedule without indirect demand first)
        It also made the link between schedules even if some intermediate BoM
        levels are hidden. (e.g. B1 -1-> B2 -1-> B3, schedule for B1 and B3
        are linked even if the schedule for B2 does not exist.)
        Return a list of namedtuple that represent on top the schedules without
        indirect demand and on lowest leaves the schedules that are the most
        influenced by the others.
        """
        boms = self.env['mrp.bom'].search([
            '|',
            ('product_id', 'in', self.mapped('product_id').ids),
            '&',
            ('product_id', '=', False),
            ('product_tmpl_id', 'in', self.mapped('product_id.product_tmpl_id').ids)
        ])
        bom_lines_by_product = defaultdict(lambda: self.env['mrp.bom'])
        bom_lines_by_product_tmpl = defaultdict(lambda: self.env['mrp.bom'])
        for bom in boms:
            if bom.product_id:
                if bom.product_id not in bom_lines_by_product:
                    bom_lines_by_product[bom.product_id] = bom
            else:
                if bom.product_tmpl_id not in bom_lines_by_product_tmpl:
                    bom_lines_by_product_tmpl[bom.product_tmpl_id] = bom

        Node = namedtuple('Node', ['product', 'ratio', 'children'])
        indirect_demand_trees = {}
        product_visited = {}

        def _get_product_tree(product, ratio):
            product_tree = product_visited.get(product)
            if product_tree:
                return Node(product_tree.product, ratio, product_tree.children)

            product_tree = Node(product, ratio, [])
            product_boms = (bom_lines_by_product[product] | bom_lines_by_product_tmpl[product.product_tmpl_id]).sorted('sequence')[:1]
            if not product_boms:
                product_boms = self.env['mrp.bom']._bom_find(product=product) or self.env['mrp.bom']
            for line in product_boms.bom_line_ids:
                line_qty = line.product_uom_id._compute_quantity(line.product_qty, line.product_id.uom_id)
                bom_qty = line.bom_id.product_uom_id._compute_quantity(line.bom_id.product_qty, line.bom_id.product_tmpl_id.uom_id)
                ratio = line_qty / bom_qty
                tree = _get_product_tree(line.product_id, ratio)
                product_tree.children.append(tree)
                if line.product_id in indirect_demand_trees:
                    del indirect_demand_trees[line.product_id]
            product_visited[product] = product_tree
            return product_tree

        for product in self.mapped('product_id'):
            if product in product_visited:
                continue
            indirect_demand_trees[product] = _get_product_tree(product, 1.0)

        return [tree for tree in indirect_demand_trees.values()]

    def _get_moves_domain(self, date_start, date_stop, type):
        """ Return domain for incoming or outgoing moves """
        location = type == 'incoming' and 'location_dest_id' or 'location_id'
        location_dest = type == 'incoming' and 'location_id' or 'location_dest_id'
        domain_confirmed = [
            (location, 'child_of', self.mapped('warehouse_id.view_location_id').ids),
            ('product_id', 'in', self.mapped('product_id').ids),
            ('state', 'not in', ['done', 'cancel', 'draft']),
            (location + '.usage', '!=', 'inventory'),
            '|',
                (location_dest + '.usage', 'not in', ('internal', 'inventory')),
                '&',
                (location_dest + '.usage', '=', 'internal'),
                '!',
                    (location_dest, 'child_of', self.mapped('warehouse_id.view_location_id').ids),
            ('inventory_id', '=', False),
            ('date_expected', '>=', date_start),
            ('date_expected', '<=', date_stop)
        ]
        domain_done = [
            (location, 'child_of', self.mapped('warehouse_id.view_location_id').ids),
            ('product_id', 'in', self.mapped('product_id').ids),
            ('state', '=', 'done'),
            (location + '.usage', '!=', 'inventory'),
            '|',
                (location_dest + '.usage', 'not in', ('internal', 'inventory')),
                '&',
                (location_dest + '.usage', '=', 'internal'),
                '!',
                    (location_dest, 'child_of', self.mapped('warehouse_id.view_location_id').ids),
            ('inventory_id', '=', False),
            ('date', '>=', date_start),
            ('date', '<=', date_stop)
        ]
        return domain_confirmed, domain_done

    def _get_outgoing_qty(self, date_range):
        """ Get the outgoing quantity from existing moves.
        return a dict with as key a production schedule and as values a list
        of outgoing quantity for each date range.
        """
        outgoing_qty = defaultdict(float)
        outgoing_qty_done = defaultdict(float)
        after_date = date_range[0][0]
        before_date = date_range[-1][1]
        # Get quantity on incoming moves

        domain_moves_confirmed, domain_moves_done = self._get_moves_domain(after_date, before_date, 'outgoing')
        domain_moves_confirmed = AND([domain_moves_confirmed, [('raw_material_production_id', '=', False)]])
        domain_moves_done = AND([domain_moves_done, [('raw_material_production_id', '=', False)]])

        stock_moves_confirmed = self.env['stock.move'].search(domain_moves_confirmed, order='date_expected')
        index = 0
        for move in stock_moves_confirmed:
            # Skip to the next time range if the planned date is not in the
            # current time interval.
            while not (date_range[index][0] <= move.date_expected.date() and
                    date_range[index][1] >= move.date_expected.date()):
                index += 1
            key = (date_range[index], move.product_id, move.location_id.get_warehouse())
            outgoing_qty[key] += move.product_uom_qty

        stock_moves_done = self.env['stock.move'].search(domain_moves_done, order='date')
        index = 0
        for move in stock_moves_done:
            # Skip to the next time range if the planned date is not in the
            # current time interval.
            while not (date_range[index][0] <= move.date.date() and
                    date_range[index][1] >= move.date.date()):
                index += 1
            key = (date_range[index], move.product_id, move.location_id.get_warehouse())
            outgoing_qty_done[key] += move.product_uom_qty

        return outgoing_qty, outgoing_qty_done

    def _get_rfq_domain(self, date_start, date_stop):
        """ Return a domain used to compute the incoming quantity for a given
        product/warehouse/company.

        :param date_start: start date of the forecast domain
        :param date_stop: end date of the forecast domain
        """
        return [
            ('order_id.picking_type_id.default_location_dest_id', 'child_of', self.mapped('warehouse_id.view_location_id').ids),
            ('product_id', 'in', self.mapped('product_id').ids),
            ('state', 'in', ('draft', 'sent', 'to approve')),
            ('date_planned', '>=', date_start),
            ('date_planned', '<=', date_stop)
        ]


class MrpProductForecast(models.Model):
    _name = 'mrp.product.forecast'
    _order = 'date'
    _description = 'Product Forecast at Date'

    production_schedule_id = fields.Many2one('mrp.production.schedule',
        required=True, ondelete='cascade')
    date = fields.Date('Date', required=True)

    forecast_qty = fields.Float('Demand Forecast')
    replenish_qty = fields.Float('To Replenish')
    replenish_qty_updated = fields.Boolean('Replenish_qty has been manually updated')

    procurement_launched = fields.Boolean('Procurement has been run for this forecast')
