# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StockLandedCost(models.Model):
    _inherit = 'stock.landed.cost'

    __pattern = re.compile(r'[0-9]{2}  [0-9]{2}  [0-9]{4}  [0-9]{7}')

    l10n_mx_edi_customs_number = fields.Char(
        help='Optional field for entering the customs information in the case '
        'of first-hand sales of imported goods or in the case of foreign trade'
        ' operations with goods or services.\n'
        'The format must be:\n'
        ' - 2 digits of the year of validation followed by two spaces.\n'
        ' - 2 digits of customs clearance followed by two spaces.\n'
        ' - 4 digits of the serial number followed by two spaces.\n'
        ' - 1 digit corresponding to the last digit of the current year, '
        'except in case of a consolidated customs initiated in the previous '
        'year of the original request for a rectification.\n'
        ' - 6 digits of the progressive numbering of the custom.',
        string='Customs number', size=21, copy=False)

    _sql_constraints = [
        ('l10n_mx_edi_customs_number',
         'unique (l10n_mx_edi_customs_number)',
         _('The custom number must be unique!'))
    ]

    @api.constrains('l10n_mx_edi_customs_number')
    def check_l10n_mx_edi_customs_number_format(self):
        help_message = self.fields_get().get(
            "l10n_mx_edi_customs_number").get("help").split('\n', 1)[1]
        for rec in self.filtered('l10n_mx_edi_customs_number'):
            if not self.__pattern.match(rec.l10n_mx_edi_customs_number):
                raise ValidationError(_(
                    'Error!, The format of the customs number is'
                    ' incorrect. \n%s\n'
                    'For example: 15  48  3009  0001234') % (help_message))
