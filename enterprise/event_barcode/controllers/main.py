# -*- coding: utf-8 -*-
from odoo import fields, http, _
from odoo.http import request


class EventBarcode(http.Controller):

    @http.route('/event_barcode/register_attendee', type='json', auth="user")
    def register_attendee(self, barcode, event_id, **kw):
        Registration = request.env['event.registration']
        attendee = Registration.search([('barcode', '=', barcode), ('event_id', '=', event_id)], limit=1)
        if not attendee:
            return {'warning': _('This ticket is not valid for this event')}
        res = {
            'registration': dict(attendee.summary(), id=attendee.id, partner_id=attendee.partner_id.id),
        }
        attendee_name = attendee.name or _('Attendee')
        if attendee.state == 'cancel':
            res.update({'warning': _('Canceled registration')})
        elif attendee.state != 'done':
            attendee.write({'state': 'done', 'date_closed': fields.Datetime.now()})
            res.update({'success': _('%s is successfully registered') % attendee_name})
        else:
            res.update({'warning': _('%s is already registered') % attendee_name})
        return res

    @http.route(['/event_barcode/event'], type='json', auth="user")
    def get_event_data(self, event_id):
        event = request.env['event.event'].browse(event_id)
        return {
            'name': event.name,
            'country': event.address_id.country_id.name,
            'city': event.address_id.city,
            'company_name': event.company_id.name
        }
