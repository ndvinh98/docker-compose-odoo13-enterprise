# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.addons.hr_payroll.models.browsable_object import BrowsableObject, InputLine, WorkedDays, Payslips
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round, date_utils
from odoo.tools.misc import format_date
from odoo.tools.safe_eval import safe_eval


class HrPayslip(models.Model):
    _name = 'hr.payslip'
    _description = 'Pay Slip'
    _inherit = ['mail.thread.cc', 'mail.activity.mixin']
    _order = 'date_to desc'

    struct_id = fields.Many2one('hr.payroll.structure', string='Structure',
        readonly=True, states={'draft': [('readonly', False)], 'verify': [('readonly', False)]},
        help='Defines the rules that have to be applied to this payslip, accordingly '
             'to the contract chosen. If you let empty the field contract, this field isn\'t '
             'mandatory anymore and thus the rules applied will be all the rules set on the '
             'structure of all contracts of the employee valid for the chosen period')
    name = fields.Char(string='Payslip Name', readonly=True, required=True,
        states={'draft': [('readonly', False)], 'verify': [('readonly', False)]})
    number = fields.Char(string='Reference', readonly=True, copy=False,
        states={'draft': [('readonly', False)], 'verify': [('readonly', False)]})
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, readonly=True,
        states={'draft': [('readonly', False)], 'verify': [('readonly', False)]}, domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    date_from = fields.Date(string='From', readonly=True, required=True,
        default=lambda self: fields.Date.to_string(date.today().replace(day=1)), states={'draft': [('readonly', False)], 'verify': [('readonly', False)]})
    date_to = fields.Date(string='To', readonly=True, required=True,
        default=lambda self: fields.Date.to_string((datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()),
        states={'draft': [('readonly', False)], 'verify': [('readonly', False)]})
    # this is chaos: 4 states are defined, 3 are used ('verify' isn't) and 5 exist ('confirm' seems to have existed)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('verify', 'Waiting'),
        ('done', 'Done'),
        ('cancel', 'Rejected'),
    ], string='Status', index=True, readonly=True, copy=False, default='draft',
        help="""* When the payslip is created the status is \'Draft\'
                \n* If the payslip is under verification, the status is \'Waiting\'.
                \n* If the payslip is confirmed then status is set to \'Done\'.
                \n* When user cancel payslip the status is \'Rejected\'.""")
    line_ids = fields.One2many('hr.payslip.line', 'slip_id', string='Payslip Lines', readonly=True,
        states={'draft': [('readonly', False)], 'verify': [('readonly', False)]})
    company_id = fields.Many2one('res.company', string='Company', readonly=True, copy=False, required=True,
        default=lambda self: self.env.company,
        states={'draft': [('readonly', False)], 'verify': [('readonly', False)]})
    worked_days_line_ids = fields.One2many('hr.payslip.worked_days', 'payslip_id',
        string='Payslip Worked Days', copy=True, readonly=True,
        states={'draft': [('readonly', False)], 'verify': [('readonly', False)]})
    input_line_ids = fields.One2many('hr.payslip.input', 'payslip_id', string='Payslip Inputs',
        readonly=True, states={'draft': [('readonly', False)], 'verify': [('readonly', False)]})
    paid = fields.Boolean(string='Made Payment Order ? ', readonly=True, copy=False,
        states={'draft': [('readonly', False)], 'verify': [('readonly', False)]})
    note = fields.Text(string='Internal Note', readonly=True, states={'draft': [('readonly', False)], 'verify': [('readonly', False)]})
    contract_id = fields.Many2one('hr.contract', string='Contract', readonly=True,
        states={'draft': [('readonly', False)], 'verify': [('readonly', False)]}, domain="[('company_id', '=', company_id)]")
    credit_note = fields.Boolean(string='Credit Note', readonly=True,
        states={'draft': [('readonly', False)], 'verify': [('readonly', False)]},
        help="Indicates this payslip has a refund of another")
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Batch Name', readonly=True,
        copy=False, states={'draft': [('readonly', False)], 'verify': [('readonly', False)]}, ondelete='cascade',
        domain="[('company_id', '=', company_id)]")
    compute_date = fields.Date('Computed On')
    basic_wage = fields.Monetary(compute='_compute_basic_net')
    net_wage = fields.Monetary(compute='_compute_basic_net')
    currency_id = fields.Many2one(related='contract_id.currency_id')
    warning_message = fields.Char(readonly=True)

    @api.onchange('worked_days_line_ids', 'input_line_ids')
    def _onchange_worked_days_inputs(self):
        if self.line_ids and self.state in ['draft', 'verify']:
            values = [(5, 0, 0)] + [(0, 0, line_vals) for line_vals in self._get_payslip_lines()]
            self.update({'line_ids': values})

    def _compute_basic_net(self):
        for payslip in self:
            payslip.basic_wage = payslip._get_salary_line_total('BASIC')
            payslip.net_wage = payslip._get_salary_line_total('NET')

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        if any(self.filtered(lambda payslip: payslip.date_from > payslip.date_to)):
            raise ValidationError(_("Payslip 'Date From' must be earlier 'Date To'."))

    def action_payslip_draft(self):
        return self.write({'state': 'draft'})

    def action_payslip_done(self):
        if any(slip.state == 'cancel' for slip in self):
            raise ValidationError(_("You can't validate a cancelled payslip."))
        self.write({'state' : 'done'})
        self.mapped('payslip_run_id').action_close()
        if self.env.context.get('payslip_generate_pdf'):
            for payslip in self:
                if not payslip.struct_id or not payslip.struct_id.report_id:
                    report = self.env.ref('hr_payroll.action_report_payslip', False)
                else:
                    report = payslip.struct_id.report_id
                pdf_content, content_type = report.render_qweb_pdf(payslip.id)
                if payslip.struct_id.report_id.print_report_name:
                    pdf_name = safe_eval(payslip.struct_id.report_id.print_report_name, {'object': payslip})
                else:
                    pdf_name = _("Payslip")
                self.env['ir.attachment'].create({
                    'name': pdf_name,
                    'type': 'binary',
                    'datas': base64.encodestring(pdf_content),
                    'res_model': payslip._name,
                    'res_id': payslip.id
                })


    def action_payslip_cancel(self):
        if self.filtered(lambda slip: slip.state == 'done'):
            raise UserError(_("Cannot cancel a payslip that is done."))
        self.write({'state': 'cancel'})
        self.mapped('payslip_run_id').action_close()

    def refund_sheet(self):
        for payslip in self:
            copied_payslip = payslip.copy({'credit_note': True, 'name': _('Refund: ') + payslip.name})
            copied_payslip.compute_sheet()
            copied_payslip.action_payslip_done()
        formview_ref = self.env.ref('hr_payroll.view_hr_payslip_form', False)
        treeview_ref = self.env.ref('hr_payroll.view_hr_payslip_tree', False)
        return {
            'name': ("Refund Payslip"),
            'view_mode': 'tree, form',
            'view_id': False,
            'res_model': 'hr.payslip',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'domain': "[('id', 'in', %s)]" % copied_payslip.ids,
            'views': [(treeview_ref and treeview_ref.id or False, 'tree'), (formview_ref and formview_ref.id or False, 'form')],
            'context': {}
        }

    @api.model
    def create(self, vals):
        contract_id = vals.get('contract_id')
        if contract_id and not vals.get('struct_id'):
            vals['struct_id'] = self.env['hr.contract'].browse(contract_id).structure_type_id.default_struct_id.id
        res = super(HrPayslip, self).create(vals)
        return res

    def unlink(self):
        if any(self.filtered(lambda payslip: payslip.state not in ('draft', 'cancel'))):
            raise UserError(_('You cannot delete a payslip which is not draft or cancelled!'))
        return super(HrPayslip, self).unlink()

    def compute_sheet(self):
        for payslip in self.filtered(lambda slip: slip.state not in ['cancel', 'done']):
            number = payslip.number or self.env['ir.sequence'].next_by_code('salary.slip')
            # delete old payslip lines
            payslip.line_ids.unlink()
            lines = [(0, 0, line) for line in payslip._get_payslip_lines()]
            payslip.write({'line_ids': lines, 'number': number, 'state': 'verify', 'compute_date': fields.Date.today()})
        return True

    def _round_days(self, work_entry_type, days):
        if work_entry_type.round_days != 'NO':
            precision_rounding = 0.5 if work_entry_type.round_days == "HALF" else 1
            day_rounded = float_round(days, precision_rounding=precision_rounding, rounding_method=work_entry_type.round_days_type)
            return day_rounded
        return days

    def _get_worked_day_lines(self):
        """
        :returns: a list of dict containing the worked days values that should be applied for the given payslip
        """
        res = []
        # fill only if the contract as a working schedule linked
        self.ensure_one()
        contract = self.contract_id
        if contract.resource_calendar_id:
            paid_amount = self._get_contract_wage()
            unpaid_work_entry_types = self.struct_id.unpaid_work_entry_type_ids.ids

            work_hours = contract._get_work_hours(self.date_from, self.date_to)
            total_hours = sum(work_hours.values()) or 1
            work_hours_ordered = sorted(work_hours.items(), key=lambda x: x[1])
            biggest_work = work_hours_ordered[-1][0] if work_hours_ordered else 0
            add_days_rounding = 0
            for work_entry_type_id, hours in work_hours_ordered:
                work_entry_type = self.env['hr.work.entry.type'].browse(work_entry_type_id)
                is_paid = work_entry_type_id not in unpaid_work_entry_types
                calendar = contract.resource_calendar_id
                days = round(hours / calendar.hours_per_day, 5) if calendar.hours_per_day else 0
                if work_entry_type_id == biggest_work:
                    days += add_days_rounding
                day_rounded = self._round_days(work_entry_type, days)
                add_days_rounding += (days - day_rounded)
                attendance_line = {
                    'sequence': work_entry_type.sequence,
                    'work_entry_type_id': work_entry_type_id,
                    'number_of_days': day_rounded,
                    'number_of_hours': hours,
                    'amount': hours * paid_amount / total_hours if is_paid else 0,
                }
                res.append(attendance_line)
        return res

    def _get_base_local_dict(self):
        return {
            'float_round': float_round
        }

    def _get_payslip_lines(self):
        def _sum_salary_rule_category(localdict, category, amount):
            if category.parent_id:
                localdict = _sum_salary_rule_category(localdict, category.parent_id, amount)
            localdict['categories'].dict[category.code] = localdict['categories'].dict.get(category.code, 0) + amount
            return localdict

        self.ensure_one()
        result = {}
        rules_dict = {}
        worked_days_dict = {line.code: line for line in self.worked_days_line_ids if line.code}
        inputs_dict = {line.code: line for line in self.input_line_ids if line.code}

        employee = self.employee_id
        contract = self.contract_id

        localdict = {
            **self._get_base_local_dict(),
            **{
                'categories': BrowsableObject(employee.id, {}, self.env),
                'rules': BrowsableObject(employee.id, rules_dict, self.env),
                'payslip': Payslips(employee.id, self, self.env),
                'worked_days': WorkedDays(employee.id, worked_days_dict, self.env),
                'inputs': InputLine(employee.id, inputs_dict, self.env),
                'employee': employee,
                'contract': contract
            }
        }
        for rule in sorted(self.struct_id.rule_ids, key=lambda x: x.sequence):
            localdict.update({
                'result': None,
                'result_qty': 1.0,
                'result_rate': 100})
            if rule._satisfy_condition(localdict):
                amount, qty, rate = rule._compute_rule(localdict)
                #check if there is already a rule computed with that code
                previous_amount = rule.code in localdict and localdict[rule.code] or 0.0
                #set/overwrite the amount computed for this rule in the localdict
                tot_rule = amount * qty * rate / 100.0
                localdict[rule.code] = tot_rule
                rules_dict[rule.code] = rule
                # sum the amount for its salary category
                localdict = _sum_salary_rule_category(localdict, rule.category_id, tot_rule - previous_amount)
                # create/overwrite the rule in the temporary results
                result[rule.code] = {
                    'sequence': rule.sequence,
                    'code': rule.code,
                    'name': rule.name,
                    'note': rule.note,
                    'salary_rule_id': rule.id,
                    'contract_id': contract.id,
                    'employee_id': employee.id,
                    'amount': amount,
                    'quantity': qty,
                    'rate': rate,
                    'slip_id': self.id,
                }
        return result.values()

    @api.onchange('employee_id', 'struct_id', 'contract_id', 'date_from', 'date_to')
    def _onchange_employee(self):
        if (not self.employee_id) or (not self.date_from) or (not self.date_to):
            return

        employee = self.employee_id
        date_from = self.date_from
        date_to = self.date_to

        self.company_id = employee.company_id
        if not self.contract_id or self.employee_id != self.contract_id.employee_id: # Add a default contract if not already defined
            contracts = employee._get_contracts(date_from, date_to)

            if not contracts or not contracts[0].structure_type_id.default_struct_id:
                self.contract_id = False
                self.struct_id = False
                return
            self.contract_id = contracts[0]
            self.struct_id = contracts[0].structure_type_id.default_struct_id

        payslip_name = self.struct_id.payslip_name or _('Salary Slip')
        self.name = '%s - %s - %s' % (payslip_name, self.employee_id.name or '', format_date(self.env, self.date_from, date_format="MMMM y"))

        if date_to > date_utils.end_of(fields.Date.today(), 'month'):
            self.warning_message = _("This payslip can be erroneous! Work entries may not be generated for the period from %s to %s." %
                (date_utils.add(date_utils.end_of(fields.Date.today(), 'month'), days=1), date_to))
        else:
            self.warning_message = False

        self.worked_days_line_ids = self._get_new_worked_days_lines()

    def _get_new_worked_days_lines(self):
        if self.struct_id.use_worked_day_lines:
            # computation of the salary worked days
            worked_days_line_values = self._get_worked_day_lines()
            worked_days_lines = self.worked_days_line_ids.browse([])
            for r in worked_days_line_values:
                worked_days_lines |= worked_days_lines.new(r)
            return worked_days_lines
        else:
            return [(5, False, False)]

    def _get_salary_line_total(self, code):
        lines = self.line_ids.filtered(lambda line: line.code == code)
        return sum([line.total for line in lines])

    def action_print_payslip(self):
        return {
            'name': 'Payslip',
            'type': 'ir.actions.act_url',
            'url': '/print/payslips?list_ids=%(list_ids)s' % {'list_ids': ','.join(str(x) for x in self.ids)},
        }

    def _get_contract_wage(self):
        self.ensure_one()
        return self.contract_id.wage

    def _get_paid_amount(self):
        self.ensure_one()
        if not self.worked_days_line_ids:
            return self._get_contract_wage()
        total_amount = 0
        for line in self.worked_days_line_ids:
            total_amount += line.amount
        return total_amount

    def _get_unpaid_amount(self):
        self.ensure_one()
        return self._get_contract_wage() - self._get_paid_amount()


class HrPayslipLine(models.Model):
    _name = 'hr.payslip.line'
    _description = 'Payslip Line'
    _order = 'contract_id, sequence, code'

    name = fields.Char(required=True, translate=True)
    note = fields.Text(string='Description')
    sequence = fields.Integer(required=True, index=True, default=5,
                              help='Use to arrange calculation sequence')
    code = fields.Char(required=True,
                       help="The code of salary rules can be used as reference in computation of other rules. "
                       "In that case, it is case sensitive.")
    slip_id = fields.Many2one('hr.payslip', string='Pay Slip', required=True, ondelete='cascade')
    salary_rule_id = fields.Many2one('hr.salary.rule', string='Rule', required=True)
    contract_id = fields.Many2one('hr.contract', string='Contract', required=True, index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    rate = fields.Float(string='Rate (%)', digits='Payroll Rate', default=100.0)
    amount = fields.Float(digits='Payroll')
    quantity = fields.Float(digits='Payroll', default=1.0)
    total = fields.Float(compute='_compute_total', string='Total', digits='Payroll', store=True)

    amount_select = fields.Selection(related='salary_rule_id.amount_select', readonly=True)
    amount_fix = fields.Float(related='salary_rule_id.amount_fix', readonly=True)
    amount_percentage = fields.Float(related='salary_rule_id.amount_percentage', readonly=True)
    appears_on_payslip = fields.Boolean(related='salary_rule_id.appears_on_payslip', readonly=True)
    category_id = fields.Many2one(related='salary_rule_id.category_id', readonly=True, store=True)
    partner_id = fields.Many2one(related='salary_rule_id.partner_id', readonly=True, store=True)

    date_from = fields.Date(string='From', related="slip_id.date_from", store=True)
    date_to = fields.Date(string='To', related="slip_id.date_to", store=True)
    company_id = fields.Many2one(related='slip_id.company_id')

    @api.depends('quantity', 'amount', 'rate')
    def _compute_total(self):
        for line in self:
            line.total = float(line.quantity) * line.amount * line.rate / 100

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if 'employee_id' not in values or 'contract_id' not in values:
                payslip = self.env['hr.payslip'].browse(values.get('slip_id'))
                values['employee_id'] = values.get('employee_id') or payslip.employee_id.id
                values['contract_id'] = values.get('contract_id') or payslip.contract_id and payslip.contract_id.id
                if not values['contract_id']:
                    raise UserError(_('You must set a contract to create a payslip line.'))
        return super(HrPayslipLine, self).create(vals_list)


class HrPayslipWorkedDays(models.Model):
    _name = 'hr.payslip.worked_days'
    _description = 'Payslip Worked Days'
    _order = 'payslip_id, sequence'

    name = fields.Char(related='work_entry_type_id.name', string='Description', readonly=True)
    payslip_id = fields.Many2one('hr.payslip', string='Pay Slip', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(required=True, index=True, default=10)
    code = fields.Char(string='Code', related='work_entry_type_id.code')
    work_entry_type_id = fields.Many2one('hr.work.entry.type', string='Type', required=True, help="The code that can be used in the salary rules")
    number_of_days = fields.Float(string='Number of Days')
    number_of_hours = fields.Float(string='Number of Hours')
    amount = fields.Monetary(string='Amount', digits='Payroll', default=0.0)
    contract_id = fields.Many2one(related='payslip_id.contract_id', string='Contract', required=True,
        help="The contract for which applied this worked days")
    currency_id = fields.Many2one('res.currency', related='payslip_id.currency_id')


class HrPayslipInput(models.Model):
    _name = 'hr.payslip.input'
    _description = 'Payslip Input'
    _order = 'payslip_id, sequence'

    name = fields.Char(related='input_type_id.name', string="Name", readonly=True)
    payslip_id = fields.Many2one('hr.payslip', string='Pay Slip', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(required=True, index=True, default=10)
    input_type_id = fields.Many2one('hr.payslip.input.type', string='Description', required=True)
    code = fields.Char(related='input_type_id.code', required=True, help="The code that can be used in the salary rules")
    amount = fields.Float(help="It is used in computation. For e.g. A rule for sales having "
                               "1% commission of basic salary for per product can defined in expression "
                               "like result = inputs.SALEURO.amount * contract.wage*0.01.")
    contract_id = fields.Many2one(related='payslip_id.contract_id', string='Contract', required=True,
        help="The contract for which applied this input")
    struct_id = fields.Many2one('hr.payroll.structure', string='Structure', related='payslip_id.struct_id')

    @api.onchange('struct_id')
    def _onchange_struct_id(self):
        return {'domain': {'input_type_id': ['|', ('id', 'in', self.payslip_id.struct_id.input_line_type_ids.ids), ('struct_ids', '=', False)]}}

class HrPayslipInputType(models.Model):
    _name = 'hr.payslip.input.type'
    _description = 'Payslip Input Type'

    name = fields.Char(string='Description', required=True)
    code = fields.Char(required=True, help="The code that can be used in the salary rules")
    struct_ids = fields.Many2many('hr.payroll.structure', string='Avaibility in Structure', help='This input will be only available in those structure. If empty, it will be available in all payslip.')
    country_id = fields.Many2one('res.country', string='Country', default=lambda self: self.env.company.country_id)


class HrPayslipRun(models.Model):
    _name = 'hr.payslip.run'
    _description = 'Payslip Batches'
    _order = 'date_end desc'

    name = fields.Char(required=True, readonly=True, states={'draft': [('readonly', False)]})
    slip_ids = fields.One2many('hr.payslip', 'payslip_run_id', string='Payslips', readonly=True,
        states={'draft': [('readonly', False)]})
    state = fields.Selection([
        ('draft', 'Draft'),
        ('verify', 'Verify'),
        ('close', 'Done'),
    ], string='Status', index=True, readonly=True, copy=False, default='draft')
    date_start = fields.Date(string='Date From', required=True, readonly=True,
        states={'draft': [('readonly', False)]}, default=lambda self: fields.Date.to_string(date.today().replace(day=1)))
    date_end = fields.Date(string='Date To', required=True, readonly=True,
        states={'draft': [('readonly', False)]},
        default=lambda self: fields.Date.to_string((datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()))
    credit_note = fields.Boolean(string='Credit Note', readonly=True,
        states={'draft': [('readonly', False)]},
        help="If its checked, indicates that all payslips generated from here are refund payslips.")
    payslip_count = fields.Integer(compute='_compute_payslip_count')
    company_id = fields.Many2one('res.company', string='Company', readonly=True, required=True,
        default=lambda self: self.env.company)

    def _compute_payslip_count(self):
        for payslip_run in self:
            payslip_run.payslip_count = len(self.slip_ids)

    def action_draft(self):
        return self.write({'state': 'draft'})

    def action_close(self):
        if self._are_payslips_ready():
            self.write({'state' : 'close'})

    def action_validate(self):
        self.mapped('slip_ids').filtered(lambda slip: slip.state != 'cancel').action_payslip_done()
        self.action_close()

    def action_open_payslips(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hr.payslip",
            "views": [[False, "tree"], [False, "form"]],
            "domain": [['id', 'in', self.slip_ids.ids]],
            "name": "Payslips",
        }

    def unlink(self):
        if any(self.filtered(lambda payslip_run: payslip_run.state not in ('draft'))):
            raise UserError(_('You cannot delete a payslip batch which is not draft!'))
        if any(self.mapped('slip_ids').filtered(lambda payslip: payslip.state not in ('draft','cancel'))):
            raise UserError(_('You cannot delete a payslip which is not draft or cancelled!'))
        return super(HrPayslipRun, self).unlink()

    def _are_payslips_ready(self):
        return all(slip.state in ['done', 'cancel'] for slip in self.mapped('slip_ids'))


class ContributionRegisterReport(models.AbstractModel):
    _name = 'report.hr_payroll.contribution_register'
    _description = 'Model for Printing hr.payslip.line grouped by register'

    def _get_report_values(self, docids, data):
        docs = []
        lines_data = {}
        lines_total = {}

        for result in self.env['hr.payslip.line'].read_group([('id', 'in', docids)], ['partner_id', 'total', 'ids:array_agg(id)'], ['partner_id']):
            if result['partner_id']:
                docid = result['partner_id'][0]
                docs.append(docid)
                lines_data[docid] = self.env['hr.payslip.line'].browse(result['ids'])
                lines_total[docid] = result['total']

        return {
            'docs': self.env['res.partner'].browse(docs),
            'data': data,
            'lines_data': lines_data,
            'lines_total': lines_total
        }
