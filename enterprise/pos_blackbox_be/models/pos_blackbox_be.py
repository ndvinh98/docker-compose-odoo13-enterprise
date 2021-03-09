# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from odoo.addons.base.models import res_users as ru
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from odoo.tools.translate import _
from dateutil import parser
from itertools import groupby


class AccountTax(models.Model):
    _inherit = 'account.tax'

    identification_letter = fields.Selection([('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')], compute='_compute_identification_letter')

    @api.depends('amount_type', 'amount')
    def _compute_identification_letter(self):
        for rec in self:
            if rec.type_tax_use == "sale" and (rec.amount_type == "percent" or rec.amount_type == "group"):
                if rec.amount == 21:
                    rec.identification_letter = "A"
                elif rec.amount == 12:
                    rec.identification_letter = "B"
                elif rec.amount == 6:
                    rec.identification_letter = "C"
                elif rec.amount == 0:
                    rec.identification_letter = "D"
                else:
                    rec.identification_letter = False
            else:
                rec.identification_letter = False

class pos_config(models.Model):
    _inherit = 'pos.config'

    report_sequence_number = fields.Integer()
    blackbox_pos_production_id = fields.Char("Registered IoT Box serial number",
        help='e.g. BODO001... The IoT Box must be certified by Odoo S.A. to be used with the blackbox.',
        copy=False)
    iface_fiscal_data_module = fields.Many2one('iot.device',
                                               domain="[('type', '=', 'fiscal_data_module'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    @api.constrains("module_pos_reprint", "module_pos_discount", "module_pos_loyalty","blackbox_pos_production_id")
    def _check_blackbox_config(self):
        for config in self:
            if config.blackbox_pos_production_id and (config.module_pos_reprint or config.module_pos_discount or config.module_pos_loyalty):
                raise UserError(_("Loyalty programs, reprint and global discounts cannot be used on a PoS associated with a blackbox."))

    @api.constrains('blackbox_pos_production_id')
    def _check_blackbox_pos_production(self):
        for config in self:
            if config.blackbox_pos_production_id:
                if len(config.blackbox_pos_production_id) != 14:
                    raise ValidationError(_("Serial number must consist of 14 characters."))

    def open_session_cb(self):
        if self.blackbox_pos_production_id:
            self._check_insz_user()
            self._check_company_address()
            self._check_work_product_taxes()
        return super(pos_config, self).open_session_cb()

    def _check_work_product_taxes(self):
        work_in = self.env.ref('pos_blackbox_be.product_product_work_in')
        work_out = self.env.ref('pos_blackbox_be.product_product_work_out')
        if not work_in.taxes_id or work_in.taxes_id.amount != 0 or not work_out.taxes_id or work_out.taxes_id.amount != 0:
            raise ValidationError(_("The WORK IN/OUT products must have a taxes with 0%."))

    def _check_insz_user(self):
        if not self.env.user.insz_or_bis_number:
            raise ValidationError(_("The user must have a INSZ or BIS number."))

    def _check_company_address(self):
        if not self.company_id.street:
            raise ValidationError(_("The address of the company must be filled."))

    @api.constrains('blackbox_pos_production_id', 'iface_fiscal_data_module', 'is_posbox')
    def _check_iot_and_blackbox_state(self):
        for config in self:
            if (config.blackbox_pos_production_id and not config.iface_fiscal_data_module) \
                    or (not config.blackbox_pos_production_id and config.iface_fiscal_data_module) \
                    or (config.blackbox_pos_production_id and config.iface_fiscal_data_module and not config.is_posbox):
                raise ValidationError(_("The certified PosBox Ref and the fiscal data module fields have to be set together or ignored."))

    @api.constrains('blackbox_pos_production_id', 'fiscal_position_ids')
    def _check_posbox_fp_tax_code(self):
        for config in self:
            if not config.blackbox_pos_production_id:
                continue

            for fp in config.fiscal_position_ids:
                for tax_line in fp.tax_ids:
                    if tax_line.tax_src_id.identification_letter and not tax_line.tax_dest_id.identification_letter:
                        raise ValidationError(_("Fiscal Position %s (tax %s) has an invalid tax amount. Only 21%%, 12%%, 6%% and 0%% are allowed.") % (fp.name, tax_line.tax_dest_id.name))


    def get_next_report_sequence_number(self):
        to_return = self.report_sequence_number
        self.report_sequence_number += 1

        return to_return

    def _compute_iot_device_ids(self):
        super(pos_config, self)._compute_iot_device_ids()
        for config in self:
            if config.is_posbox:
                config.iot_device_ids += config.iface_fiscal_data_module


class res_users(models.Model):
    _inherit = 'res.users'

    # bis number is for foreigners in Belgium
    insz_or_bis_number = fields.Char("INSZ or BIS number",
                                     help="Social security identification number")
    session_clocked_ids = fields.Many2many(
        'pos.session',
        'users_session_clocking_info',
        string='Session Clocked In',
        help='This is a technical field used for tracking the status of the session for each users.',
    )

    @api.constrains('insz_or_bis_number')
    def _check_insz_or_bis_number(self):
        for rec in self:
            if rec.insz_or_bis_number and (len(rec.insz_or_bis_number) != 11 or not rec.insz_or_bis_number.isdigit()):
                raise ValidationError(_("The INSZ or BIS number has to consist of 11 numerical digits."))

    @api.model
    def create(self, values):

        filtered_values = {field: ('********' if field in ru.USER_PRIVATE_FIELDS else value)
                               for field, value in values.items()}
        self.env['pos_blackbox_be.log'].sudo().create(filtered_values, "create", self._name, values.get('login'))

        return super(res_users, self).create(values)

    def write(self, values):

        filtered_values = {field: ('********' if field in ru.USER_PRIVATE_FIELDS else value)
                               for field, value in values.items()}
        for user in self:
            self.env['pos_blackbox_be.log'].sudo().create(filtered_values, "modify", user._name, user.login)

        return super(res_users, self).write(values)

    def unlink(self):

        for user in self:
            self.env['pos_blackbox_be.log'].sudo().create({}, "delete", user._name, user.login)

        return super(res_users, self).unlink()


class pos_session(models.Model):
    _inherit = 'pos.session'

    pro_forma_order_ids = fields.One2many('pos.order_pro_forma', 'session_id')

    total_sold = fields.Monetary(compute='_compute_total_sold')
    total_pro_forma = fields.Monetary(compute='_compute_total_pro_forma')
    total_base_of_measure_tax_a = fields.Monetary(compute='_compute_total_tax')
    total_base_of_measure_tax_b = fields.Monetary(compute='_compute_total_tax')
    total_base_of_measure_tax_c = fields.Monetary(compute='_compute_total_tax')
    total_base_of_measure_tax_d = fields.Monetary(compute='_compute_total_tax')
    total_tax_a = fields.Monetary(compute='_compute_total_tax')
    total_tax_b = fields.Monetary(compute='_compute_total_tax')
    total_tax_c = fields.Monetary(compute='_compute_total_tax')
    total_tax_d = fields.Monetary(compute='_compute_total_tax')
    amount_of_vat_tickets = fields.Integer(compute='_compute_amounts_of_tickets')
    amount_of_pro_forma_tickets = fields.Integer(compute='_compute_amounts_of_tickets')
    amount_of_discounts = fields.Integer(compute='_compute_discounts')
    total_discount = fields.Monetary(compute='_compute_discounts')
    amount_of_corrections = fields.Integer(compute='_compute_corrections')
    total_corrections = fields.Monetary(compute='_compute_corrections')
    users_clocked_ids = fields.Many2many(
        'res.users',
        'users_session_clocking_info',
        string='Users Clocked In',
        help='This is a technical field used for tracking the status of the session for each users.',
    )

    @api.depends('statement_ids')
    def _compute_total_sold(self):
        for rec in self:
            rec.total_sold = 0
            for st in rec.statement_ids:
                rec.total_sold += st.total_entry_encoding

    @api.depends('pro_forma_order_ids')
    def _compute_total_pro_forma(self):
        for rec in self:
            rec.total_pro_forma = 0
            for pro_forma in rec.pro_forma_order_ids:
                rec.total_pro_forma += pro_forma.amount_total

    @api.depends('order_ids')
    def _compute_total_tax(self):
        for rec in self:
            rec.total_base_of_measure_tax_a = 0
            rec.total_base_of_measure_tax_b = 0
            rec.total_base_of_measure_tax_c = 0
            rec.total_base_of_measure_tax_d = 0
            for order in rec.order_ids:
                rec.total_base_of_measure_tax_a += order.blackbox_tax_category_a
                rec.total_base_of_measure_tax_b += order.blackbox_tax_category_b
                rec.total_base_of_measure_tax_c += order.blackbox_tax_category_c
                rec.total_base_of_measure_tax_d += order.blackbox_tax_category_d
            # compute the tax totals
            currency = self.env['res.currency'].browse(rec.currency_id.id)
            rec.total_tax_a = currency.round(rec.total_base_of_measure_tax_a * 0.21)
            rec.total_tax_b = currency.round(rec.total_base_of_measure_tax_b * 0.12)
            rec.total_tax_c = currency.round(rec.total_base_of_measure_tax_c * 0.06)
            rec.total_tax_d = 0

    @api.depends('order_ids')
    def _compute_amount_of_vat_tickets(self):
        for rec in self:
            rec.amount_of_vat_tickets = len(rec.order_ids)

    @api.depends('order_ids', 'pro_forma_order_ids')
    def _compute_amounts_of_tickets(self):
        for rec in self:
            rec.amount_of_vat_tickets = len(rec.order_ids)
            rec.amount_of_pro_forma_tickets = len(rec.pro_forma_order_ids)

    @api.depends('order_ids')
    def _compute_discounts(self):
        for rec in self:
            rec.amount_of_discounts = 0
            rec.total_discount = 0
            for order in rec.order_ids:
                for line in order.lines:
                    if line.discount > 0:
                        rec.amount_of_discounts += 1
                        original_line_discount = line.discount
                        line.discount = 0
                        price_without_discount = line.price_subtotal_incl
                        line.discount = original_line_discount
                        rec.total_discount += price_without_discount - line.price_subtotal_incl

    @api.depends('order_ids')
    def _compute_corrections(self):
        for rec in self:
            rec.amount_of_corrections = 0
            rec.total_corrections = 0
            for order in rec.order_ids:
                for line in order.lines:
                    if line.price_subtotal_incl < 0:
                        rec.amount_of_corrections += 1
                        rec.total_corrections += line.price_subtotal_incl

    def get_user_session_work_status(self, user_id):
        if user_id in self.users_clocked_ids.ids:
            return True
        return False

    def set_user_session_work_status(self, user_id, status):
        if status:
            self.write({'users_clocked_ids': [(4, user_id)]})
        else:
            self.write({'users_clocked_ids': [(3, user_id)]})
        return self.users_clocked_ids.ids

    def action_pos_session_closing_control(self):
        # The government does not want PS orders that have not been
        # finalized into an NS before we close a session
        pro_forma_orders = self.env['pos.order_pro_forma'].search([('session_id', '=', self.id)])
        regular_orders = self.env['pos.order'].search([('session_id', '=', self.id)])

        # we can link pro forma orders to regular orders using their pos_reference
        pro_forma_orders = {order.pos_reference for order in pro_forma_orders}
        regular_orders = {order.pos_reference for order in regular_orders}
        non_finalized_orders = pro_forma_orders.difference(regular_orders)

        if non_finalized_orders:
            raise UserError(_("Your session still contains open orders (%s). Please close all of them first.") % ', '.join(non_finalized_orders))

        return super(pos_session, self).action_pos_session_closing_control()

    def get_total_sold_per_category(self, group_by_user_id=None):
        total_sold_per_user_per_category = {}

        for order in self.order_ids:
            if group_by_user_id:
                user_id = order.user_id.id
            else:
                # use a user_id of 0 to keep the logic between with user group and without user group the same
                user_id = 0

            if user_id not in total_sold_per_user_per_category:
                total_sold_per_user_per_category[user_id] = {}

            total_sold_per_category = total_sold_per_user_per_category[user_id]

            for line in order.lines:
                key = line.product_id.pos_categ_id.name or "None"

                if key in total_sold_per_category:
                    total_sold_per_category[key] += line.price_subtotal_incl
                else:
                    total_sold_per_category[key] = line.price_subtotal_incl

        if group_by_user_id or not total_sold_per_user_per_category:
            return list(total_sold_per_user_per_category.items())
        else:
            return list(total_sold_per_user_per_category[0].items())

    def _get_order_data_for_user_report(self, order):
        return {
                    'login': order.user_id.name,
                    'insz_or_bis_number': order.user_id.insz_or_bis_number,
                    'revenue': order.amount_total,
                    'revenue_per_category': {},
                    'first_ticket_time': order.blackbox_pos_receipt_time,
                    'last_ticket_time': False,
                }

    def _build_order_data_list_for_user_report(self):
        sorted_orders = sorted(self.order_ids, key=lambda o: o.user_id.id)
        return groupby(sorted_orders, key=lambda o: o.user_id.id)

    def get_user_report_data(self):
        data = {}
        i = 0
        if self.config_id.blackbox_pos_production_id:
            for user, orders in self._build_order_data_list_for_user_report():
                for order in sorted(orders, key=lambda o: o.blackbox_pos_receipt_time):
                    if order.plu_hash == 'cf44878a':
                        total_sold_per_category = {}
                        data[i] = self._get_order_data_for_user_report(order)

                        current = data[i]
                    elif order.plu_hash == '142164ed':
                        current['last_ticket_time'] = order.blackbox_pos_receipt_time
                        i += 1
                    else:
                        current['revenue'] += order.amount_total
                        for line in order.lines:
                            key = line.product_id.pos_categ_id.name or "None"
                            if key in total_sold_per_category:
                                total_sold_per_category[key] += line.price_subtotal_incl
                            else:
                                total_sold_per_category[key] = line.price_subtotal_incl
                        current['revenue_per_category'] = list(total_sold_per_category.items())
        return data

    def action_report_journal_file(self):
        self.ensure_one()
        pos = self.config_id
        if not pos.blackbox_pos_production_id:
            raise UserError(_("PoS %s is not a certified PoS") % pos.name)
        return {
            'type': 'ir.actions.act_url',
            'url': "/journal_file/" + pos.blackbox_pos_production_id,
            'target': 'self',
        }


class pos_order(models.Model):
    _inherit = 'pos.order'

    blackbox_date = fields.Char("Fiscal Data Module date", help="Date returned by the Fiscal Data Module.", readonly=True)
    blackbox_time = fields.Char("Fiscal Data Module time", help="Time returned by the Fiscal Data Module.", readonly=True)
    blackbox_pos_receipt_time = fields.Datetime("Receipt time", readonly=True)
    blackbox_ticket_counters = fields.Char("Fiscal Data Module ticket counters", help="Ticket counter returned by the Fiscal Data Module (format: counter / total event type)", readonly=True)
    blackbox_unique_fdm_production_number = fields.Char("Fiscal Data Module ID", help="Unique ID of the blackbox that handled this order", readonly=True)
    blackbox_vsc_identification_number = fields.Char("VAT Signing Card ID", help="Unique ID of the VAT signing card that handled this order", readonly=True)
    blackbox_signature = fields.Char("Electronic signature", help="Electronic signature returned by the Fiscal Data Module", readonly=True)
    blackbox_tax_category_a = fields.Float(readonly=True)
    blackbox_tax_category_b = fields.Float(readonly=True)
    blackbox_tax_category_c = fields.Float(readonly=True)
    blackbox_tax_category_d = fields.Float(readonly=True)

    plu_hash = fields.Char(help="Eight last characters of PLU hash")
    pos_version = fields.Char(help="Version of Odoo that created the order")
    pos_production_id = fields.Char(help="Unique ID of Odoo that created this order")
    terminal_id = fields.Char(help="Unique ID of the terminal that created this order")
    hash_chain = fields.Char()

    def _set_log_description(self, order):
        lines = "Lignes de commande: "
        if order.lines:
            lines += "\n* " + "\n* ".join([
                "%s x %s: %s" % (l.qty, l.product_id.name, l.price_subtotal_incl)
                for l in order.lines
            ])
        description = """
        NORMAL SALES
        Date: {create_date}
        Réf: {pos_reference}
        Vendeur: {user_id}
        {lines}
        Total: {total}
        Compteur Ticket: {ticket_counters}
        Hash: {hash}
        POS Version: {pos_version}
        FDM ID: {fdm_id}
        POS ID: {pos_id}
        """.format(
            create_date=order.create_date,
            user_id=order.user_id.name,
            lines=lines,
            total=order.amount_total,
            pos_reference=order.pos_reference,
            hash=order.hash_chain,
            pos_version=order.pos_version,
            ticket_counters=order.blackbox_ticket_counters,
            fdm_id=order.blackbox_unique_fdm_production_number,
            pos_id=order.pos_production_id,
        )
        return description

    @api.model
    def create(self, values):
        pos_session = self.env["pos.session"].browse(values.get("session_id"))

        if pos_session.config_id.blackbox_pos_production_id and not values.get("blackbox_signature"):
            raise UserError(_("Manually creating registered orders is not allowed."))

        order = super(pos_order, self).create(values)
        if order.blackbox_signature:
            description = self._set_log_description(order)
            self.env["pos_blackbox_be.log"].sudo().create(description, "create", self._name, order.pos_reference)

        return order

    def unlink(self):
        for order in self:
            if order.config_id.blackbox_pos_production_id:
                raise UserError(_('Deleting of registered orders is not allowed.'))

        return super(pos_order, self).unlink()

    def write(self, values):
        for order in self:
            if order.config_id.blackbox_pos_production_id and order.state != 'draft':
                white_listed_fields = ['state', 'account_move', 'picking_id',
                                       'invoice_id']

                for field in values:
                    if field not in white_listed_fields:
                        raise UserError(_("Modifying registered orders is not allowed."))

        return super(pos_order, self).write(values)

    def refund(self):
        for order in self:
            if order.config_id.blackbox_pos_production_id:
                raise UserError(_("Refunding registered orders is not allowed."))

        return super(pos_order, self).refund()

    @api.model
    def _order_fields(self, ui_order):
        fields = super(pos_order, self)._order_fields(ui_order)

        fields.update({
            'blackbox_date': ui_order.get('blackbox_date'),
            'blackbox_time': ui_order.get('blackbox_time'),
            'blackbox_pos_receipt_time': ui_order.get('blackbox_pos_receipt_time'),
            'blackbox_ticket_counters': ui_order.get('blackbox_ticket_counters'),
            'blackbox_unique_fdm_production_number': ui_order.get('blackbox_unique_fdm_production_number'),
            'blackbox_vsc_identification_number': ui_order.get('blackbox_vsc_identification_number'),
            'blackbox_signature': ui_order.get('blackbox_signature'),
            'blackbox_tax_category_a': ui_order.get('blackbox_tax_category_a'),
            'blackbox_tax_category_b': ui_order.get('blackbox_tax_category_b'),
            'blackbox_tax_category_c': ui_order.get('blackbox_tax_category_c'),
            'blackbox_tax_category_d': ui_order.get('blackbox_tax_category_d'),
            'plu_hash': ui_order.get('blackbox_plu_hash'),
            'pos_version': ui_order.get('blackbox_pos_version'),
            'pos_production_id': ui_order.get('blackbox_pos_production_id'),
            'terminal_id': ui_order.get('blackbox_terminal_id'),
            'hash_chain': ui_order.get('blackbox_hash_chain'),
        })

        return fields

    @api.model
    def create_from_ui(self, orders, draft=False):
        # this will call pos_order_pro_forma.create_from_ui when required
        pro_forma_orders = [order['data'] for order in orders if order['data'].get('blackbox_pro_forma')]

        # filter the pro_forma orders out of the orders list
        regular_orders = [order for order in orders if not order['data'].get('blackbox_pro_forma')]

        # deal with the pro forma orders
        self.env['pos.order_pro_forma'].create_from_ui(pro_forma_orders)

        # only return regular order ids, shouldn't care about pro forma in the POS anyway
        return super(pos_order, self).create_from_ui(regular_orders)

class pos_make_payment(models.TransientModel):
    _inherit = 'pos.make.payment'

    def check(self):
        order = self.env['pos.order'].browse(self.env.context.get('active_id'))

        if order.config_id.blackbox_pos_production_id:
            raise UserError(_("Adding additional payments to registered orders is not allowed."))

        return super(pos_make_payment, self).check()

class pos_order_line(models.Model):
    _inherit = 'pos.order.line'

    vat_letter = fields.Selection([('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')])

    def write(self, values):
        if values.get('vat_letter'):
            raise UserError(_("Can't modify fields related to the Fiscal Data Module."))

        return super(pos_order_line, self).write(values)

class pos_order_line_pro_forma(models.Model):
    _name = 'pos.order_line_pro_forma'  # needs to be a new class
    _inherit = 'pos.order.line'
    _description = 'Order line of a pro forma order'

    order_id = fields.Many2one('pos.order_pro_forma')

    @api.model
    def create(self, values):
        # the pos.order.line create method consider 'order_id' is a pos.order
        # override to bypass it and generate a name
        if values.get('order_id') and not values.get('name'):
            name = self.env['pos.order_pro_forma'].browse(values['order_id']).name
            values['name'] = "%s-%s" % (name, values.get('id'))
        return super(pos_order_line_pro_forma, self).create(values)


class pos_order_pro_forma(models.Model):
    _name = 'pos.order_pro_forma'
    _description = 'Model for pro forma order'

    def _default_session(self):
        so = self.env['pos.session']
        session_ids = so.search([('state', '=', 'opened'), ('user_id', '=', self.env.uid)])
        return session_ids and session_ids[0] or False

    def _default_pricelist(self):
        session_ids = self._default_session()
        if session_ids:
            session_record = self.env['pos.session'].browse(session_ids.id)
            return session_record.config_id.pricelist_id or False
        return False

    name = fields.Char('Order Ref', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env['res.users'].browse(self.env.uid).company_id.id, readonly=True)
    date_order = fields.Datetime('Order Date', readonly=True)
    create_date = fields.Datetime(string="Pro Forma Creation")
    user_id = fields.Many2one('res.users', 'Salesman', help="Person who uses the cash register. It can be a reliever, a student or an interim employee.", readonly=True)
    amount_total = fields.Float(readonly=True)
    lines = fields.One2many('pos.order_line_pro_forma', 'order_id', 'Order Lines', readonly=True, copy=True)
    pos_reference = fields.Char('Receipt Ref', readonly=True)
    session_id = fields.Many2one('pos.session', 'Session', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Customer', readonly=True)
    config_id = fields.Many2one('pos.config', related='session_id.config_id', readonly=True)
    pricelist_id = fields.Many2one('product.pricelist', 'Pricelist', default=_default_pricelist, readonly=True)
    fiscal_position_id = fields.Many2one('account.fiscal.position', 'Fiscal Position', readonly=True)
    table_id = fields.Many2one('restaurant.table', 'Table', readonly=True)
    currency_id = fields.Many2one(related='session_id.currency_id')

    blackbox_date = fields.Char("Fiscal Data Module date", help="Date returned by the Fiscal Data Module.", readonly=True)
    blackbox_time = fields.Char("Fiscal Data Module time", help="Time returned by the Fiscal Data Module.", readonly=True)
    blackbox_pos_receipt_time = fields.Datetime("Receipt time", readonly=True)
    blackbox_ticket_counters = fields.Char("Fiscal Data Module ticket counters", help="Ticket counter returned by the Fiscal Data Module (format: counter / total event type)", readonly=True)
    blackbox_unique_fdm_production_number = fields.Char("Fiscal Data Module ID", help="Unique ID of the blackbox that handled this order", readonly=True)
    blackbox_vsc_identification_number = fields.Char("VAT Signing Card ID", help="Unique ID of the VAT signing card that handled this order", readonly=True)
    blackbox_signature = fields.Char("Electronic signature", help="Electronic signature returned by the Fiscal Data Module", readonly=True)
    blackbox_tax_category_a = fields.Float(readonly=True)
    blackbox_tax_category_b = fields.Float(readonly=True)
    blackbox_tax_category_c = fields.Float(readonly=True)
    blackbox_tax_category_d = fields.Float(readonly=True)

    plu_hash = fields.Char(help="Eight last characters of PLU hash", readonly=True)
    pos_version = fields.Char(help="Version of Odoo that created the order", readonly=True)
    pos_production_id = fields.Char(help="Unique ID of Odoo that created this order", readonly=True)
    terminal_id = fields.Char(help="Unique ID of the POS that created this order", readonly=True)
    hash_chain = fields.Char()

    def _set_log_description(self, order):
        lines = "Lignes de commande: "
        if order.lines:
            lines += "\n* " + "\n* ".join([
                "%s x %s: %s" % (l.qty, l.product_id.name, l.price_subtotal_incl)
                for l in order.lines
            ])
        description = """
        PRO FORMA SALES
        Date: {create_date}
        Réf: {pos_reference}
        Vendeur: {user_id}
        {lines}
        Total: {total}
        Compteur Ticket: {ticket_counters}
        Hash: {hash}
        POS Version: {pos_version}
        FDM ID: {fdm_id}
        POS ID: {pos_id}
        """.format(
            create_date=order.create_date,
            user_id=order.user_id.name,
            lines=lines,
            total=order.amount_total,
            pos_reference=order.pos_reference,
            hash=order.hash_chain,
            pos_version=order.pos_version,
            ticket_counters=order.blackbox_ticket_counters,
            fdm_id=order.blackbox_unique_fdm_production_number,
            pos_id=order.pos_production_id,
        )
        return description

    def set_values(self, ui_order):
        return {
            'user_id': ui_order['user_id'] or False,
            'session_id': ui_order['pos_session_id'],
            'pos_reference': ui_order['name'],
            'lines': [self.env['pos.order_line_pro_forma']._order_line_fields(l) for l in ui_order['lines']] if
            ui_order['lines'] else False,
            'partner_id': ui_order['partner_id'] or False,
            'date_order': parser.parse(ui_order['creation_date']).strftime("%Y-%m-%d %H:%M:%S"),
            'fiscal_position_id': ui_order['fiscal_position_id'],
            'blackbox_date': ui_order.get('blackbox_date'),
            'blackbox_time': ui_order.get('blackbox_time'),
            'blackbox_pos_receipt_time': parser.parse(ui_order.get('blackbox_pos_receipt_time')).strftime(
                "%Y-%m-%d %H:%M:%S"),
            'amount_total': ui_order.get('blackbox_amount_total'),
            'blackbox_ticket_counters': ui_order.get('blackbox_ticket_counters'),
            'blackbox_unique_fdm_production_number': ui_order.get('blackbox_unique_fdm_production_number'),
            'blackbox_vsc_identification_number': ui_order.get('blackbox_vsc_identification_number'),
            'blackbox_signature': ui_order.get('blackbox_signature'),
            'blackbox_tax_category_a': ui_order.get('blackbox_tax_category_a'),
            'blackbox_tax_category_b': ui_order.get('blackbox_tax_category_b'),
            'blackbox_tax_category_c': ui_order.get('blackbox_tax_category_c'),
            'blackbox_tax_category_d': ui_order.get('blackbox_tax_category_d'),
            'plu_hash': ui_order.get('blackbox_plu_hash'),
            'pos_version': ui_order.get('blackbox_pos_version'),
            'pos_production_id': ui_order.get('blackbox_pos_production_id'),
            'terminal_id': ui_order.get('blackbox_terminal_id'),
            'table_id': ui_order.get('table_id'),
            'hash_chain': ui_order.get('blackbox_hash_chain')
        }

    @api.model
    def create_from_ui(self, orders):
        for ui_order in orders:
            values = self.set_values(ui_order)
            # set name based on the sequence specified on the config
            session = self.env['pos.session'].browse(values['session_id'])
            values['name'] = session.config_id.sequence_id._next()

            order = self.create(values)
            description = self._set_log_description(order)
            self.env["pos_blackbox_be.log"].sudo().create(description, "create", self._name, order.pos_reference)


class pos_blackbox_be_log(models.Model):
    _name = 'pos_blackbox_be.log'
    _description = 'Track every changes made while using the Blackbox'
    _order = 'id desc'

    user = fields.Many2one('res.users', readonly=True)
    action = fields.Selection([('create', 'create'), ('modify', 'modify'), ('delete', 'delete')], readonly=True)
    date = fields.Datetime(default=fields.Datetime.now, readonly=True)
    model_name = fields.Char(readonly=True)
    record_name = fields.Char(readonly=True)
    description = fields.Char(readonly=True)

    def create(self, values, action, model_name, record_name):
        if not self.env.context.get('install_mode'):
            log_values = {
                'user': self.env.uid,
                'action': action,
                'model_name': model_name,
                'record_name': record_name,
                'description': str(values)
            }

            return super(pos_blackbox_be_log, self).create(log_values)

        return None

    def write(self, values):
        raise UserError(_("Can't modify the log book."))

    def unlink(self):
        raise UserError(_("Can't modify the log book."))

class product_template(models.Model):
    _inherit = 'product.template'

    @api.model
    def create(self, values):
        self.env['pos_blackbox_be.log'].sudo().create(values, "create", self._name, values.get('name'))

        return super(product_template, self).create(values)

    def write(self, values):
        work_in = self.env.ref('pos_blackbox_be.product_product_work_in')
        work_out = self.env.ref('pos_blackbox_be.product_product_work_out')

        if not self.env.context.get('install_mode'):
            for product in self.ids:
                if product == work_in.id or product == work_out.id:
                    raise UserError(_('Modifying this product is not allowed.'))

        for product in self:
            self.env['pos_blackbox_be.log'].sudo().create(values, "modify", product._name, product.name)

        return super(product_template, self).write(values)

    def unlink(self):
        ir_model_data = self.env['ir.model.data']
        work_in = ir_model_data.xmlid_to_object('pos_blackbox_be.product_product_work_in').product_tmpl_id.id
        work_out = ir_model_data.xmlid_to_object('pos_blackbox_be.product_product_work_out').product_tmpl_id.id

        for product in self.ids:
            if product == work_in or product == work_out:
                raise UserError(_('Deleting this product is not allowed.'))

        for product in self:
            self.env['pos_blackbox_be.log'].sudo().create({}, "delete", product._name, product.name)

        return super(product_template, self).unlink()

    @api.model
    def _remove_availibility_all_but_blackbox(self):
        """ Remove all products from the point of sale that were not create by this module

        Useful in demo only.
        Only a subset of demo products should be displayed for the certification process
        """
        blackbox_products = self.env['ir.model.data'].search([
            ('module', '=', 'pos_blackbox_be'), ('model', '=', 'product.template')
        ])
        tip_products = self.env['pos.config'].search([]).mapped('tip_product_id').ids
        to_keep = blackbox_products.mapped('res_id') + tip_products
        other_products = self.search([
            ('id', 'not in', to_keep), ('available_in_pos', '=', True)
        ])
        return other_products.write({'available_in_pos': False})


class module(models.Model):
    _inherit = 'ir.module.module'

    def module_uninstall(self):
        for module_to_remove in self:
            if module_to_remove.name == "pos_blackbox_be":
                raise UserError(_("This module is not allowed to be removed."))

        return super(module, self).module_uninstall()


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def set_tax_on_work_in_out(self):
        existing_companies = self.env['res.company'].sudo().search([])
        for company in existing_companies:
            if company.chart_template_id == self.env.ref('l10n_be.l10nbe_chart_template'):
                work_in = self.env.ref('pos_blackbox_be.product_product_work_in')
                work_out = self.env.ref('pos_blackbox_be.product_product_work_out')
                taxes = self.env['account.tax'].sudo().with_context(active_test=False).search([('amount', '=', 0.0), ('type_tax_use', '=', 'sale'), ('name', '=', '0%'), ('company_id', '=', company.id)])
                if not taxes.active:
                    taxes.active = True
                work_in.with_context(force_company=company.id).write({'taxes_id': [(4, taxes.id)]})
                work_out.with_context(force_company=company.id).write({'taxes_id': [(4, taxes.id)]})


class AccountChartTemplate(models.Model):
    _inherit = "account.chart.template"

    def _load(self, sale_tax_rate, purchase_tax_rate, company):
        super(AccountChartTemplate, self)._load(sale_tax_rate, purchase_tax_rate, company)
        if self == self.env.ref('l10n_be.l10nbe_chart_template'):
            work_in = self.env.ref('pos_blackbox_be.product_product_work_in')
            work_out = self.env.ref('pos_blackbox_be.product_product_work_out')
            taxes = self.env['account.tax'].sudo().with_context(active_test=False).search([('amount', '=', 0.0), ('type_tax_use', '=', 'sale'), ('name', '=', '0%'), ('company_id', '=', company.id)])
            if not taxes.active:
                taxes.active = True
            work_in.with_context(install_mode=True, force_company=company.id).write({'taxes_id': [(4, taxes.id)]})
            work_out.with_context(install_mode=True, force_company=company.id).write({'taxes_id': [(4, taxes.id)]})
