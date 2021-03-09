# -*- coding: utf-8 -*-
import requests
import json
import datetime
import logging

from odoo import models, api, fields, SUPERUSER_ID
from odoo.tools.translate import _
from odoo.exceptions import AccessError, UserError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, date_utils

_logger = logging.getLogger(__name__)

class PlaidProviderAccount(models.Model):
    _inherit = ['account.online.provider']

    provider_type = fields.Selection(selection_add=[('plaid', 'Plaid')])
    plaid_error_type = fields.Char(readonly=True, help='Additional information on error')
    plaid_item_id = fields.Char(readonly=True, help='item id in plaid database')

    def _get_available_providers(self):
        ret = super(PlaidProviderAccount, self)._get_available_providers()
        ret.append('plaid')
        return ret

    def _get_plaid_credentials(self):
        ICP_obj = self.env['ir.config_parameter'].sudo()
        login = self._cr.dbname
        secret = ICP_obj.get_param('database.uuid')
        base_url = self.sudo().env['ir.config_parameter'].get_param('odoo.online_sync_proxy') or 'https://onlinesync.odoo.com'
        url = base_url + '/plaid/api/2'
        return {'login': login, 'secret': secret, 'url': url}

    def check_plaid_error(self, resp):
        try:
            resp_json = resp.json()
            # Reply to /item/get may encapsulate the error in the error key
            if type(resp_json) == dict and resp_json.get('error', False):
                resp_json = resp_json.get('error')
            if type(resp_json) == dict and resp_json.get('error_code') and resp.status_code >= 400:
                message = _('There was en error with Plaid Services!\n{message: %s,\nerror code: %s,\nerror type: %s,\nrequest id: %s}')
                message = message % (resp_json.get('display_message') or resp_json.get('error_message'), 
                    resp_json.get('error_code', ''), resp_json.get('error_type', ''), resp_json.get('request_id', ''))
                if self and self.id:
                    self._update_status('FAILED', resp_json)
                    self.flush(['status'])
                    self.log_message(message)
                raise UserError(message)
            elif resp.status_code in (400, 403):
                if self and self.id:
                    self._update_status('FAILED', {})
                    self.flush(['status'])
                    self.log_message(resp.text)
                raise UserError(resp.text)
            resp.raise_for_status()
        except (requests.HTTPError, ValueError):
            message = _('Get %s status code for call to %s. Content message: %s' % (resp.status_code, resp.url, resp.text))
            if self and self.id:
                self.log_message(message)
            raise UserError(message)

    def plaid_fetch(self, url, data):
        credentials = self._get_plaid_credentials()
        url = credentials['url'] + url
        try:
            data['client_id'] = credentials['login']
            data['secret'] = credentials['secret']
            if len(self.ids) and self.provider_account_identifier:
                data['access_token'] = self.provider_account_identifier
                if self.provider_identifier.startswith('development_'):
                    data['environment'] = 'development'
                elif self.provider_identifier.startswith('sandbox_'):
                    data['environment'] = 'sandbox'
            # This is only intended to work with Odoo proxy, if user wants to use his own plaid account
            # replace the query by requests.post(url, json=data, timeout=60)
            resp = requests.post(url, data=json.dumps(data, default=date_utils.json_default),
                                 timeout=60)
        except requests.exceptions.Timeout:
            raise UserError(_('Timeout: the server did not reply within 60s'))
        self.check_plaid_error(resp)
        resp_json = resp.json()
        if self and self.id:
            self._update_status('SUCCESS', resp_json)
        if resp_json.get('jsonrpc', '') == '2.0':
            return resp_json.get('result')
        return resp.json()

    def get_login_form(self, site_id, provider, beta=False):
        if provider != 'plaid':
            return super(PlaidProviderAccount, self).get_login_form(site_id, provider, beta)
        ctx = self.env.context.copy()
        ctx['method'] = 'add'
        environment = 'production'
        if site_id.startswith('development_'):
            environment = 'development'
            site_id = site_id.replace('development_', '')
        if site_id.startswith('sandbox_'):
            environment = 'sandbox'
            site_id = site_id.replace('sandbox_', '')
        return {
            'type': 'ir.actions.client',
            'tag': 'plaid_online_sync_widget',
            'target': 'new',
            'institution_id': site_id,
            'open_link': True,
            'environment': environment,
            'public_key': self.plaid_fetch('/public_key', {}).get('public_key'),
            'context': ctx,
        }

    def link_success(self, public_token, metadata):
        # convert public token to access_token and create a provider with accounts defined in metadata
        data = {'public_token': public_token}
        environment = metadata.get('environment', 'production')
        if environment != 'production':
            data['environment'] = environment
        resp_json = self.plaid_fetch('/item/public_token/exchange', data)
        provider_identifier = metadata.get('institution', {}).get('institution_id', '')
        if environment != 'production':
            provider_identifier = environment + '_' + provider_identifier
        item_vals = {
            'name': metadata.get('institution', {}).get('name', ''), 
            'provider_type': 'plaid', 
            'provider_account_identifier': resp_json.get('access_token'),
            'plaid_item_id': resp_json.get('item_id'),
            'provider_identifier': provider_identifier,
            'status': 'SUCCESS',
            'status_code': 0
        }
        accounts_ids = [m.get('id') for m in metadata.get('accounts') if m.get('id')]
        # Call plaid to get balance on all selected accounts.
        data = { 'access_token': resp_json.get('access_token'), 'options': {'account_ids': accounts_ids}}
        if environment != 'production':
            data['environment'] = environment
        resp_json = self.plaid_fetch('/accounts/balance/get',data)
        account_vals = []
        for acc in resp_json.get('accounts'):
            account_vals.append((0, 0, {
                'name': acc.get('name'),
                'account_number': acc.get('mask'),
                'online_identifier': acc.get('account_id'),
                'balance': acc.get('balances', {}).get('available', 0),
            }))
        item_vals['account_online_journal_ids'] = account_vals
        provider_account = self.create(item_vals)
        result = {'status': 'SUCCESS', 'added': provider_account.account_online_journal_ids, 'method': self.env.context.get('method')}
        if self.env.context.get('journal_id', False):
            result['journal_id'] = self.env.context.get('journal_id')
        return self.show_result(result)


    def _update_status(self, status, resp_json=None):
        if not self.user_has_groups('account.group_account_user'):
            raise AccessError(_('Only an Accountant is allowed to perform this operation.'))
        if not resp_json:
            resp_json = {}
        code = str(resp_json.get('error_code', 0))
        message = resp_json.get('display_message') or resp_json.get('error_message') or ''
        error_type = resp_json.get('error_type', '')
        with self.pool.cursor() as cr:
            self = self.with_env(self.env(cr=cr, user=SUPERUSER_ID)).write({
                'status': status, 
                'status_code': code, 
                'last_refresh': fields.Datetime.now(),
                'message': message,
                'plaid_error_type': error_type,
                'action_required': True if status == 'FAILED' else False
            })

    def manual_sync(self):
        if self.provider_type != 'plaid':
            return super(PlaidProviderAccount, self).manual_sync()
        transactions = []
        for account in self.account_online_journal_ids:
            if account.journal_ids:
                tr = account.retrieve_transactions()
                transactions.append({'journal': account.journal_ids[0].name, 'count': tr})
        result = {'status': 'SUCCESS', 'transactions': transactions, 'method': 'refresh', 'added': self.env['account.online.journal']}
        return self.show_result(result)

    def update_credentials(self):
        if self.provider_type != 'plaid':
            return super(PlaidProviderAccount, self).update_credentials()
        # Create public token and open link in update mode with that token
        resp_json = self.plaid_fetch('/item/public_token/create', {})
        ret_action = self.get_login_form(self.provider_identifier, 'plaid')
        ret_action['public_token'] = resp_json.get('public_token')
        ret_action['account_online_provider_id'] = self.id
        ctx = self.env.context.copy()
        ctx['method'] = 'edit'
        ctx['journal_id'] = False
        return ret_action

    @api.model
    def cron_fetch_online_transactions(self):
        if self.provider_type != 'plaid':
            return super(PlaidProviderAccount, self).cron_fetch_online_transactions()
        self.manual_sync()

    def unlink(self):
        for provider in self:
            if provider.provider_type == 'plaid':
                # call plaid to ask to remove item
                try:
                    ctx = self._context.copy()
                    ctx['no_post_message'] = True
                    provider.with_context(ctx).plaid_fetch('/item/remove', {})
                except UserError:
                    # If call to fails, don't prevent user to delete record 
                    pass
        super(PlaidProviderAccount, self).unlink()

class PlaidAccount(models.Model):
    _inherit = 'account.online.journal'

    def retrieve_transactions(self):
        if (self.account_online_provider_id.provider_type != 'plaid'):
            return super(PlaidAccount, self).retrieve_transactions()
        transactions = []
        offset = 0
        # transactions are paginated by 500 results so we need to loop to ensure we have every transactions
        while True:
            params = {
                'start_date': self.last_sync or fields.Date.today(),
                'end_date': fields.Date.today(),
                'options': {'account_ids': [self.online_identifier], 'count': 500, 'offset': offset},
            }
            resp_json = self.account_online_provider_id.plaid_fetch('/transactions/get', params)
            # Update the balance
            for account in resp_json.get('accounts', []):
                if account.get('account_id', '') == self.online_identifier:
                    end_amount = account.get('balances', {}).get('current', 0)
            # Prepare the transaction
            for transaction in resp_json.get('transactions'):
                if transaction.get('pending') == False:
                    trans = {
                        'online_identifier': transaction.get('transaction_id'),
                        'date': fields.Date.from_string(transaction.get('date')),
                        'name': transaction.get('name'),
                        'amount': -1 * transaction.get('amount'), #https://plaid.com/docs/api/#transactions amount positive if purchase
                        'end_amount': end_amount,
                    }
                    if transaction.get('payment_meta') and transaction['payment_meta'].get('payee_name', False) and transaction.get('amount') > 0:
                        trans['online_partner_vendor_name'] = transaction['payment_meta']['payee_name']
                        trans['partner_id'] = self._find_partner([('online_partner_vendor_name', '=', transaction['payment_meta']['payee_name'])])
                    if 'location' in transaction and not trans.get('partner_id'):
                        trans['partner_id'] = self._find_partner_from_location(transaction.get('location'))
                    transactions.append(trans)
            if resp_json.get('total_transactions', 0) <= offset + 500:
                break
            else:
                offset += 500
        # Create the bank statement with the transactions
        return self.env['account.bank.statement'].online_sync_bank_statement(transactions, self.journal_ids[0])
