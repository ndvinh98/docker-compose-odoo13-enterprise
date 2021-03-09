# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.fields import Datetime
from odoo.osv.expression import NEGATIVE_TERM_OPERATORS


class MarketingParticipant(models.Model):
    _name = 'marketing.participant'
    _description = 'Marketing Participant'
    _rec_name = 'resource_ref'

    @api.model
    def default_get(self, default_fields):
        defaults = super(MarketingParticipant, self).default_get(default_fields)
        if not defaults.get('res_id'):
            model_name = defaults.get('model_name')
            if not model_name and defaults.get('campaign_id'):
                model_name = self.env['marketing.campaign'].browse(defaults['campaign_id']).model_name
            if model_name and model_name in self.env:
                resource = self.env[model_name].search([], limit=1)
                defaults['res_id'] = resource.id
        return defaults

    @api.model
    def _selection_target_model(self):
        models = self.env['ir.model'].search([('is_mail_thread', '=', True)])
        return [(model.model, model.name) for model in models]

    def _search_resource_ref(self, operator, value):
        ir_models = set([model['model_name'] for model in self.env['marketing.campaign'].search([]).read(['model_name'])])
        ir_model_ids = []
        for model in ir_models:
            if model in self.env:
                ir_model_ids += self.env['marketing.participant'].search(['&', ('model_name', '=', model), ('res_id', 'in', [name[0] for name in self.env[model].name_search(name=value)])]).ids
        operator = 'not in' if operator in NEGATIVE_TERM_OPERATORS else 'in'
        return [('id', operator, ir_model_ids)]

    campaign_id = fields.Many2one(
        'marketing.campaign', string='Campaign',
        index=True, ondelete='cascade', required=True)
    model_id = fields.Many2one(
        'ir.model', string='Object', related='campaign_id.model_id',
        index=True, readonly=True, store=True)
    model_name = fields.Char(
        string='Record model', related='campaign_id.model_id.model',
        readonly=True, store=True)
    res_id = fields.Integer(string='Record ID', index=True)
    resource_ref = fields.Reference(
        string='Record', selection='_selection_target_model',
        compute='_compute_resource_ref', inverse='_set_resource_ref', search='_search_resource_ref')
    trace_ids = fields.One2many('marketing.trace', 'participant_id', string='Actions')
    state = fields.Selection([
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('unlinked', 'Removed'),
        ], default='running', index=True, required=True,
        help='Removed means the related record does not exist anymore.')
    is_test = fields.Boolean('Test Record', default=False)

    @api.depends('model_name', 'res_id')
    def _compute_resource_ref(self):
        for participant in self:
            if participant.model_name and participant.model_name in self.env:
                participant.resource_ref = '%s,%s' % (participant.model_name, participant.res_id or 0)
            else:
                participant.resource_ref = None

    def _set_resource_ref(self):
        for participant in self:
            if participant.resource_ref:
                participant.res_id = participant.resource_ref.id

    def check_completed(self):
        existing_traces = self.env['marketing.trace'].search([
            ('participant_id', 'in', self.ids),
            ('state', '=', 'scheduled'),
        ])
        (self - existing_traces.mapped('participant_id')).write({'state': 'completed'})

    @api.model
    def create(self, values):
        res = super(MarketingParticipant, self).create(values)
        # prepare first traces related to begin activities
        primary_activities = res.campaign_id.marketing_activity_ids.filtered(lambda act: act.trigger_type == 'begin')
        now = Datetime.now()
        trace_ids = [
            (0, 0, {
                'activity_id': activity.id,
                'schedule_date': now + relativedelta(**{activity.interval_type: activity.interval_number}),
            }) for activity in primary_activities]
        res.write({'trace_ids': trace_ids})
        return res

    def action_set_completed(self):
        ''' Manually mark as a completed and cancel every scheduled trace '''
        # TDE TODO: delegate set Canceled to trace record
        self.write({'state': 'completed'})
        self.env['marketing.trace'].search([
            ('participant_id', 'in', self.ids),
            ('state', '=', 'scheduled')
        ]).write({
            'state': 'canceled',
            'schedule_date': Datetime.now(),
            'state_msg': _('Marked as completed')
        })

    def action_set_running(self):
        self.write({'state': 'running'})

    def action_set_unlink(self):
        self.write({'state': 'unlinked'})
        self.env['marketing.trace'].search([
            ('participant_id', 'in', self.ids),
            ('state', '=', 'scheduled')
        ]).write({
            'state': 'canceled',
            'state_msg': _('Record deleted'),
        })
        return True


class MarketingTrace(models.Model):
    _name = 'marketing.trace'
    _description = 'Marketing Trace'
    _order = 'schedule_date DESC'
    _rec_name = 'participant_id'

    participant_id = fields.Many2one(
        'marketing.participant', string='Participant',
        index=True, ondelete='cascade', required=True)
    res_id = fields.Integer(string='Document ID', related='participant_id.res_id', index=True, store=True, readonly=False)
    is_test = fields.Boolean(string='Test Trace', related='participant_id.is_test', index=True, store=True, readonly=True)
    activity_id = fields.Many2one(
        'marketing.activity', string='Activity',
        index=True, ondelete='cascade', required=True)
    activity_type = fields.Selection(related='activity_id.activity_type', readonly=True)
    trigger_type = fields.Selection(related='activity_id.trigger_type', readonly=True)

    state = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('processed', 'Processed'),
        ('rejected', 'Rejected'),
        ('canceled', 'Canceled'),
        ('error', 'Error')
        ], default='scheduled', index=True, required=True)
    schedule_date = fields.Datetime()
    state_msg = fields.Char(string='Error message')
    # hierarchy
    parent_id = fields.Many2one('marketing.trace', string='Parent', index=True, ondelete='cascade')
    child_ids = fields.One2many('marketing.trace', 'parent_id', string='Direct child traces')
    # statistics
    mailing_trace_ids = fields.One2many('mailing.trace', 'marketing_trace_id', string='Mass mailing statistics')
    sent = fields.Datetime(related='mailing_trace_ids.sent', readonly=False)
    exception = fields.Datetime(related='mailing_trace_ids.exception', readonly=False)
    opened = fields.Datetime(related='mailing_trace_ids.opened', readonly=False)
    replied = fields.Datetime(related='mailing_trace_ids.replied', readonly=False)
    bounced = fields.Datetime(related='mailing_trace_ids.bounced', readonly=False)
    clicked = fields.Datetime(related='mailing_trace_ids.clicked', readonly=False)

    def participant_action_cancel(self):
        self.action_cancel(message=_('Manually'))

    def action_cancel(self, message=None):
        values = {'state': 'canceled', 'schedule_date': Datetime.now()}
        if message:
            values['state_msg'] = message
        self.write(values)
        self.mapped('participant_id').check_completed()

    def action_execute(self):
        self.activity_id.execute_on_traces(self)

    def process_event(self, action):
        """Process event coming from customers currently centered on email actions.
        It updates child traces :

         * opposite actions are canceled, for example mail_not_open when mail_open is triggered;
         * bounced mail cancel all child actions not being mail_bounced;

        :param string action: see trigger_type field of activity
        """
        self.ensure_one()
        if self.participant_id.campaign_id.state not in ['draft', 'running']:
            return

        now = Datetime.from_string(Datetime.now())
        msg = {
            'mail_not_reply': _('Parent activity mail replied'),
            'mail_not_click': _('Parent activity mail clicked'),
            'mail_not_open': _('Parent activity mail opened'),
            'mail_bounce': _('Parent activity mail bounced'),
        }

        opened_child = self.child_ids.filtered(lambda trace: trace.state == 'scheduled')

        for next_trace in opened_child.filtered(lambda trace: trace.activity_id.trigger_type == action):
            if next_trace.activity_id.interval_number == 0:
                next_trace.write({
                    'schedule_date': now,
                })
                next_trace.activity_id.execute_on_traces(next_trace)
            else:
                next_trace.write({
                    'schedule_date': now + relativedelta(**{
                        next_trace.activity_id.interval_type: next_trace.activity_id.interval_number
                    }),
                })

        if action in ['mail_reply', 'mail_click', 'mail_open']:
            opposite_trigger = action.replace('_', '_not_')
            opened_child.filtered(
                lambda trace: trace.activity_id.trigger_type == opposite_trigger
            ).action_cancel(message=msg[opposite_trigger])

        elif action == 'mail_bounce':
            opened_child.filtered(
                lambda trace: trace.activity_id.trigger_type != 'mail_bounce'
            ).action_cancel(message=msg[action])

        return True
