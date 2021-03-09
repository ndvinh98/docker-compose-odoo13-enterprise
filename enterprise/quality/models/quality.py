# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TestType(models.Model):
    _name = "quality.point.test_type"
    _description = "Quality Control Test Type"

    # Used instead of selection field in order to hide a choice depending on the view.
    name = fields.Char('Name', required=True)
    technical_name = fields.Char('Technical name', required=True)

class QualityPoint(models.Model):
    _name = "quality.point"
    _description = "Quality Control Point"
    _inherit = ['mail.thread']
    _order = "sequence, id"
    _check_company_auto = True

    def _get_default_team_id(self):
        company_id = self.company_id.id or self.env.context.get('default_company_id', self.env.company.id)
        domain = ['|', ('company_id', '=', company_id), ('company_id', '=', False)]
        return self.team_id._get_quality_team(domain)

    def _get_default_test_type_id(self):
        domain = self._get_type_default_domain()
        return self.env['quality.point.test_type'].search(domain, limit=1).id

    name = fields.Char(
        'Reference', copy=False, default=lambda self: _('New'),
        required=True)
    sequence = fields.Integer('Sequence')
    title = fields.Char('Title')
    team_id = fields.Many2one(
        'quality.alert.team', 'Team', check_company=True,
        default=_get_default_team_id, required=True)
    product_id = fields.Many2one(
        'product.product', 'Product Variant',
        domain="[('product_tmpl_id', '=', product_tmpl_id)]")
    product_tmpl_id = fields.Many2one(
        'product.template', 'Product', required=True, check_company=True,
        domain="[('type', 'in', ['consu', 'product']), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    picking_type_id = fields.Many2one('stock.picking.type', "Operation Type", required=True, check_company=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', 'Responsible')
    active = fields.Boolean(default=True)
    check_count = fields.Integer(compute="_compute_check_count")
    check_ids = fields.One2many('quality.check', 'point_id')
    test_type_id = fields.Many2one('quality.point.test_type', 'Test Type', help="Defines the type of the quality control point.",
                                   required=True, default=_get_default_test_type_id)
    test_type = fields.Char(related='test_type_id.technical_name', readonly=True)
    note = fields.Html('Note')
    reason = fields.Html('Cause')

    def _compute_check_count(self):
        check_data = self.env['quality.check'].read_group([('point_id', 'in', self.ids)], ['point_id'], ['point_id'])
        result = dict((data['point_id'][0], data['point_id_count']) for data in check_data)
        for point in self:
            point.check_count = result.get(point.id, 0)

    @api.onchange('product_tmpl_id')
    def onchange_product_tmpl_id(self):
        self.product_id = self.product_tmpl_id.product_variant_ids.ids and self.product_tmpl_id.product_variant_ids[0]

    @api.model
    def create(self, vals):
        if 'name' not in vals or vals['name'] == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('quality.point') or _('New')
        return super(QualityPoint, self).create(vals)

    def check_execute_now(self):
        # TDE FIXME: make true multi
        self.ensure_one()
        return True

    def _get_type_default_domain(self):
        return []


class QualityAlertTeam(models.Model):
    _name = "quality.alert.team"
    _description = "Quality Alert Team"
    _inherit = ['mail.alias.mixin', 'mail.thread']
    _order = "sequence, id"

    name = fields.Char('Name', required=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True)
    sequence = fields.Integer('Sequence')
    check_count = fields.Integer('# Quality Checks', compute='_compute_check_count')
    alert_count = fields.Integer('# Quality Alerts', compute='_compute_alert_count')
    color = fields.Integer('Color', default=1)
    alias_id = fields.Many2one('mail.alias', 'Alias', ondelete="restrict", required=True)

    def _compute_check_count(self):
        check_data = self.env['quality.check'].read_group([('team_id', 'in', self.ids), ('quality_state', '=', 'none')], ['team_id'], ['team_id'])
        check_result = dict((data['team_id'][0], data['team_id_count']) for data in check_data)
        for team in self:
            team.check_count = check_result.get(team.id, 0)

    def _compute_alert_count(self):
        alert_data = self.env['quality.alert'].read_group([('team_id', 'in', self.ids), ('stage_id.done', '=', False)], ['team_id'], ['team_id'])
        alert_result = dict((data['team_id'][0], data['team_id_count']) for data in alert_data)
        for team in self:
            team.alert_count = alert_result.get(team.id, 0)

    @api.model
    def _get_quality_team(self, domain):
        team_id = self.env['quality.alert.team'].search(domain, limit=1).id
        if team_id:
            return team_id
        else:
            raise UserError(_("No quality team found for this company.\n"
                              "Please go to configuration and create one first."))


class QualityReason(models.Model):
    _name = "quality.reason"
    _description = "Root Cause for Quality Failure"

    name = fields.Char('Name', required=True, translate=True)


class QualityTag(models.Model):
    _name = "quality.tag"
    _description = "Quality Tag"

    name = fields.Char('Tag Name', required=True)
    color = fields.Integer('Color Index', help='Used in the kanban view')  # TDE: should be default value


class QualityAlertStage(models.Model):
    _name = "quality.alert.stage"
    _description = "Quality Alert Stage"
    _order = "sequence, id"
    _fold_name = 'folded'

    name = fields.Char('Name', required=True, translate=True)
    sequence = fields.Integer('Sequence')
    folded = fields.Boolean('Folded')
    done = fields.Boolean('Alert Processed')


class QualityCheck(models.Model):
    _name = "quality.check"
    _description = "Quality Check"
    _inherit = ['mail.thread']
    _check_company_auto = True

    name = fields.Char('Name', default=lambda self: _('New'))
    point_id = fields.Many2one(
        'quality.point', 'Control Point', check_company=True)
    quality_state = fields.Selection([
        ('none', 'To do'),
        ('pass', 'Passed'),
        ('fail', 'Failed')], string='Status', tracking=True,
        default='none', copy=False)
    control_date = fields.Datetime('Control Date', tracking=True)
    product_id = fields.Many2one(
        'product.product', 'Product', check_company=True, required=True,
        domain="[('type', 'in', ['consu', 'product']), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    picking_id = fields.Many2one('stock.picking', 'Picking', check_company=True)
    lot_id = fields.Many2one(
        'stock.production.lot', 'Lot',
        domain="[('product_id', '=', product_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    user_id = fields.Many2one('res.users', 'Responsible', tracking=True)
    team_id = fields.Many2one(
        'quality.alert.team', 'Team', required=True, check_company=True)
    company_id = fields.Many2one(
        'res.company', 'Company', required=True, index=True,
        default=lambda self: self.env.company)
    alert_ids = fields.One2many('quality.alert', 'check_id', string='Alerts')
    alert_count = fields.Integer('# Quality Alerts', compute="_compute_alert_count")
    note = fields.Html(related='point_id.note', readonly=True)
    test_type_id = fields.Many2one(
        'quality.point.test_type', 'Test Type',
        required=True)
    test_type = fields.Char(related='test_type_id.technical_name')
    picture = fields.Binary('Picture', attachment=True)

    def _compute_alert_count(self):
        alert_data = self.env['quality.alert'].read_group([('check_id', 'in', self.ids)], ['check_id'], ['check_id'])
        alert_result = dict((data['check_id'][0], data['check_id_count']) for data in alert_data)
        for check in self:
            check.alert_count = alert_result.get(check.id, 0)

    @api.onchange('point_id')
    def _onchange_point_id(self):
        if self.point_id:
            self.product_id = self.point_id.product_id
            self.team_id = self.point_id.team_id.id

    @api.model
    def create(self, vals):
        if 'name' not in vals or vals['name'] == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('quality.check') or _('New')
        if 'point_id' in vals and not vals.get('test_type_id'):
            vals['test_type_id'] = self.env['quality.point'].browse(vals['point_id']).test_type_id.id
        return super(QualityCheck, self).create(vals)

    def do_fail(self):
        self.write({
            'quality_state': 'fail',
            'user_id': self.env.user.id,
            'control_date': datetime.now()})
        if self.env.context.get('no_redirect'):
            return True
        return self.redirect_after_pass_fail()

    def do_pass(self):
        self.write({'quality_state': 'pass',
                    'user_id': self.env.user.id,
                    'control_date': datetime.now()})
        if self.env.context.get('no_redirect'):
            return True
        return self.redirect_after_pass_fail()

    def redirect_after_pass_fail(self):
        return {'type': 'ir.actions.act_window_close'}


class QualityAlert(models.Model):
    _name = "quality.alert"
    _description = "Quality Alert"
    _inherit = ['mail.thread.cc', 'mail.activity.mixin']
    _check_company_auto = True

    def _get_default_team_id(self):
        company_id = self.company_id.id or self.env.context.get('default_company_id', self.env.company.id)
        domain = ['|', ('company_id', '=', company_id), ('company_id', '=', False)]
        return self.team_id._get_quality_team(domain)

    name = fields.Char('Name', default=lambda self: _('New'))
    description = fields.Html('Description')
    stage_id = fields.Many2one('quality.alert.stage', 'Stage', ondelete='restrict',
        group_expand='_read_group_stage_ids',
        default=lambda self: self.env['quality.alert.stage'].search([], limit=1).id, tracking=True)
    company_id = fields.Many2one(
        'res.company', 'Company', required=True, index=True,
        default=lambda self: self.env.company)
    reason_id = fields.Many2one('quality.reason', 'Root Cause')
    tag_ids = fields.Many2many('quality.tag', string="Tags")
    date_assign = fields.Datetime('Date Assigned')
    date_close = fields.Datetime('Date Closed')
    picking_id = fields.Many2one('stock.picking', 'Picking', check_company=True)
    action_corrective = fields.Html('Corrective Action')
    action_preventive = fields.Html('Preventive Action')
    user_id = fields.Many2one('res.users', 'Responsible', tracking=True, default=lambda self: self.env.user)
    team_id = fields.Many2one(
        'quality.alert.team', 'Team', required=True, check_company=True,
        default=lambda x: x._get_default_team_id())
    partner_id = fields.Many2one('res.partner', 'Vendor', check_company=True)
    check_id = fields.Many2one('quality.check', 'Check', check_company=True)
    product_tmpl_id = fields.Many2one(
        'product.template', 'Product', check_company=True,
        domain="[('type', 'in', ['consu', 'product']), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    product_id = fields.Many2one(
        'product.product', 'Product Variant',
        domain="[('product_tmpl_id', '=', product_tmpl_id)]")
    lot_id = fields.Many2one(
        'stock.production.lot', 'Lot', check_company=True,
        domain="['|', ('product_id', '=', product_id), ('product_id.product_tmpl_id.id', '=', product_tmpl_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Low'),
        ('2', 'High'),
        ('3', 'Very High')], string='Priority',
        index=True)

    @api.model
    def create(self, vals):
        if 'name' not in vals or vals['name'] == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('quality.alert') or _('New')
        return super(QualityAlert, self).create(vals)

    def write(self, vals):
        res = super(QualityAlert, self).write(vals)
        if self.stage_id.done and 'stage_id' in vals:
            self.write({'date_close': fields.Datetime.now()})
        return res

    @api.onchange('product_tmpl_id')
    def onchange_product_tmpl_id(self):
        self.product_id = self.product_tmpl_id.product_variant_ids.ids and self.product_tmpl_id.product_variant_ids.ids[0]

    @api.onchange('team_id')
    def onchange_team_id(self):
        if self.team_id:
            self.company_id = self.team_id.company_id or self.env.company

