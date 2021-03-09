# -*- coding: utf-8 -*-
import logging

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError, except_orm
from odoo.addons.base_iban.models.res_partner_bank import validate_iban
from odoo.addons.iap import InsufficientCreditError
from odoo.addons.phone_validation.tools.phone_validation import phone_sanitize_numbers

_logger = logging.getLogger(__name__)


class SepaDirectDebitController(http.Controller):
    def _check_values(self, acquirer, iban, phone=None):
        validate_iban(iban)
        # TO CHECK: should we restrict to country code from iban country?
        sanitized_number = None
        if acquirer.sepa_direct_debit_sms_enabled:
            if not phone:
                raise ValidationError(_('No phone number provided.'))
            sanitized_number = phone_sanitize_numbers([phone], None, None).get(phone, {}).get('sanitized')
            if not sanitized_number:
                raise ValidationError(_('Incorrect phone number.'))
        return (iban, sanitized_number)

    @http.route("/payment/sepa_direct_debit/send_sms", type="json", auth="public", website=True)
    def send_sms(self, iban, phone, acquirer_id, partner_id=None, mandate_id=None, **post):
        """Generate a draft mandate (or find an existing one) with a validation code."""
        try:
            if request.env.user._is_public() and partner_id is None:
                raise ValidationError(_("Can't register a mandate with an undefined partner."))
            acquirer = request.env['payment.acquirer'].sudo().browse(int(acquirer_id))
            if acquirer.provider != 'sepa_direct_debit':
                raise ValidationError(_('This provider is not a SEPA Direct Debit provider.'))
            (iban, phone) = self._check_values(acquirer, iban, phone)
            partner_id = int(partner_id) or request.env.user.partner_id.id
            mandate = acquirer._create_or_find_mandate(iban, partner_id)
            try:
                mandate._send_verification_code(phone)
            except InsufficientCreditError:
                raise ValidationError(_('SMS could not be sent due to insufficient credit.'))
        except except_orm as e:
            return {
                'mandate_id': mandate_id,
                'error': e.name,
            }
        return {
            'mandate_id': mandate.id
        }

    @http.route("/payment/sepa_direct_debit/new", type="json", auth="public", website=True)
    def create_mandate(self, iban, phone, validation_code, acquirer_id, signature=None, signer=None, partner_id=None, mandate_id=None, **post):
        try:
            if request.env.user._is_public() and not partner_id:
                raise ValidationError(_("Can't register a mandate with an undefined partner."))
            acquirer = request.env['payment.acquirer'].sudo().browse(int(acquirer_id))
            if acquirer.provider != 'sepa_direct_debit':
                raise ValidationError(_('This provider is not a SEPA Direct Debit provider.'))
            (iban, phone) = self._check_values(acquirer, iban, phone)
            if acquirer.sepa_direct_debit_sign_enabled:
                if not signature or not signer:
                    raise ValidationError(_('Please enter your signature.'))
            token = acquirer.s2s_process({
                'mandate_id': mandate_id and int(mandate_id),
                'iban': iban,
                'acquirer_id': acquirer_id,
                'partner_id': int(partner_id) or request.env.user.partner_id,
            })
            mandate = token.sdd_mandate_id
            mandate._sign(signature=signature, signer=signer)
            mandate._confirm(code=validation_code, phone=phone)
            mandate_id = mandate.id
        except except_orm as e:
            return {
                'error': e.name,
                'mandate_id': mandate_id
            }
        return {
            'result': True,
            'id': token.id,
            '3d_secure': False,
        }
