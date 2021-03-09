# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import json
import random
import string

import requests

from odoo import _, models

try:
    from json.decoder import JSONDecodeError
except ImportError:
    # py2 compatibility
    JSONDecodeError = ValueError


class PACSWMixin(models.AbstractModel):
    """PAC SW Mixin is a mixin Abstract class to add methods
    in order to call services of the PAC SW.
    It defines standard name methods that are auto-called from account.move
    or account.payment.

    Re-using code as soon as possible.

    It class is not defining new fields.
    In fact, It is using the standard fields defined by a l10n_mx_edi classes
    """
    _name = 'l10n_mx_edi.pac.sw.mixin'
    _description = 'Mixin methods for PAC SW'

    @staticmethod
    def _l10n_mx_edi_sw_token(pac_info):
        """Get token for SW PAC
        return: string token, string error.
          e.g. if token is success
               (token, None)
          e.g. if token is not success
               (None, error)
        """
        if pac_info['password'] and not pac_info['username']:
            # token is configured directly instead of user/password
            token = pac_info['password'].strip()
            return token, None
        try:
            headers = {
                'user': pac_info['username'],
                'password': pac_info['password'],
                'Cache-Control': "no-cache"
            }
            response = requests.post(pac_info['login_url'], headers=headers)
            response.raise_for_status()
            response_json = response.json()
            return response_json['data']['token'], None
        except (requests.exceptions.RequestException, KeyError, TypeError) as req_e:
            return None, str(req_e)

    @staticmethod
    def _l10n_mx_edi_sw_post(url, headers, payload=None):
        """Send requests.post to PAC SW
        return dict using keys 'status' and 'message'
          e.g. if is success
            {'status': 'success', 'data': {'cfdi': XML}}
          e.g. if is not success
            {'status': 'error', 'message': error, 'messageDetail': error}
        """
        try:
            response = requests.post(url, data=payload, headers=headers,
                                     verify=True, timeout=20)
        except requests.exceptions.RequestException as req_e:
            return {'status': 'error', 'message': str(req_e)}
        msg = ""
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as res_e:
            msg = str(res_e)
        try:
            response_json = response.json()
        except JSONDecodeError:
            # If it is not possible get json then
            # use response exception message
            return {'status': 'error', 'message': msg}
        if (response_json['status'] == 'error' and
                response_json['message'].startswith('307')):
            # XML signed previously
            cfdi = base64.encodestring(
                response_json['messageDetail'].encode('UTF-8'))
            cfdi = cfdi.decode('UTF-8')
            response_json['data'] = {'cfdi': cfdi}
            # We do not need an error message if XML signed was
            # retrieved then cleaning them
            response_json.update({
                'message': None,
                'messageDetail': None,
                'status': 'success',
            })
        return response_json

    @staticmethod
    def _l10n_mx_edi_sw_boundary():
        lst = [random.choice(string.ascii_letters + string.digits)
               for n in range(30)]
        boundary = "".join(lst)
        return boundary

    def _l10n_mx_edi_sw_info(self, company_id, service_type):
        test = company_id.l10n_mx_edi_pac_test_env
        username = company_id.l10n_mx_edi_pac_username
        password = company_id.l10n_mx_edi_pac_password
        url = ('http://services.test.sw.com.mx/'
               if test else 'https://services.sw.com.mx/')
        url_service = url + ('cfdi33/stamp/v3/b64' if service_type == 'sign'
                             else 'cfdi33/cancel/csd')
        url_login = url + 'security/authenticate'
        return {
            'url': url_service,
            'multi': False,  # TODO: implement multi
            'username': 'demo' if test else username,
            'password': '123456789' if test else password,
            'login_url': url_login,
        }

    def _l10n_mx_edi_sw_sign(self, pac_info):
        token, req_e = self._l10n_mx_edi_sw_token(pac_info)
        if not token:
            self.l10n_mx_edi_log_error(
                _("Token could not be obtained %s") % req_e)
            return
        url = pac_info['url']
        for rec in self:
            xml = rec.l10n_mx_edi_cfdi.decode('UTF-8')
            boundary = self._l10n_mx_edi_sw_boundary()
            payload = """--%(boundary)s
Content-Type: text/xml
Content-Transfer-Encoding: binary
Content-Disposition: form-data; name="xml"; filename="xml"

%(xml)s
--%(boundary)s--
""" % {'boundary': boundary, 'xml': xml}
            headers = {
                'Authorization': "bearer " + token,
                'Content-Type': ('multipart/form-data; '
                                 'boundary="%s"') % boundary,
            }
            payload = payload.replace('\n', '\r\n').encode('UTF-8')
            response_json = self._l10n_mx_edi_sw_post(
                url, headers, payload=payload)
            code = response_json.get('message')
            msg = response_json.get('messageDetail')
            try:
                xml_signed = response_json['data']['cfdi']
            except (KeyError, TypeError):
                xml_signed = None
            rec._l10n_mx_edi_post_sign_process(
                xml_signed.encode('utf-8') if xml_signed else None,
                code, msg)

    def _l10n_mx_edi_sw_cancel(self, pac_info):
        token, req_e = self._l10n_mx_edi_sw_token(pac_info)
        if not token:
            self.l10n_mx_edi_log_error(
                _("Token could not be obtained %s") % req_e)
            return
        url = pac_info['url']
        headers = {
            'Authorization': "bearer " + token,
            'Content-Type': "application/json"
        }
        for rec in self:
            xml = rec.l10n_mx_edi_get_xml_etree()
            tfd_node = rec.l10n_mx_edi_get_tfd_etree(xml)
            certificate_ids = rec.company_id.l10n_mx_edi_certificate_ids
            certificate = certificate_ids.sudo().get_valid_certificate()
            data = {
                'rfc': xml.Emisor.get('Rfc'),
                'b64Cer': certificate.content.decode('UTF-8'),
                'b64Key': certificate.key.decode('UTF-8'),
                'password': certificate.password,
                'uuid': tfd_node.get('UUID'),
            }
            response_json = self._l10n_mx_edi_sw_post(
                url, headers, payload=json.dumps(data).encode('UTF-8'))
            cancelled = response_json['status'] == 'success'
            code = response_json.get('message')
            msg = response_json.get('messageDetail')
            rec._l10n_mx_edi_post_cancel_process(
                cancelled, code=code, msg=msg)
