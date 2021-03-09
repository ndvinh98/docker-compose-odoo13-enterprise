# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools.translate import _
from dateutil import parser
from itertools import groupby


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    insz_or_bis_number = fields.Char("INSZ or BIS number", readonly=True)
    clocked_session_ids = fields.Many2many(
        'pos.session',
        'employees_session_clocking_info',
        string='Users Clocked In',
        help='This is a technical field used for tracking the status of the session for each employees.',
    )

    @api.constrains('insz_or_bis_number')
    def _check_insz_or_bis_number(self):
        for emp in self:
            if emp.insz_or_bis_number and (len(emp.insz_or_bis_number) != 11 or not emp.insz_or_bis_number.isdigit()):
                raise ValidationError(_("The INSZ or BIS number has to consist of 11 numerical digits."))

    @api.model
    def init_INSZ_number(self):
        employees = self.env['hr.employee'].search([('user_id', '!=', False)])
        for emp in employees:
            emp.insz_or_bis_number = emp.user_id.insz_or_bis_number


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def _check_employee_insz_or_bis_number(self):
        if self.module_pos_hr and self.blackbox_pos_production_id:
            emp_list = []
            for emp in self.employee_ids if self.employee_ids else self.env['hr.employee'].search([]):
                if not emp.insz_or_bis_number:
                    emp_list.append(emp.name)
            if not self.env.user.employee_id.insz_or_bis_number:
                emp_list.append(self.env.user.name)

            if len(emp_list) > 0:
                raise ValidationError(_(", ".join(str(emp) for emp in emp_list) + " must have an INSZ or BIS number."))

    def open_session_cb(self):
        self._check_employee_insz_or_bis_number()
        return super(PosConfig, self).open_session_cb()


class PosSession(models.Model):
    _inherit = 'pos.session'

    employees_clocked_ids = fields.Many2many(
        'hr.employee',
        'employees_session_clocking_info',
        string='Employees Clocked In',
        help='This is a technical field used for tracking the status of the session for each employees.',
    )

    def get_employee_session_work_status(self, employee_id):
        if employee_id in self.employees_clocked_ids.ids:
            return True
        return False

    def set_employee_session_work_status(self, user_id, status):
        if status:
            self.write({'employees_clocked_ids': [(4, user_id)]})
        else:
            self.write({'employees_clocked_ids': [(3, user_id)]})
        return self.employees_clocked_ids.ids

    def _get_order_data_for_user_report(self, order):
        ret = super(PosSession, self)._get_order_data_for_user_report(order)
        if order.employee_id:
            ret['insz_or_bis_number'] = order.employee_id.insz_or_bis_number
        return ret

    def _build_order_data_list_for_user_report(self):
        sorted_orders = sorted(self.order_ids, key=lambda o: o.employee_id.id or o.user_id.id)
        return groupby(sorted_orders, key=lambda o: o.employee_id.id or o.user_id.id)


class pos_order(models.Model):
    _inherit = 'pos.order'

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
                user_id=order.employee_id.name or order.user_id.name,
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


class pos_order_pro_forma(models.Model):
    _inherit = 'pos.order_pro_forma'

    employee_id = fields.Many2one('hr.employee')

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
            'hash_chain': ui_order.get('blackbox_hash_chain'),
            'employee_id': ui_order.get('employee_id')
        }

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
                user_id=order.employee_id.name or order.user_id.name,
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
