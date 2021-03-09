# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields

class ResCompany(models.Model):
    _inherit = "res.company"

    matr_number = fields.Char(string="Matr Number")
    ecdf_prefix = fields.Char(string="eCDF Prefix")
