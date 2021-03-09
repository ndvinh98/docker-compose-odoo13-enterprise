# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hashlib
import os

from odoo import http
from odoo.http import request

from odoo.addons.point_of_sale.controllers.main import PosController

class GovCertificationController(http.Controller):
    @http.route('/fdm_source', auth='public')
    def handler(self):
        data = {'files': []}
        main_hash = ""
        relative_file_paths_to_show = [
            "pos_blackbox_be/data/pos_blackbox_be_data.xml",
            "pos_blackbox_be/models/pos_blackbox_be.py",
            "pos_blackbox_be/security/ir.model.access.csv",
            "pos_blackbox_be/security/pos_blackbox_be_security.xml",
            "pos_blackbox_be/static/lib/sha1.js",
            "pos_blackbox_be/static/src/css/pos_blackbox_be.css",
            "pos_blackbox_be/static/src/js/pos_blackbox_be.js",
            "pos_blackbox_be/static/src/xml/pos_blackbox_be.xml",
            "pos_blackbox_be/views/pos_blackbox_be_assets.xml",
            "pos_blackbox_be/views/pos_blackbox_be_views.xml",
            "pos_blackbox_be/controllers/main.py",
            "pos_hr_l10n_be/data/pos_hr_l10n_be_data.xml",
            "pos_hr_l10n_be/models/hr_employee.py",
            "pos_hr_l10n_be/static/src/js/pos_hr_l10n_be.js",
            "pos_hr_l10n_be/views/hr_employee_view.xml",
            "pos_hr_l10n_be/views/pos_hr_l10n_be_assets.xml"
        ]

        for relative_file_path in relative_file_paths_to_show:
            absolute_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, relative_file_path))
            size_in_bytes = os.path.getsize(absolute_file_path)

            with open(absolute_file_path, 'rb') as f:
                content = f.read()
                data['files'].append({
                    'name': relative_file_path,
                    'size_in_bytes': size_in_bytes,
                    'contents': content,
                    'hash': hashlib.sha1(content).hexdigest()
                })
                main_hash += hashlib.sha1(content).hexdigest()

        data['main_hash'] = hashlib.sha1(main_hash.encode('utf-8')).hexdigest()

        return request.render('pos_blackbox_be.fdm_source', data, mimetype='text/plain')

    @http.route("/journal_file/<string:serial>", auth="user")
    def journal_file(self, serial, **kw):
        """ Give the journal file report for a specific blackbox
        serial: e.g. BODO001bd6034a
        """
        logs = request.env["pos_blackbox_be.log"].search([
            ("action", "=", "create"),
            ("model_name", "in", ["pos.order", "pos.order_pro_forma"]),
            ("description", "ilike", serial),
        ], order='id')

        data = {
            'pos_id': serial,
            'logs': logs,
        }

        return request.render("pos_blackbox_be.journal_file", data, mimetype="text/plain")


class BlackboxPOSController(PosController):
    @http.route()
    def pos_web(self, **k):
        response = super(BlackboxPOSController, self).pos_web(**k)

        if response.status_code == 200:
            pos_session = request.env['pos.session']
            active_pos_session = pos_session.search([('state', '=', 'opened'), ('user_id', '=', request.session.uid)], limit=1)
            response.qcontext.update({
                'blackbox': active_pos_session.config_id.blackbox_pos_production_id
            })
        return response
