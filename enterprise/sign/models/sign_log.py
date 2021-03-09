# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from hashlib import sha256
from json import dumps
from datetime import datetime
import logging

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

LOG_FIELDS = ['log_date', 'action', 'partner_id', 'request_state', 'latitude', 'longitude', 'ip',]

class SignLog(models.Model):
    _name = 'sign.log'
    _order = 'log_date, id'
    _description = "Sign requests access history"
    
    # Accessed on ?
    log_date = fields.Datetime(default=fields.Datetime.now, required=True)
    sign_request_id = fields.Many2one('sign.request', required=True)
    sign_request_item_id = fields.Many2one('sign.request.item')
    # Accessed as ?
    user_id = fields.Many2one('res.users', groups="sign.group_sign_manager")
    partner_id = fields.Many2one('res.partner')

    # Accessed from ?
    # If defined on request item when signing: take from it
    # Else : taken from geoip
    latitude = fields.Float(digits=(10, 7), groups="sign.group_sign_manager")
    longitude = fields.Float(digits=(10, 7), groups="sign.group_sign_manager")
    ip = fields.Char("IP address of the visitor", required=True, groups="sign.group_sign_manager")
    log_hash = fields.Char(string="Inalterability Hash", readonly=True, copy=False)
    token = fields.Char(string="User token")

    # Accessed for ?
    action = fields.Selection(
        string="Action Performed",
        selection=[
            ('create', 'Creation'),
            ('open', 'View/Download'),
            ('sign', 'Signature'),
        ], required=True,
    )

    request_state = fields.Selection([
        ("sent", "Signatures in Progress"),
        ("signed", "Fully Signed"),
        ("canceled", "Canceled")
    ], required=True, string="State of the request on action log", groups="sign.group_sign_manager")

    # Not related on purpose :P

    def write(self, vals):
        raise ValidationError(_("Log history of sign requests cannot be modified !"))

    def unlink(self):
        raise ValidationError(_("Log history of sign requests cannot be deleted !"))

    def create(self, vals):
        """
        1/ if action=='create': get initial shasign from template (checksum pdf)
        2/ if action == 'sign': search for logs with hash for the same request and use that to compute new hash
        """
        vals['log_date'] = datetime.utcnow()
        vals['log_hash'] = self._get_or_check_hash(vals)
        res = super(SignLog, self).create(vals)
        return res

    def _get_or_check_hash(self, vals):
        """ Returns the hash to write on sign log entries """
        if vals['action'] not in ['sign', 'create']:
            return False
        # When we check the hash, we need to restrict the previous activity to logs created before
        domain = [('sign_request_id', '=', vals['sign_request_id']), ('action', 'in', ['create', 'sign'])]
        if 'id' in vals:
            domain.append(('id', '<', vals['id']))
        prev_activity = self.sudo().search(domain, limit=1, order='id desc')
        # Multiple signers lead to multiple creation actions but for them, the hash of the PDF must be calculated.
        previous_hash = ""
        if not prev_activity:
            sign_request = self.env['sign.request'].browse(vals['sign_request_id'])
            body = sign_request.template_id.with_context(bin_size=False).attachment_id.datas
        else:
            previous_hash = prev_activity.log_hash
            body = self._compute_string_to_hash(vals)
        hash = sha256((previous_hash + str(body)).encode('utf-8')).hexdigest()
        return hash

    def _compute_string_to_hash(self, vals):
        values = {}
        for field in LOG_FIELDS:
            values[field] = str(vals[field])
        # Values are filtered based on the token
        # Signer is signing the document. We save the value of its field. self is an empty recordset.
        item_values = self.env['sign.request.item.value'].search([('sign_request_id', '=', vals['sign_request_id'])]).filtered(lambda item: item.sign_request_item_id.access_token == vals['token'])
        for item_value in item_values:
            values[str(item_value.id)] = str(item_value.value)
        return dumps(values, sort_keys=True, ensure_ascii=True, indent=None)

    def _check_document_integrity(self):
        """
        Check the integrity of a sign request by comparing the logs hash to the computed values.
        """
        logs = self.filtered(lambda item: item.action in ['sign', 'create'])
        for log in logs:
            vals = {key: value[0] if isinstance(value, tuple) else value for key, value in log.read()[0].items()}
            hash = self._get_or_check_hash(vals)
            if hash != log.log_hash:
                # TODO add logs and comments
                return False
        return True


    def _prepare_vals_from_item(self, request_item):
        request = request_item.sign_request_id
        return dict(
            sign_request_item_id=request_item.id,
            sign_request_id=request.id,
            request_state=request.state,
            latitude=request_item.latitude or 0.0,
            longitude=request_item.longitude or 0.0,
            partner_id=request_item.partner_id.id)

    def _prepare_vals_from_request(self, sign_request):
        return dict(
            sign_request_id=sign_request.id,
            request_state=sign_request.state,
        )

    def _update_vals_with_http_request(self, vals):
        vals.update({
            'user_id': request.env.user.id if not request.env.user._is_public() else None,
            'ip': request.httprequest.remote_addr,
        })
        if not vals.get('partner_id', False):
            vals.update({
                'partner_id': request.env.user.partner_id.id if not request.env.user._is_public() else None
            })
        # NOTE: during signing, this method is always called after the log is generated based on the
        # request item. This means that if the signer accepted the browser geolocation request, the `vals`
        # will already contain much more precise coordinates. We should use the GeoIP ones only if the
        # browser did not send anything
        if 'geoip' in request.session and not (vals.get('latitude') and vals.get('longitude')):
            vals.update({
                'latitude': request.session['geoip'].get('latitude') or 0.0,
                'longitude': request.session['geoip'].get('longitude') or 0.0,
            })
        return vals
