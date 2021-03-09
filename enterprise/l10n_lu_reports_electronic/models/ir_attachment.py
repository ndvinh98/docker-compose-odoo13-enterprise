# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import logging
import requests
from os.path import join
from lxml import etree, objectify

from odoo import models, tools

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def _load_xsd_lu_electronic_files(self):
        attachment = self.env.ref('l10n_lu_reports_electronic.xsd_cached_eCDF_file_v1_1-XML_schema_xsd', False)
        if attachment:
            return
        try:
            response = requests.get('https://ecdf-developer.b2g.etat.lu/ecdf/formdocs/eCDF_file_v1.1-XML_schema.xsd', timeout=10)
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            _logger.info('I cannot connect with the given URL for the Luxembourg electronic reports xsd.')
            return ''
        try:
            objectify.fromstring(response.content)
        except etree.XMLSyntaxError as e:
            _logger.info('You are trying to load an invalid xsd file for the Luxembourg electronic reports.\n%s', e)
            return ''
        attachment = self.create({
            'name': 'xsd_cached_eCDF_file_v1_1-XML_schema_xsd',
            'datas': base64.encodestring(response.content),
        })
        self.env['ir.model.data'].create({
            'name': 'xsd_cached_eCDF_file_v1_1-XML_schema_xsd',
            'module': 'l10n_lu_reports_electronic',
            'res_id': attachment.id,
            'model': 'ir.attachment',
            'noupdate': True
        })
        return join(tools.config.filestore(self.env.cr.dbname), attachment.store_fname)
