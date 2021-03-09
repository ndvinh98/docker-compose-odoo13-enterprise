# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request
from werkzeug.urls import url_encode

import werkzeug


class YodleeController(http.Controller):

    # This controller is needed because yodlee append query informations to the end of our
    # callback URL and we can't have an URL that looks like http://localhost/web#action=12?state=success
    # The query parameters must be before the hash. Therefore we use this controller that will redirect
    # to the correct action and will set the parameter in a correct way as well
    @http.route('/sync_status/<string:journal>/<string:state>', type='http', auth='user', methods=['GET'])
    def sync_status_name(self, journal, state, **kw):
        provider_identifier = kw.get('JSONcallBackStatus', '')
        # read action id and redirect to it with correct parameters
        if provider_identifier != '':
            action_id = request.env.ref('account_yodlee.yodlee_widget').id
        else:
            action_id = request.env.ref('account.open_account_journal_dashboard_kanban').id
        params = {
                'action': action_id,
                'state': state,
                'journal_id': journal,
                'provider_identifier': provider_identifier
                }
        url = '/web#' + url_encode(params)
        return werkzeug.utils.redirect(url, 303)