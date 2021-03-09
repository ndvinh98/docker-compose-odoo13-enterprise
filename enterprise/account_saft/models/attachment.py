# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import io
import logging
import requests
import zipfile
from os.path import join
from lxml import etree, objectify

from odoo import models, tools

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def _extract_xsd_from_zip(self, url, response, file_name=None):
        """
        :return bytes: return read bytes

        :param response: response object
        :param url: url of zip file
        :param file_name: the file name to be extracted from the given url
        """
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        file = ''
        for file_path in archive.namelist():
            if file_name in file_path:
                file = file_path
                break
        try:
            return archive.open(file).read()
        except KeyError as e:
            _logger.info(e)
            return ''

    def _modify_and_validate_xsd_content(self, module_name, content):
        """
        :return object: returns ObjectifiedElement.

        :param module_name: name of the module who is invoking this function(to be used by overridden methods)
        :param content: file content as bytes
        """
        try:
            return objectify.fromstring(content)
        except etree.XMLSyntaxError as e:
            _logger.warning('You are trying to load an invalid xsd file.\n%s', e)
            return ''

    def _load_xsd_saft(self, url, module_name, file_name=None):
        fname = file_name or url.split('/')[-1]
        xsd_fname = 'xsd_cached_%s' % fname.replace('.', '_')
        attachment = self.env.ref('%s.%s' % (module_name, xsd_fname), False)
        if attachment:
            return
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.exceptions.HTTPError as httpe:
            _logger.warning('HTTP error %s with the given URL: %s' % (httpe.code, url))
            return
        if file_name:
            content = self._extract_xsd_from_zip(url, response, file_name)
        else:
            content = response.content
        xsd_object = self._modify_and_validate_xsd_content(module_name, content)
        if not len(xsd_object):
            return
        validated_content = etree.tostring(xsd_object)
        attachment = self.create({
            'name': xsd_fname,
            'datas': base64.encodestring(validated_content),
        })
        self.env['ir.model.data'].create({
            'name': xsd_fname,
            'module': module_name,
            'res_id': attachment.id,
            'model': 'ir.attachment',
            'noupdate': True
        })
        return join(tools.config.filestore(self.env.cr.dbname), attachment.store_fname)
