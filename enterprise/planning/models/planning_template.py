import math

from datetime import datetime, timedelta, time, date
from odoo import api, fields, models, _
from odoo.tools import format_time


class PlanningTemplate(models.Model):
    _name = 'planning.slot.template'
    _description = "Shift Template"

    role_id = fields.Many2one('planning.role', string="Role")
    start_time = fields.Float('Start hour', default=0)
    duration = fields.Float('Duration (hours)', default=0)

    _sql_constraints = [
        ('check_start_time_lower_than_24', 'CHECK(start_time <= 24)', 'You cannot have a start hour greater than 24'),
        ('check_start_time_positive', 'CHECK(start_time >= 0)', 'Start hour must be a positive number'),
        ('check_duration_positive', 'CHECK(duration >= 0)', 'You cannot have a negative duration')
    ]

    def name_get(self):
        result = []
        for shift_template in self:
            start_time = time(hour=int(shift_template.start_time), minute=round(math.modf(shift_template.start_time)[0] / (1 / 60.0)))
            duration = timedelta(hours=int(shift_template.duration), minutes=round(math.modf(shift_template.duration)[0] / (1 / 60.0)))
            end_time = datetime.combine(date.today(), start_time) + duration
            name = '%s - %s %s %s' % (
                format_time(shift_template.env, start_time, time_format='short').replace(':00 ', ' '),
                format_time(shift_template.env, end_time.time(), time_format='short').replace(':00 ', ' '),
                _('(%s days span)') % (duration.days + 1) if duration.days > 0 else '',
                shift_template.role_id.name if shift_template.role_id.name is not False else ''
            )
            result.append([shift_template.id, name])
        return result
