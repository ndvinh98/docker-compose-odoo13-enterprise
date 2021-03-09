# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from werkzeug.utils import redirect

from odoo import http, SUPERUSER_ID
from odoo import registry as registry_get
from odoo.api import Environment
from odoo.http import request

from odoo.addons.calendar.controllers.main import CalendarController


class WebsiteCalendarController(CalendarController):

    @http.route(website=True)
    def view(self, db, token, action, id, view='calendar', **kwargs):
        """ Redirect the user to the website page of the calendar.event, only if it is an appointment """
        super(WebsiteCalendarController, self).view(db, token, action, id, view='calendar', **kwargs)
        registry = registry_get(db)
        with registry.cursor() as cr:
            env = Environment(cr, SUPERUSER_ID, {})
            attendee = env['calendar.attendee'].search([('access_token', '=', token), ('event_id', '=', int(id))])
            if attendee:
                request.session['timezone'] = attendee.partner_id.tz
                if not attendee.event_id.access_token:
                    attendee.event_id._generate_access_token()
                return redirect('/website/calendar/view/' + str(attendee.event_id.access_token))
            else:
                return request.render("website_calendar.appointment_invalid", {})
