# -*- coding: utf-8 -*-
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

    def _extract_sii_xsd_from_zip(self, url, response, file_name=None):
        """
        This method is used to extract file from SII's XSD zipfile
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

    def _modify_and_validate_sii_xsd_content(self, content):
        """
        :return object: returns ObjectifiedElement.
        :param content: file content as bytes
        """
        try:
            return objectify.fromstring(content)
        except etree.XMLSyntaxError as e:
            _logger.warning('You are trying to load an invalid xsd file.\n%s', e)
            return ''

    def _load_xsd_sii_multi(self):
        # This method only brings the xsd files if it doesn't exist as attachment
        main_xsd_download_url = 'http://www.sii.cl/factura_electronica'

        validation_types = {
            'consu': {
                'description': 'Libro de consumo de folios para boletas de venta',
                'file_name': 'ConsumoFolio_v10.xsd',
                'file_url': 'ConsumoFolio_v10.xsd',
            },
            'doc': {
                'description': 'Documentos Tributarios Electrónicos',
                'file_name': 'DTE_v10.xsd',
                'file_url': 'schema_dte.zip',
            },
            'bol': {
                'description': 'Validación de XML de envío de boletas de venta',
                'file_name': 'EnvioBOLETA_v11.xsd',
                'file_url': 'schema_envio_bol.zip',
            },
            'siitypes': {
                'description': 'Tipos SII',
                'file_name': 'SiiTypes_v10.xsd',
                'file_url': 'schema_dte.zip',
            },
            'env': {
                'description': 'Validación de XML de envío de documentos tributarios Electrónicos',
                'file_name': 'EnvioDTE_v10.xsd',
                'file_url': 'schema_dte.zip',
            },
            'recep': {
                'description': 'Validación de XML de intercambio entre contribuyentes',
                'file_name': 'Recibos_v10.xsd',
                'file_url': 'schema19983.zip',
            },
            'env_recep': {
                'description': 'Validación de envíos de intercambio entre contribuyentes',
                'file_name': 'EnvioRecibos_v10.xsd',
                'file_url': 'schema19983.zip',
            },
            'resp_sii': {
                'description': 'Esquema de respuestas de envío del SII',
                'file_name': 'RespSII_v10.xsd',
                'file_url': 'schema_resp.zip',
            },
            'book': {
                'description': 'Informacion Electronica de Libros de Compra y Venta',
                'file_name': 'LibroCV_v10.xsd',
                'file_url': 'schema_iecv.zip',
            },
            'resp_env': {
                'description': 'Validación de XML de intercambio entre contribuyentes',
                'file_name': 'RespuestaEnvioDTE_v10.xsd',
                'file_url': 'schema_ic.zip',
            },
            'librobol': {
                'description': 'Informacion Electronica de Libros de Boletas',
                'file_name': 'LibroBOLETA_v10.xsd',
                'file_url': 'schema_libro_bol.zip',
            },
            'libroguia': {
                'description': 'Informacion Electronica del Libro de Guias',
                'file_name': 'LibroGuia_v10.xsd',
                'file_url': 'schema_lgd.zip',
            },
            'sig': {
                'description': 'Validación de Firma electrónica',
                'file_name': 'xmldsignature_v10.xsd',
                'file_url': 'schema_dte.zip',
            },
        }
        files = []
        for validator_type, values in validation_types.items():
            url = '%s/%s' % (main_xsd_download_url, values['file_url'])
            attachment = self.env.ref('l10n_cl_edi.%s' % values['file_name'], False)
            if attachment:
                return
            _logger.info('Downloading file from sii: %s, (%s)' % (values['file_url'], values['description']))
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
            except requests.exceptions.HTTPError as httpe:
                _logger.warning('HTTP error %s with the given URL: %s' % (httpe, url))
                return
            except requests.exceptions.ConnectionError as error:
                _logger.warning('ConnectionError: %s with the given URL: %s' % (error, url))
                return
            except requests.exceptions.ReadTimeout as error:
                _logger.warning('ReadTimeout: %s with the given URL: %s', (error, url))
                return
            if values['file_url'].split('.')[1] == 'zip':
                try:
                    content = self._extract_sii_xsd_from_zip(url, response, values['file_name'])
                except:
                    _logger.warning('UNZIP for %s failed from URL: %s' % (values['file_name'], url))
            else:
                content = response.content
            xsd_object = self._modify_and_validate_sii_xsd_content(content)
            if not len(xsd_object):
                return
            validated_content = etree.tostring(xsd_object, pretty_print=True)
            attachment = self.create({
                'name': values['file_name'],
                'description': values['description'],
                'datas': base64.encodebytes(validated_content),
                'company_id': False,
            })
            self.env['ir.model.data'].create({
                'name': values['file_name'],
                'module': 'l10n_cl_edi',
                'res_id': attachment.id,
                'model': 'ir.attachment',
                'noupdate': True,
            })
            file = join(tools.config.filestore(self.env.cr.dbname), attachment.store_fname)
            files.append(file)

        return files
