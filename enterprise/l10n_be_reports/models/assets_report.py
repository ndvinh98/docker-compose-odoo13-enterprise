# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _
from odoo.tools.misc import formatLang
from odoo.exceptions import UserError
from itertools import groupby


class AssetsReport(models.AbstractModel):
    _inherit = 'account.report'

    def _get_account_groups_for_asset_report(self):
        "This method is intended to be used only with account_asset installed"
        if self.env.company.country_id.code == 'BE':
            return {
                '20': {'name': _('20 Frais d’établissement')},
                '21': {'name': _('21 Immobilisations incorporelles')},
                '22-27': {'name': _('22/27 Immobilisations corporelles'),
                          'children': {
                              '22': {'name': _('22 Terrains et constructions')},
                              '23': {'name': _('23 Installations, machines et outillage')},
                              '24': {'name': _('24 Mobilier et matériel roulant 24')},
                              '25': {'name': _('25 Immobilisations détenues en location-financement et droits similaires')},
                              '26': {'name': _('26 Autres immobilisations corporelles')},
                              '27': {'name': _('27 Immobilisations corporelles en cours et acomptes versés')},
                              },
                          },
                '28': {'name': _('28 Immobilisations financières')},
            }
        return super(AssetsReport, self)._get_account_groups_for_asset_report()
