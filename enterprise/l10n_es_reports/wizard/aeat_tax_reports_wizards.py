# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _

class AEATTaxReportWizard(models.TransientModel):
    _name = 'l10n_es_reports.aeat.report.wizard'
    _description = "AEAT Tax Report Wizard"
    _modelo = None # To be defined in subclasses as 'xxx', where xxx is the modelo number of the implemented AEAT tax report

    currency_id = fields.Many2one(string='Currency', comodel_name='res.currency', default=lambda x: x.env.company.currency_id)

    def close_and_show_report(self):
        report = self.env.ref('l10n_es_reports.mod_' + self._modelo)
        return {
            'type': 'ir.actions.client',
            'name': _('Tax Report (Mod %s)') % self._modelo,
            'tag': 'account_report',
            'context': {
                'model': 'account.financial.html.report',
                'id': report.id,
                'aeat_wizard_id': self.id,
                'aeat_modelo': self._modelo,
            }
        }


class Mod111Wizard(models.TransientModel):
    _name = 'l10n_es_reports.mod111.wizard'
    _description = "Spain Tax Report Wizard for (mod111)"
    _inherit = 'l10n_es_reports.aeat.report.wizard'
    _modelo = '111'

    casilla_10 = fields.Integer(string="[10] Nº de perceptores", default=0)
    casilla_11 = fields.Monetary(string="[11] Valor percepciones en especie", default=0)
    casilla_12 = fields.Monetary(string="[12] Importe de los ingresos a cuenta", default=0)
    casilla_13 = fields.Integer(string="[13] Nº de perceptores", default=0)
    casilla_14 = fields.Monetary(string="[14] Importe de las percepciones", default=0)
    casilla_15 = fields.Monetary(string="[15] Importe de las retenciones", default=0)
    casilla_16 = fields.Integer(string="[16] Nº de perceptores", default=0)
    casilla_17 = fields.Monetary(string="[17] Valor percepciones en especie", default=0)
    casilla_18 = fields.Monetary(string="[18] Importe de los ingresos a cuenta", default=0)
    casilla_19 = fields.Integer(string="[19] Nº de perceptores", default=0)
    casilla_20 = fields.Monetary(string="[20] Importe de las percepciones", default=0)
    casilla_21 = fields.Monetary(string="[21] Importe de las retenciones", default=0)
    casilla_22 = fields.Integer(string="[22] Nº de perceptores", default=0)
    casilla_23 = fields.Monetary(string="[23] Valor percepciones en especie", default=0)
    casilla_24 = fields.Monetary(string="[24] Importe de los ingresos a cuenta", default=0)
    casilla_25 = fields.Integer(string="[25] Nº de perceptores", default=0)
    casilla_26 = fields.Monetary(string="[26] Contraprestaciones satisfechas", default=0)
    casilla_27 = fields.Monetary(string="[27] Importe de los ingresos a cuenta", default=0)
    casilla_29 = fields.Monetary(string="[29] Resultados a ingresar anteriores", default=0)


class Mod115Wizard(models.TransientModel):
    _name = 'l10n_es_reports.mod115.wizard'
    _description = "Spain Tax Report Wizard for (mod115)"
    _inherit = 'l10n_es_reports.aeat.report.wizard'
    _modelo = '115'

    casilla_04 = fields.Monetary(string="[04] Resultados a ingresar anteriores", default=0)


class Mod303Wizard(models.TransientModel):
    _name = 'l10n_es_reports.mod303.wizard'
    _description = "Spain Tax Report Wizard for (mod303)"
    _inherit = 'l10n_es_reports.aeat.report.wizard'
    _modelo = '303'

    casilla_43 = fields.Monetary(string="[43] Regularización bienes de inversión", default=0)
    casilla_44 = fields.Monetary(string="[44] Regularización por aplicación del porcentaje definitivo de prorrata", default=0)
    casilla_62 = fields.Monetary(string="[62] Base imponible", default=0)
    casilla_63 = fields.Monetary(string="[63] Cuota", default=0)
    casilla_65 = fields.Monetary(string="[65] % Atribuible a la Administración", default=0)
    casilla_67 = fields.Monetary(string="[67] Cuotas a compensar de periodos anteriores", default=0)
    casilla_68 = fields.Monetary(string="[68] Resultado de la regularización anual", default=0)
    casilla_69 = fields.Monetary(string="[69] Resultado", default=0)
    casilla_70 = fields.Monetary(string="[70] A deducir", default=0)
