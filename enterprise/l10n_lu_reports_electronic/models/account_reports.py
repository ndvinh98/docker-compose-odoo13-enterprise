# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
import base64
from io import BytesIO
from datetime import datetime
from odoo import models, tools, _
from odoo.exceptions import UserError


class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    def _get_reports_buttons(self):
        res = super()._get_reports_buttons()
        # disable XML export for users belonging to companies other than Luxembourg country
        if not self._is_lu_electronic_report() or self.env.company.country_id.code != 'LU':
            return res
        res += [{'name': _('Export (XML)'), 'sequence': 3, 'action': 'print_xml', 'file_export_type': _('XML')}]
        return res

    def get_report_filename(self, options):
        if not self._is_lu_electronic_report():
            return super().get_report_filename(options)
        # we can't determine milliseconds using fields.Datetime, hence used python's `datetime`
        now_datetime = datetime.now()
        file_ref_data = {
            'ecdf_prefix': self.env.company.ecdf_prefix,
            'datetime': now_datetime.strftime('%Y%m%dT%H%M%S%f')[:-4]
        }
        filename = '{ecdf_prefix}X{datetime}'.format(**file_ref_data)
        # `FileReference` element of exported XML must have same `filename` as above. So, we pass it from
        # here and get it from options in `_get_lu_electronic_report_values` and pass it further to template.
        options['filename'] = filename
        return filename

    # TO BE OVERWRITTEN
    def _is_lu_electronic_report(self):
        return False

    def _get_lu_electronic_report_values(self, options):
        company = self.env.company
        return {
            'filename': options.get('filename'),
            'lang': 'EN',
            'interface' : 'MODL5',
            'vat_number' : company.vat or "NE",
            'matr_number' : company.matr_number or "NE",
            'rcs_number' : company.company_registry or "NE",
        }

    def _lu_validate_ecdf_prefix(self):
        ecdf_prefix = self.env.company.ecdf_prefix
        if not ecdf_prefix:
            raise UserError(_('Please set valid eCDF Prefix for your company.'))
        re_valid_prefix = re.compile(r'[0-9|A-Z]{6}$')
        if not re_valid_prefix.match(ecdf_prefix):
            msg = _('eCDF Prefix `{0}` associated with `{1}` company is invalid.\nThe expected format is ABCD12 (Six digits of numbers or capital letters)')
            raise UserError(msg.format(ecdf_prefix, self.env.company.display_name))
        return True

    def _lu_validate_xml_content(self, content):
        attachment = self.env.ref('l10n_lu_reports_electronic.xsd_cached_eCDF_file_v1_1-XML_schema_xsd', raise_if_not_found=False)
        if attachment:
            xsd_datas = base64.b64decode(attachment.datas) if attachment else b''
            with BytesIO(xsd_datas) as xsd:
                tools.xml_utils._check_with_xsd(content, xsd)
        return True
