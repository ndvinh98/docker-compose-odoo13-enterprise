# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from OpenSSL import crypto
import base64
import logging
import re

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    l10n_ar_country_code = fields.Char(related='company_id.country_id.code', string='Country Code')
    l10n_ar_afip_verification_type = fields.Selection(related='company_id.l10n_ar_afip_verification_type', readonly=False)

    l10n_ar_afip_ws_environment = fields.Selection(related='company_id.l10n_ar_afip_ws_environment', readonly=False)
    l10n_ar_afip_ws_key = fields.Binary(related='company_id.l10n_ar_afip_ws_key', readonly=False)
    l10n_ar_afip_ws_crt = fields.Binary(related='company_id.l10n_ar_afip_ws_crt', readonly=False)

    l10n_ar_afip_ws_key_fname = fields.Char('Private Key name', default='private_key.pem')
    l10n_ar_afip_ws_crt_fname = fields.Char(related='company_id.l10n_ar_afip_ws_crt_fname')

    def l10n_ar_action_create_certificate_request(self):
        self.ensure_one()
        if not self.company_id.partner_id.city:
            raise UserError(_('The company city must be defined before this action'))
        if not self.company_id.partner_id.country_id:
            raise UserError(_('The company country must be defined before this action'))
        if not self.company_id.partner_id.l10n_ar_vat:
            raise UserError(_('The company CUIT must be defined before this action'))

        return {'type': 'ir.actions.act_url', 'url': '/l10n_ar_edi/download_csr/' + str(self.company_id.id), 'target': 'new'}

    def l10n_ar_connection_test(self):
        self.ensure_one()
        error = ''
        if not self.l10n_ar_afip_ws_crt:
            error += '\n* ' + _('Please set a certificate in order to make the test')
        if not self.l10n_ar_afip_ws_key:
            error += '\n* ' + _('Please set a private key in order to make the test')
        if error:
            raise UserError(error)

        res = ''
        for webservice in ['wsfe', 'wsfex', 'wsbfe', 'wscdc']:
            try:
                self.company_id._l10n_ar_get_connection(webservice)
                res += ('\n* %s: ' + _('Connection is available')) % webservice
            except UserError as error:
                hint_msg = re.search('.*(HINT|CONSEJO): (.*)', error.name)
                msg = hint_msg.groups()[-1] if hint_msg and len(hint_msg.groups()) > 1 \
                    else '\n'.join(re.search('.*' + webservice + ': (.*)\n\n', error.name).groups())
                res += '\n* %s: ' % webservice + _('Connection failed') + '. %s' % msg.strip()
            except Exception as error:
                res += ('\n* %s: ' + _('Connection failed') + '. ' + _('This is what we get') + ' %s') % (webservice, repr(error))
        raise UserError(res)

    def random_demo_cert(self):
        self.company_id.set_demo_random_cert()
