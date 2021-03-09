# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from dateutil.relativedelta import relativedelta
from datetime import date
from lxml import etree

from odoo import api, fields, models, _
from odoo.tools import date_utils
from odoo.exceptions import ValidationError
from odoo.addons.l10n_be_hr_payroll.models.hr_dmfa import DMFANode, format_amount


class DMFACompanyVehicle(DMFANode):

    def __init__(self, vehicle, sequence=1):
        super().__init__(vehicle.env, sequence=sequence)
        self.license_plate = vehicle.license_plate


class HrDMFAReport(models.Model):
    _inherit = 'l10n_be.dmfa'

    vehicle_ids = fields.One2many('fleet.vehicle', compute='_compute_vehicle_ids')

    @api.depends('quarter_end')
    def _compute_vehicle_ids(self):
        for dmfa in self:
            vehicles = self.env['fleet.vehicle'].search([
                ('first_contract_date', '<=', dmfa.quarter_end),
                ('driver_id', '!=', False),  # contribution for unused cars?
                ('company_id', '=', dmfa.company_id.id),
            ])
            dmfa.vehicle_ids = [(6, False, vehicles.ids)]

    def _get_rendering_data(self):
        return dict(
            super()._get_rendering_data(),
            vehicles_cotisation=format_amount(self._get_vehicles_contribution()),
            vehicles=DMFACompanyVehicle.init_multi([(vehicle,) for vehicle in self.vehicle_ids]),
        )

    def _get_vehicles_contribution(self):
        amount = 0
        self = self.sudo()
        for vehicle in self.vehicle_ids:
            n_months = min(relativedelta(self.quarter_end, self.quarter_start).months, relativedelta(self.quarter_end, vehicle.first_contract_date).months)
            amount += vehicle.co2_fee * n_months
        return amount

    def _get_global_contribution(self, payslips):
        amount = super()._get_global_contribution(payslips)
        return amount + self._get_vehicles_contribution()
