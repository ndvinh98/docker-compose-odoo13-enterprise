# -*- coding: utf-8 -*-

from . import models
from . import report
from . import controllers

from odoo import api, SUPERUSER_ID


def _configure_fsm_project(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    fsm_project = env.ref("industry_fsm.fsm_project", raise_if_not_found=False)
    if fsm_project:
        fsm_project.write(
            {
                "worksheet_template_id": env.ref("industry_fsm_report.fsm_worksheet_template").id,
                "allow_worksheets": True,
            }
        )

    fsm_product = env.ref("industry_fsm.field_service_product", raise_if_not_found=False)
    if fsm_product:
        fsm_product.write(
            {"worksheet_template_id": env.ref("industry_fsm_report.fsm_worksheet_template").id,}
        )
