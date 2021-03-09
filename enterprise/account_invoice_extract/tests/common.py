# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from contextlib import contextmanager
from unittest.mock import patch

from odoo.addons.account_invoice_extract.models.account_invoice import AccountMove
from odoo.addons.iap.models.iap import IapAccount
from odoo.sql_db import Cursor
from odoo.tests import common


class MockIAP(common.BaseCase):
    @contextmanager
    def mock_iap_extract(self, extract_response, partner_autocomplete_response):
        def _contact_iap_extract(local_endpoint, params):
            return extract_response

        def _contact_iap_partner_autocomplete(local_endpoint, params):
            return partner_autocomplete_response

        def get_credits(service_name):
            return 1

        def commit():
            pass

        try:
            with patch.object(AccountMove, '_contact_iap_extract', side_effect=_contact_iap_extract) as contact_iap_extract_mock:
                with patch.object(AccountMove, '_contact_iap_partner_autocomplete', side_effect=_contact_iap_partner_autocomplete) as contact_iap_partner_autocomplete_mock:
                    # the module iap is committing the transaction when creating an IAP account, we mock it to avoid that
                    with patch.object(IapAccount, 'get_credits', side_effect=get_credits) as iap_account_get_credits:
                        with patch.object(Cursor, 'commit', side_effect=commit) as cursor_commit_mock:
                            yield
        finally:
            pass
